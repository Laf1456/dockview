# DockView — API Reference

Base URL: `http://localhost:8080`  
Interactive docs: `http://localhost:8080/api/docs` (Swagger UI)  
ReDoc: `http://localhost:8080/api/redoc`

---

## Databases

### `GET /api/databases`

Returns all detected databases.

**Response:**
```json
[
  {
    "id": "abc12345",
    "name": "demo-postgres",
    "type": "postgres",
    "display_name": "PostgreSQL",
    "icon": "🐘",
    "color": "#4f9de0",
    "status": "running",
    "host": "172.18.0.3",
    "port": 5432,
    "container_name": "demo-postgres",
    "image": "postgres:16-alpine"
  }
]
```

---

### `GET /api/databases/{id}/schemas`

Lists schemas (logical databases) within a database.

**Response:** `["public", "app", "analytics"]`

---

### `GET /api/databases/{id}/schemas/{schema}/tables`

Lists tables in a schema.

**Response:**
```json
[
  {
    "name": "users",
    "row_count": 15234,
    "size_bytes": 2097152,
    "schema_name": "public",
    "collection_type": "table"
  }
]
```

---

### `GET /api/databases/{id}/schemas/{schema}/tables/{table}/preview`

Returns row data preview.

**Query params:**
- `limit` (int, default 50) — rows to return
- `offset` (int, default 0) — rows to skip

**Response:**
```json
{
  "columns": [
    { "name": "id", "data_type": "integer", "nullable": false, "is_primary_key": true, "default": null }
  ],
  "rows": [[1, "alice@example.com", "2024-01-15"]],
  "total_rows": 15234,
  "limit": 50,
  "offset": 0,
  "truncated": true
}
```

---

### `GET /api/databases/{id}/schemas/{schema}/tables/{table}/columns`

Returns column-level schema.

---

### `POST /api/databases/{id}/connect`

Test connection and optionally save credential overrides.

**Body (optional):**
```json
{
  "user": "myuser",
  "password": "mypassword",
  "database": "mydb",
  "host": "localhost",
  "port": 5432
}
```

**Response:** `{ "connected": true, "db_id": "abc12345" }`

---

### `GET /api/databases/{id}/info`

Returns server version metadata.

**Response:**
```json
{ "version": "PostgreSQL 16.1 on x86_64-pc-linux-musl" }
```

---

## Containers

### `GET /api/containers/status`

Returns Docker connection health.

```json
{ "connected": true, "error": null, "db_count": 4 }
```

### `POST /api/containers/refresh`

Force re-scan of all containers.

---

## Events

### `GET /api/events`

Server-Sent Events stream. Pushes updates when container state changes.

**Event format:**
```
data: {"count": 4, "databases": [{"id": "abc", "name": "demo-pg", "type": "postgres", "status": "running"}]}
```

Connect with JavaScript: `new EventSource('/api/events')`

---

## Health

### `GET /health`

```json
{ "status": "ok", "version": "1.0.0" }
```
