"""
Docker Inspector Service
Scans running containers, identifies databases, extracts connection info.

ENHANCED:
- Multi-strategy Docker connection (Linux, macOS, Windows)
- Smart host resolution (cross-network, Docker Desktop, bridge fallback)
- Non-breaking: preserves all existing logic
"""

import asyncio
import logging
import os
from typing import Any

import docker
from docker.errors import DockerException

from app.models import DetectedDatabase, DatabaseType
from app.adapters.registry import AdapterRegistry

logger = logging.getLogger("dockview.inspector")

# Image name → DB type mapping
IMAGE_PATTERNS: dict[str, DatabaseType] = {
    "postgres": DatabaseType.POSTGRES,
    "postgis": DatabaseType.POSTGRES,
    "supabase/postgres": DatabaseType.POSTGRES,
    "mysql": DatabaseType.MYSQL,
    "mariadb": DatabaseType.MYSQL,
    "percona": DatabaseType.MYSQL,
    "mongo": DatabaseType.MONGO,
    "bitnami/mongodb": DatabaseType.MONGO,
    "redis": DatabaseType.REDIS,
    "bitnami/redis": DatabaseType.REDIS,
    "keydb": DatabaseType.REDIS,
    "sqlite": DatabaseType.SQLITE,
}

# Default ports per DB type
DEFAULT_PORTS: dict[DatabaseType, int] = {
    DatabaseType.POSTGRES: 5432,
    DatabaseType.MYSQL: 3306,
    DatabaseType.MONGO: 27017,
    DatabaseType.REDIS: 6379,
    DatabaseType.SQLITE: 0,
}

# ENV variable patterns per DB type
ENV_PATTERNS: dict[DatabaseType, dict[str, list[str]]] = {
    DatabaseType.POSTGRES: {
        "user": ["POSTGRES_USER", "PGUSER"],
        "password": ["POSTGRES_PASSWORD", "PGPASSWORD"],
        "database": ["POSTGRES_DB", "PGDATABASE"],
    },
    DatabaseType.MYSQL: {
        "user": ["MYSQL_USER", "MARIADB_USER"],
        "password": ["MYSQL_PASSWORD", "MARIADB_PASSWORD", "MYSQL_ROOT_PASSWORD"],
        "database": ["MYSQL_DATABASE", "MARIADB_DATABASE"],
        "root_password": ["MYSQL_ROOT_PASSWORD", "MARIADB_ROOT_PASSWORD"],
    },
    DatabaseType.MONGO: {
        "user": ["MONGO_INITDB_ROOT_USERNAME", "MONGODB_USERNAME"],
        "password": ["MONGO_INITDB_ROOT_PASSWORD", "MONGODB_PASSWORD"],
        "database": ["MONGO_INITDB_DATABASE", "MONGODB_DATABASE"],
    },
    DatabaseType.REDIS: {
        "password": ["REDIS_PASSWORD", "REQUIREPASS"],
    },
}


