# DockView — Architecture Documentation

**Version:** 1.0  
**Type:** Technical Reference  
**Audience:** Contributors, platform engineers, security reviewers

---

## 1. System Overview

DockView is a **single-container Python web application** that provides a read-only browser interface for databases running in Docker.

The system has three distinct layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                             │
│  Vanilla JS SPA (no framework) + CSS Custom Properties          │
│  Progressive Web App (installable, offline shell)              │
├─────────────────────────────────────────────────────────────────┤
│  APPLICATION LAYER                                              │
│  FastAPI async REST API + Server-Sent Events                    │
│  Jinja2 for initial HTML shell render                          │
├─────────────────────────────────────────────────────────────────┤
│  DATA LAYER                                                     │
│  Docker Inspector → Adapter Registry → DB Drivers              │
│  Credential Resolver → In-memory credential cache             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Architecture

### 2.1 Docker Inspector (`app/services/docker_inspector.py`)

The core engine. Responsibilities:
- Connect to Docker socket via Python docker SDK
- List all running containers
- Identify database containers by image name pattern matching
- Extract connection info (host IP from container network, mapped port fallback)
- Extract credentials from container environment variables
- Watch Docker events (start/die/stop) and re-scan in real time

**Key design decision:** The inspector uses the container's internal Docker network IP when available, which allows DockView to connect to databases without requiring port mapping on the host. If no network IP is found, it falls back to the host-mapped port on `localhost`.

```
Docker Socket
    │
    ▼
list_containers()
    │
    ├── detect_db_type(container)       → match image name vs patterns dict
    ├── extract_credentials(container)  → parse ENV vars
    └── extract_host_port(container)    → network IP or mapped port
         │
         ▼
DetectedDatabase (Pydantic model, held in memory dict)
```

**Re-scan triggers:**
- Application startup
- Docker event: `start`, `die`, `stop`, `destroy`
- Manual refresh via `POST /api/containers/refresh`

---

### 2.2 Adapter System (`app/adapters/`)

Each supported database type has one adapter. Adapters implement the `BaseAdapter` abstract interface:

```python
class BaseAdapter:
    async def test_connection() -> bool
    async def list_databases() -> list[str]
    async def list_tables(database) -> list[TableInfo]
    async def get_columns(database, table) -> list[ColumnInfo]
    async def preview_table(database, table, limit, offset) -> TablePreview
    async def get_server_info() -> dict
```

**Registration pattern:** Adapters self-register using a decorator:

```python
@register(DatabaseType.POSTGRES)
class PostgresAdapter(BaseAdapter):
    ...
```

The `AdapterRegistry` is a simple dict mapping `DatabaseType → Adapter class`. The API layer looks up the adapter at request time.

**All database operations are async** — adapters use asyncpg (Postgres), aiomysql (MySQL), motor (Mongo), and redis.asyncio (Redis). No blocking calls.

---

### 2.3 Credential Resolver (3-tier waterfall)

```
Tier 1: Container ENV vars (auto-extracted at scan time)
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
    MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
    MONGO_INITDB_ROOT_USERNAME, MONGO_INITDB_ROOT_PASSWORD
    REDIS_PASSWORD

Tier 2: Hardcoded defaults
    Postgres: user=postgres, database=postgres
    MySQL: user=root
    (no-password fallbacks)

Tier 3: Manual input (stored in app/services/credential_cache.py)
    In-memory Python dict, keyed by container short ID
    Written via POST /api/databases/{id}/connect
    Cleared on restart
```

---

### 2.4 REST API (`app/api/`)

All API routes are under `/api/`.

| Method | Path | Description |
|---|---|---|
| GET | `/api/databases` | List all detected databases |
| GET | `/api/databases/{id}` | Get single database metadata |
| POST | `/api/databases/{id}/connect` | Test connection / save credentials |
| GET | `/api/databases/{id}/schemas` | List schemas/databases |
| GET | `/api/databases/{id}/schemas/{s}/tables` | List tables |
| GET | `/api/databases/{id}/schemas/{s}/tables/{t}/preview` | Row preview |
| GET | `/api/databases/{id}/schemas/{s}/tables/{t}/columns` | Column schema |
| GET | `/api/databases/{id}/info` | Server version info |
| GET | `/api/containers/status` | Docker connection status |
| POST | `/api/containers/refresh` | Force re-scan |
| GET | `/api/events` | SSE stream for live updates |
| GET | `/health` | Health check endpoint |

---

### 2.5 Server-Sent Events (`app/services/event_stream.py`)

The `/api/events` endpoint is a persistent HTTP connection that pushes JSON updates every 3 seconds when the database list changes.

```
Browser EventSource("/api/events")
    ←── {"count": 4, "databases": [...status updates...]}
    ←── (only when state changes)
```

The client uses this to update status dots in the sidebar without polling or page reload.

**Design choice:** SSE over WebSockets — simpler, HTTP/1.1 compatible, works through any reverse proxy without special configuration.

---

### 2.6 Frontend SPA (`app/static/js/app.js`)

Pure vanilla JavaScript — no React, no Vue, no build step. This means:
- **Zero client-side dependencies**
- **Instant load** — one JS file, one CSS file
- **Easy to read and modify**

