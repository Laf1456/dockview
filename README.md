# ⬡ DockView

**Zero-config Docker database viewer. Auto-detects PostgreSQL, MySQL, MongoDB & Redis. Browse schemas, tables, and row data in a beautiful browser UI — no setup required.**

![Version](https://img.shields.io/badge/version-1.0.0-7c6cf0)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-ready-2496ed)
![Docker Pulls](https://img.shields.io/docker/pulls/levichinecherem/dockview?color=2496ed&label=pulls&logo=docker)
![Docker Image Size](https://img.shields.io/docker/image-size/levichinecherem/dockview/latest?label=image%20size&logo=docker)
![GitHub stars](https://img.shields.io/github/stars/0xSemantic/dockview?style=social)
![Last Commit](https://img.shields.io/github/last-commit/0xSemantic/dockview)

---

## What is DockView?

DockView is a **single-container tool** that mounts the Docker socket, scans all running containers, automatically identifies database services, extracts connection credentials from environment variables, and presents everything in a fast read‑only browser interface.

**One command. Instant visibility. No configuration.**

```bash
docker run -d \
  -p 8080:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock:rw \
  --name dockview \
  --user root \
  levichinecherem/dockview:latest
```

Open `http://localhost:8080` — done.

---

## Features

| Feature | Details |
|---|---|
| 🔍 Auto‑detection | Scans running containers, identifies DB type by image name |
| 🐘 PostgreSQL | Full schema, table, column, and row preview |
| 🐬 MySQL / MariaDB | Databases, tables, row preview, column types |
| 🍃 MongoDB | Collections, document preview, inferred schema |
| ⚡ Redis | Key browsing by type, value preview, TTL display |
| 📋 CSV Export | Copy any table preview as CSV with one click |
| 🔄 Live Sync | Detects container start/stop via Docker events (SSE) |
| 🌙 Dark / Light | Theme toggle, persisted across sessions |
| 📱 PWA | Installable on desktop and mobile |
| 🔐 Read‑only | Zero write operations — safe by design |
| 🔑 Credential fallback | Manual credential entry if auto‑detection fails |

---

## Quick Start

Here’s a **complete Quick Start** replacement for DockView with a ready-to-use **Docker Compose example** that users can copy locally and run immediately. This focuses **only on Quick Start**, with auto-detection notes included.

---

### Option 1 — Docker Compose (recommended for auto-detection)

Create a file named `docker-compose.yml` in an empty directory with the following content:

```yaml
services:
  # ── DockView App ───────────────────────────────
  dockview:
    image: levichinecherem/dockview:latest
    container_name: dockview
    user: root   # ← run as root
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:rw
    restart: unless-stopped
    depends_on:
      - postgres
      - mysql
      - mongo
      - redis
    networks:
      - dockview-net

  # ── PostgreSQL ────────────────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: demo-postgres
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: secret123
    ports:
      - "5432:5432"
    volumes:
      - pg-data:/var/lib/postgresql/data
    networks:
      - dockview-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin -d appdb"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── MySQL ────────────────────────────────────
  mysql:
    image: mysql:8.0
    container_name: demo-mysql
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: shopdb
      MYSQL_USER: shopuser
      MYSQL_PASSWORD: shoppass
    ports:
      - "3306:3306"
    volumes:
      - mysql-data:/var/lib/mysql
    networks:
      - dockview-net
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ── MongoDB ──────────────────────────────────
  mongo:
    image: mongo:7.0
    container_name: demo-mongo
    environment:
      MONGO_INITDB_ROOT_USERNAME: root
      MONGO_INITDB_ROOT_PASSWORD: mongosecret
      MONGO_INITDB_DATABASE: catalog
    ports:
      - "27017:27017"
    volumes:
      - mongo-data:/data/db
    networks:
      - dockview-net

  # ── Redis ────────────────────────────────────
  redis:
    image: redis:7.4-alpine
    container_name: demo-redis
    command: redis-server --requirepass redispass
    ports:
      - "6379:6379"
    networks:
      - dockview-net

networks:
  dockview-net:
    driver: bridge

volumes:
  pg-data:
  mysql-data:
  mongo-data:
```

Then run:

```bash
docker-compose up -d
```

Open the UI at [http://localhost:8080](http://localhost:8080).

> ✅ DockView will **auto-detect the credentials** for all database containers because it shares the same Docker network and can read their environment variables.

---

### Option 2 — Standalone Docker run (manual credentials fallback)

```bash
docker run -d \
  -p 8080:8080 \
  -v /var/run/docker.sock:/var/run/docker.sock:rw \
  --name dockview \
  --user root \
  levichinecherem/dockview:latest
```

> **Note:** Auto-detection may **not work** in standalone mode. Use the **Reconnect modal** in the UI to enter credentials manually.

---

### Option 3 — Local development

```bash
# Clone and enter the repo
git clone https://github.com/0xSemantic/dockview.git
cd dockview

# Create virtual environment
python -m venv .venv
source .venv/bin/activate      # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```


---

## Using DockView

### Sidebar — Database List
- All detected databases appear on the left, each with a status dot (green = running, red = stopped)
- Click any database to open its Explorer panel

### Search Bar (`⌘K` / `Ctrl+K`)
- Quickly filter the sidebar by name, type, or display name

### Explorer Tab (three‑column layout)
1. **Schemas / Databases** – click to load tables
2. **Tables** – shows table name, row count estimate, and a relative size bar
3. **Data Preview** – paginated rows (50 per page)

### Schema Tab
- Displays full column‑level metadata for the selected table:
  - Column name, data type, nullable flag, default value, primary key indicator

### Server Info Tab
- Container details (name, image, network)
- Database server version and connection information

### CSV Export
- Click the **CSV** button in the data panel header to copy the current page to clipboard in CSV format

### Theme Toggle
- Sun/moon icon in the top‑right toggles between dark and light modes (saved to localStorage)

### Reconnect / Manual Credentials
- If auto‑detection fails (wrong password, custom setup), click **Reconnect** in the DB header. A modal lets you override:
  - Host, port, username, password, database name
  - Credentials are stored **in‑memory only** – never written to disk

---

## Security

> **Important:** The Docker socket grants root‑level access to the host. DockView is designed for **local development** and **internal tools** – do not expose it to the public internet without authentication.

**Current security model:**
- All database operations are **read‑only** – no INSERT, UPDATE, DELETE, DROP
- Credentials are held **in‑memory** only – never persisted
- API has no authentication layer in v1 (planned for v2)
- Docker socket is mounted **read‑only** (`:ro`) in the recommended run command

**Hardening recommendations:**
- Bind to localhost only: `-p 127.0.0.1:8080:8080`
- Use a reverse proxy with basic auth (e.g., Nginx)
- Run as non‑root (already done in the Docker image)
- Use IP allow‑listing if deployed on a trusted network

See [SECURITY.md](docs/SECURITY.md) for more details.

---

## Supported Databases

| Database | Detection | Auto‑credentials | Schemas | Tables | Row Preview |
|---|---|---|---|---|---|
| PostgreSQL | ✅ | ✅ | ✅ | ✅ | ✅ |
| MySQL / MariaDB | ✅ | ✅ | ✅ | ✅ | ✅ |
| MongoDB | ✅ | ✅ | Inferred | ✅ | ✅ |
| Redis | ✅ | ✅ | — | By type | ✅ |

**Adding a new adapter?** See [EXTENDING.md](docs/EXTENDING.md).

---

## Configuration

DockView can be configured via environment variables:

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind host |
| `PORT` | `8080` | Bind port |
| `WORKERS` | `1` | Number of Uvicorn workers |
| `LOG_LEVEL` | `info` | Logging verbosity |
| `DOCKER_HOST` | (socket) | Override Docker socket path (e.g., `unix:///var/run/docker.sock`) |
| `MAX_ROWS` | `50` | Default row preview limit |

**Example custom startup:**

```bash
docker run -d \
  -e PORT=9000 \
  -e LOG_LEVEL=debug \
  -e MAX_ROWS=100 \
  -p 9000:9000 \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  levichinecherem/dockview:latest
```

---

## Troubleshooting

### "Docker unavailable" / red status dot
- Ensure the Docker socket is mounted: `-v /var/run/docker.sock:/var/run/docker.sock:ro`
- Verify permissions: `ls -la /var/run/docker.sock`
- On Linux, you may need to add your user to the `docker` group or use `sudo`.

### Database shows but connection fails
- DockView connects to the container's internal Docker network IP. If your database is on a different network, use the **Reconnect** modal to enter `host=localhost` and the mapped port.
- Alternatively, ensure DockView and the database share the same Docker network (e.g., using a custom bridge).

### MongoDB auth fails
- Set `MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD` on the MongoDB container. DockView uses `authSource=admin` by default.

### Redis "NOAUTH" error
- Set `REDIS_PASSWORD` on the Redis container or manually enter it via the Reconnect modal.

### Tables show but rows return empty
- Verify the database user has SELECT privileges on the tables. For PostgreSQL:
  ```sql
  GRANT SELECT ON ALL TABLES IN SCHEMA public TO your_user;
  ```

### Container detected but wrong DB type
- DockView detects by image name. If you're using a custom/retagged image, you can add a label: `docker run -l "dockview.type=postgres" ...` (label support coming in v1.1).

---

## Architecture

```
Browser (PWA)
  │
  ▼
FastAPI Backend
  ├── Docker Inspector   — watches Docker socket, auto-detects DBs
  ├── Adapter Registry   — maps DB types to connection adapters
  ├── Credential Resolver — ENV vars → defaults → user input
  ├── SSE Stream         — pushes live container events to browser
  └── REST API           — /api/databases, /tables, /preview...
  │
  ▼
Docker Socket (/var/run/docker.sock)
  │
  ▼
Running Containers (Postgres, MySQL, Mongo, Redis...)
```

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for full technical details.

---

## Roadmap

- **v1.0** — Auto‑detection, table preview, CSV, PWA, live sync (current)
- **v1.1** — Query runner (read‑only SELECT), result export, label overrides
- **v1.2** — Container health badges, connection latency display
- **v2.0** — Authentication, multi‑host Docker support, schema diff
- **v3.0** — Cloud‑hosted version, team sharing, webhooks

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

**Development setup:**
```bash
git clone https://github.com/0xSemantic/dockview.git
cd dockview
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

---

## License

MIT © Levi Chinecherem. See [LICENSE](LICENSE) for details.

---

## Support & Feedback

- **Issues:** [GitHub Issues](https://github.com/0xSemantic/dockview/issues)
- **Discussions:** [GitHub Discussions](https://github.com/0xSemantic/dockview/discussions)

---

## ⭐ If this helped you, consider starring the repo
**Built with FastAPI, HTMX, and ❤️**