class DockerInspector:
    """Core engine that watches Docker and discovers databases."""

    def __init__(self):
        self._client: docker.DockerClient | None = None
        self._databases: dict[str, DetectedDatabase] = {}
        self._watch_task: asyncio.Task | None = None
        self._connected = False
        self._error: str | None = None

        # thread + loop control
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False

    async def start(self):
        """Initialize Docker client and start watching (with fallbacks)."""
        self._loop = asyncio.get_running_loop()
        self._running = True

        self._client = self._connect_with_fallbacks()

        if not self._client:
            self._connected = False
            self._error = "Docker not available (socket/env failed)"
            logger.warning("Docker not available: all connection strategies failed")
            return

        try:
            self._client.ping()
            self._connected = True

            await self._scan_containers()

            # run watcher safely (non-blocking)
            self._watch_task = asyncio.create_task(self._watch_events())

            logger.info("Docker inspector started successfully")

        except DockerException as e:
            self._error = str(e)
            self._connected = False
            logger.warning(f"Docker connected but ping failed: {e}")

    def _connect_with_fallbacks(self) -> docker.DockerClient | None:
        """Try multiple Docker connection strategies."""

        strategies = []

        # 1. Standard env (works for Docker Desktop, remote, etc.)
        strategies.append(lambda: docker.from_env())

        # 2. Explicit Linux socket
        strategies.append(lambda: docker.DockerClient(base_url="unix:///var/run/docker.sock"))

        # 3. DOCKER_HOST override
        docker_host = os.getenv("DOCKER_HOST")
        if docker_host:
            strategies.append(lambda: docker.DockerClient(base_url=docker_host))

        for strategy in strategies:
            try:
                client = strategy()
                client.ping()
                logger.info("Docker connection established")
                return client
            except Exception as e:
                logger.debug(f"Docker connection strategy failed: {e}")

        return None

    async def stop(self):
        """Gracefully stop the inspector."""
        self._running = False

        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass

        if self._client:
            self._client.close()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def error(self) -> str | None:
        return self._error

    def get_all_databases(self) -> list[DetectedDatabase]:
        """Return all currently detected databases."""
        return list(self._databases.values())

    def get_database(self, db_id: str) -> DetectedDatabase | None:
        """Return a specific database by ID."""
        return self._databases.get(db_id)

    async def refresh(self):
        """Force a re-scan of all containers."""
        await self._scan_containers()

    async def _scan_containers(self):
        """Scan all running containers for databases."""
        if not self._client:
            return

        try:
            # ✅ FIXED: proper docker-py usage
            containers = await asyncio.to_thread(
                self._client.containers.list,
                all=False
            )

            logger.info(f"Scanning {len(containers)} containers...")

            found_ids = set()

            for container in containers:
                try:
                    db = self._detect_database(container)
                    if db:
                        found_ids.add(db.id)

                        if db.id not in self._databases:
                            self._databases[db.id] = db
                            logger.info(
                                f"✅ Detected: {db.type.value} | {db.name} @ {db.host}:{db.port}"
                            )
                        else:
                            self._databases[db.id].status = "running"

                except Exception as e:
                    logger.warning(f"Container parse failed: {e}")

            # Mark stopped containers
            for db_id in list(self._databases.keys()):
                if db_id not in found_ids:
                    self._databases[db_id].status = "stopped"

        except Exception as e:
            logger.error(f"Scan error: {e}")
            

    def _detect_database(self, container) -> DetectedDatabase | None:
        """Attempt to detect if a container is a database."""
        image_name = ""
        try:
            image_name = (
                container.image.tags[0]
                if container.image.tags
                else container.image.short_id
            )
        except Exception:
            image_name = container.attrs.get("Config", {}).get("Image", "")

        db_type = self._identify_type(image_name)
        if not db_type:
            return None

        env_vars = self._parse_env(container)
        creds = self._extract_credentials(db_type, env_vars)
        host, port = self._extract_host_port(container, db_type)

        return DetectedDatabase(
            id=container.short_id,
            container_id=container.id,
            container_name=container.name,
            name=container.name.lstrip("/"),
            image=image_name,
            type=db_type,
            host=host,
            port=port,
            credentials=creds,
            status="running",
            env_vars=env_vars,
        )

    def _identify_type(self, image_name: str) -> DatabaseType | None:
        """Match image name against known patterns."""
        image_lower = image_name.lower().split(":")[0]
        for pattern, db_type in IMAGE_PATTERNS.items():
            if pattern in image_lower:
                return db_type
        return None

    def _parse_env(self, container) -> dict[str, str]:
        """Parse container environment variables into a dict."""
        env_list = container.attrs.get("Config", {}).get("Env") or []
        result = {}
        for item in env_list:
            if "=" in item:
                key, _, value = item.partition("=")
                result[key] = value
        return result

    def _extract_credentials(self, db_type: DatabaseType, env_vars: dict[str, str]) -> dict[str, str]:
        """Extract credentials from environment variables."""
        creds = {}
        patterns = ENV_PATTERNS.get(db_type, {})
        for field, keys in patterns.items():
            for key in keys:
                if key in env_vars:
                    creds[field] = env_vars[key]
                    break

        # Apply sensible defaults
        if db_type == DatabaseType.POSTGRES:
            creds.setdefault("user", "postgres")
            creds.setdefault("database", creds.get("user", "postgres"))
        elif db_type == DatabaseType.MYSQL:
            creds.setdefault("user", "root")
            if "root_password" in creds and "password" not in creds:
                creds["password"] = creds["root_password"]

        return creds

    def _extract_host_port(self, container, db_type: DatabaseType) -> tuple[str, int]:
        """Determine the host:port to connect on (ENHANCED CROSS-PLATFORM)."""
        default_port = DEFAULT_PORTS[db_type]

        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})

        # 1. Same Docker network (best case)
        for net_name, net_info in networks.items():
            ip = net_info.get("IPAddress")
            if ip:
                return ip, default_port

        # 2. Port mapping (Docker Desktop / cross-network)
        ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        port_key = f"{default_port}/tcp"

        if port_key in ports and ports[port_key]:
            mapped = ports[port_key][0]
            host_port = int(mapped["HostPort"])

            # macOS / Windows Docker Desktop
            if os.name != "posix":
                return "host.docker.internal", host_port

            # Linux fallback
            return "localhost", host_port

        # 3. Linux bridge fallback
        return "172.17.0.1", default_port

    async def _watch_events(self):
        """Watch Docker events and update DB list in real time."""
        try:
            await asyncio.to_thread(self._blocking_event_loop)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Event watch error: {e}")

    def _blocking_event_loop(self):
        """Blocking Docker event stream running safely in a thread."""
        try:
            for event in self._client.events(
                decode=True, filters={"type": "container"}
            ):
                if not self._running:
                    break

                action = event.get("Action", "")
                if action in ("start", "die", "stop", "destroy"):
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._scan_containers(),
                            self._loop,
                        )
                    logger.debug(f"Container event '{action}' — re-scanned")

        except Exception as e:
            logger.error(f"Blocking event loop error: {e}")