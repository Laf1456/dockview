"""
PostgreSQL Adapter
Uses asyncpg for async, non-blocking connections.
"""

import asyncio
import logging

import asyncpg

from app.adapters.base import BaseAdapter
from app.adapters.registry import register
from app.models import DatabaseType, TableInfo, TablePreview, ColumnInfo

logger = logging.getLogger("dockview.adapter.postgres")


@register(DatabaseType.POSTGRES)
class PostgresAdapter(BaseAdapter):

    def _conn_params(self, database: str | None = None) -> dict:
        params = {
            "host": self.db.host,
            "port": self.db.port,
            "user": self.creds.get("user", "postgres"),
            "password": self.creds.get("password", ""),
            "database": database or self.creds.get("database", "postgres"),
            "timeout": 5,
            "command_timeout": 10,
        }
        return params

    async def test_connection(self) -> bool:
        try:
            conn = await asyncpg.connect(**self._conn_params())
            await conn.close()
            return True
        except Exception as e:
            logger.warning(f"Postgres connection test failed: {e}")
            return False

    async def list_databases(self) -> list[str]:
        conn = await asyncpg.connect(**self._conn_params())
        try:
            rows = await conn.fetch(
                "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"
            )
            return [r["datname"] for r in rows]
        finally:
            await conn.close()

    async def list_tables(self, database: str) -> list[TableInfo]:
        conn = await asyncpg.connect(**self._conn_params(database))
        try:
            rows = await conn.fetch("""
                SELECT
                    t.table_schema,
                    t.table_name,
                    t.table_type,
                    pg_size_pretty(pg_total_relation_size(
                        quote_ident(t.table_schema) || '.' || quote_ident(t.table_name)
                    )) AS size,
                    pg_total_relation_size(
                        quote_ident(t.table_schema) || '.' || quote_ident(t.table_name)
                    ) AS size_bytes,
                    (SELECT reltuples::bigint FROM pg_class c
                     JOIN pg_namespace n ON n.oid = c.relnamespace
                     WHERE c.relname = t.table_name AND n.nspname = t.table_schema
                    ) AS row_estimate
                FROM information_schema.tables t
                WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY t.table_schema, t.table_name
            """)
            return [
                TableInfo(
                    name=r["table_name"],
                    schema_name=r["table_schema"],
                    row_count=max(0, r["row_estimate"] or 0),
                    size_bytes=r["size_bytes"],
                    collection_type="view" if r["table_type"] == "VIEW" else "table",
                )
                for r in rows
            ]
        finally:
            await conn.close()

    async def get_columns(self, database: str, table: str) -> list[ColumnInfo]:
        schema = "public"
        if "." in table:
            schema, table = table.split(".", 1)

        conn = await asyncpg.connect(**self._conn_params(database))
        try:
            rows = await conn.fetch("""
                SELECT
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    EXISTS(
                        SELECT 1 FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND kcu.table_name = c.table_name
                          AND kcu.column_name = c.column_name
                    ) AS is_pk
                FROM information_schema.columns c
                WHERE c.table_name = $1 AND c.table_schema = $2
                ORDER BY c.ordinal_position
            """, table, schema)
            return [
                ColumnInfo(
                    name=r["column_name"],
                    data_type=r["data_type"],
                    nullable=r["is_nullable"] == "YES",
                    is_primary_key=r["is_pk"],
                    default=r["column_default"],
                )
                for r in rows
            ]
        finally:
            await conn.close()

    async def preview_table(
        self, database: str, table: str, limit: int = 50, offset: int = 0
    ) -> TablePreview:
        schema = "public"
        if "." in table:
            schema, table_name = table.split(".", 1)
        else:
            table_name = table

        qualified = f'"{schema}"."{table_name}"'
        conn = await asyncpg.connect(**self._conn_params(database))
        try:
            columns = await self.get_columns(database, f"{schema}.{table_name}")
            count_row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {qualified}")
            total = count_row["cnt"]

            rows = await conn.fetch(
                f"SELECT * FROM {qualified} LIMIT $1 OFFSET $2", limit, offset
            )
            return TablePreview(
                columns=columns,
                rows=[list(r.values()) for r in rows],
                total_rows=total,
                limit=limit,
                offset=offset,
                truncated=total > (offset + limit),
            )
        finally:
            await conn.close()

    async def get_server_info(self) -> dict:
        conn = await asyncpg.connect(**self._conn_params())
        try:
            row = await conn.fetchrow("SELECT version()")
            return {"version": row["version"]}
        finally:
            await conn.close()