State is held in a plain object:
```javascript
const state = {
  databases: [],       // all detected DBs
  activeDbId: null,    // selected DB
  activeSchema: null,  // selected schema
  activeTable: null,   // selected table
  page: 0,             // pagination
  preview: null,       // last fetched preview
};
```

DOM updates are surgical — specific elements are updated, not re-rendered wholesale.

**Live updates:** An `EventSource` connects to `/api/events` and updates sidebar status dots when containers start/stop.

---

## 3. Data Flow — Typical User Interaction

```
User opens http://localhost:8080
    │
    ▼
GET / → FastAPI serves index.html (Jinja2)
    │
    ▼
Browser loads app.js, main.css
    │
    ▼
GET /api/containers/status    → Docker connected? DB count?
GET /api/databases            → List of DetectedDatabase objects
    │
    ▼
Sidebar renders database list
    │
User clicks a database
    │
    ▼
GET /api/databases/{id}/schemas    → Adapter.list_databases()
    │
    ▼
Schemas render in left column. Auto-select first schema.
    │
GET /api/databases/{id}/schemas/{s}/tables    → Adapter.list_tables()
    │
    ▼
Tables render in middle column.
    │
User clicks a table
    │
    ▼
GET /api/databases/{id}/schemas/{s}/tables/{t}/preview?limit=50&offset=0
    → Adapter.preview_table()
    │
    ▼
Data table renders in right column.
GET /api/databases/{id}/schemas/{s}/tables/{t}/columns
    → Adapter.get_columns()
    │
Schema view pre-populated for Schema tab
```

---

## 4. Security Model

### What DockView can do:
- Read the Docker socket (equivalent to root access on the host)
- Connect to any database visible to it on Docker networks
- Execute `SELECT`, `SHOW`, `db.find()`, `KEYS`, and similar read commands
- Read container environment variables (which contain credentials)

### What DockView cannot do:
- Execute any write operations (INSERT, UPDATE, DELETE, DROP, etc.)
- Write files to disk (except logging)
- Accept arbitrary SQL input from users (no query interface in v1)
- Authenticate users (v1 has no auth layer)

### Attack surface:
- The HTTP port (8080) — protect with nginx auth or IP allowlist
- The Docker socket mount — use `:ro` to prevent container creation
- Credential storage — entirely in-memory, cleared on restart

### Recommendation matrix:

| Deployment | Recommended protection |
|---|---|
| Local dev, single developer | None needed |
| Team / shared dev server | nginx basic auth + IP allowlist |
| Internal production tool | nginx basic auth + TLS + IP allowlist |
| Public internet | Do not expose without full auth implementation |

---

## 5. Performance Characteristics

| Operation | Typical latency |
|---|---|
| Page load (initial) | < 200ms |
| Database list API | < 50ms (in-memory) |
| Schema list (Postgres) | 80–200ms |
| Table list (Postgres, 50 tables) | 100–300ms |
| Row preview (50 rows) | 50–200ms |
| MongoDB collection preview | 100–400ms |
| Redis key scan (1000 keys) | 200–800ms |

Row preview is limited to 50 rows by default. This can be increased but large previews will affect browser rendering performance.

---

## 6. File Structure Reference

```
dockview/
├── app/
│   ├── main.py                     # FastAPI app entry point, lifespan
│   ├── models.py                   # Pydantic data models
│   ├── api/
│   │   ├── __init__.py
│   │   ├── databases.py            # /api/databases/* routes
│   │   ├── containers.py           # /api/containers/* routes
│   │   └── schema.py               # /api/*/columns route
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py                 # Abstract BaseAdapter
│   │   ├── registry.py             # Adapter registration decorator + registry
│   │   ├── postgres.py             # PostgreSQL adapter (asyncpg)
│   │   ├── mysql.py                # MySQL adapter (aiomysql)
│   │   ├── mongo.py                # MongoDB adapter (motor)
│   │   └── redis.py                # Redis adapter (redis.asyncio)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── docker_inspector.py     # Core Docker scanning engine
│   │   ├── credential_cache.py     # In-memory credential store
│   │   └── event_stream.py         # SSE router for live updates
│   ├── templates/
│   │   └── index.html              # Main SPA shell (Jinja2)
│   └── static/
│       ├── css/
│       │   └── main.css            # All styles (CSS custom properties)
│       ├── js/
│       │   └── app.js              # SPA logic (vanilla JS)
│       ├── manifest.json           # PWA manifest
│       ├── sw.js                   # Service Worker
│       └── icons/
│           ├── icon-192.svg
│           └── icon-512.svg
├── docs/
│   ├── ARCHITECTURE.md             # This file
│   ├── DEVELOPMENT.md              # Dev setup and contribution guide
│   └── API.md                      # API reference
├── Dockerfile                      # Multi-stage production build
├── docker-compose.yml              # Full stack with demo DBs
├── requirements.txt                # Python dependencies
├── README.md                       # Project overview
├── GUIDE.md                        # Complete usage + deployment guide
├── .dockerignore
└── .gitignore
```
