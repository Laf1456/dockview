"""
Redis Adapter
Provides key browsing for Redis containers.
"""

import logging
import redis.asyncio as aioredis

from app.adapters.base import BaseAdapter
from app.adapters.registry import register
from app.models import DatabaseType, TableInfo, TablePreview, ColumnInfo

logger = logging.getLogger("dockview.adapter.redis")


@register(DatabaseType.REDIS)
class RedisAdapter(BaseAdapter):

    def _client(self, db: int = 0):
        password = self.creds.get("password") or None
        return aioredis.Redis(
            host=self.db.host,
            port=self.db.port,
            password=password,
            db=db,
            decode_responses=True,
            socket_connect_timeout=5,
        )

    async def test_connection(self) -> bool:
        try:
            r = self._client()
            await r.ping()
            await r.aclose()
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            return False

    async def list_databases(self) -> list[str]:
        """Return Redis logical DBs (0-15) that have keys."""
        r = self._client()
        try:
            info = await r.info("keyspace")
            dbs = [k for k in info.keys() if k.startswith("db")]
            if not dbs:
                dbs = ["db0"]
            return dbs
        finally:
            await r.aclose()

    async def list_tables(self, database: str) -> list[TableInfo]:
        """Return key type groups as pseudo-tables."""
        db_num = int(database.replace("db", ""))
        r = self._client(db_num)
        try:
            keys = await r.keys("*")
            type_groups: dict[str, int] = {}
            for key in keys[:500]:  # Sample first 500 keys
                ktype = await r.type(key)
                type_groups[ktype] = type_groups.get(ktype, 0) + 1

            tables = [
                TableInfo(
                    name=f"[{ktype}] keys",
                    row_count=count,
                    collection_type="collection",
                )
                for ktype, count in sorted(type_groups.items())
            ]

            if not tables:
                tables = [TableInfo(name="(empty)", row_count=0, collection_type="collection")]

            return tables
        finally:
            await r.aclose()

    async def get_columns(self, database: str, table: str) -> list[ColumnInfo]:
        return [
            ColumnInfo(name="key", data_type="string", nullable=False, is_primary_key=True),
            ColumnInfo(name="type", data_type="string"),
            ColumnInfo(name="value", data_type="mixed"),
            ColumnInfo(name="ttl", data_type="integer"),
        ]

    async def preview_table(
        self, database: str, table: str, limit: int = 50, offset: int = 0
    ) -> TablePreview:
        db_num = int(database.replace("db", ""))
        r = self._client(db_num)
        try:
            # Extract key type from table name like "[string] keys"
            key_type = None
            if table.startswith("["):
                key_type = table.split("]")[0].lstrip("[")

            keys = await r.keys("*")
            filtered_keys = []
            for k in keys:
                if key_type:
                    t = await r.type(k)
                    if t == key_type:
                        filtered_keys.append(k)
                else:
                    filtered_keys.append(k)

            paged_keys = filtered_keys[offset: offset + limit]
            rows = []
            for k in paged_keys:
                ktype = await r.type(k)
                ttl = await r.ttl(k)
                try:
                    if ktype == "string":
                        val = await r.get(k)
                    elif ktype == "list":
                        val = str(await r.lrange(k, 0, 10))
                    elif ktype == "hash":
                        val = str(await r.hgetall(k))
                    elif ktype == "set":
                        val = str(await r.smembers(k))
                    elif ktype == "zset":
                        val = str(await r.zrange(k, 0, 10, withscores=True))
                    else:
                        val = "(unknown type)"
                except Exception:
                    val = "(error reading value)"
                rows.append([k, ktype, val, ttl if ttl >= 0 else "∞"])

            columns = await self.get_columns(database, table)
            return TablePreview(
                columns=columns,
                rows=rows,
                total_rows=len(filtered_keys),
                limit=limit,
                offset=offset,
                truncated=len(filtered_keys) > (offset + limit),
            )
        finally:
            await r.aclose()

    async def get_server_info(self) -> dict:
        r = self._client()
        try:
            info = await r.info("server")
            return {
                "version": info.get("redis_version", "unknown"),
                "mode": info.get("redis_mode", "standalone"),
                "os": info.get("os", ""),
            }
        finally:
            await r.aclose()
