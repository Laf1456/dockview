"""
MySQL / MariaDB Adapter
Uses aiomysql for async connections.
"""

import logging
import aiomysql

from app.adapters.base import BaseAdapter
from app.adapters.registry import register
from app.models import DatabaseType, TableInfo, TablePreview, ColumnInfo

logger = logging.getLogger("dockview.adapter.mysql")


@register(DatabaseType.MYSQL)
class MySQLAdapter(BaseAdapter):

    def _conn_params(self, database: str | None = None) -> dict:
        return {
            "host": self.db.host,
            "port": self.db.port,
            "user": self.creds.get("user", "root"),
            "password": self.creds.get("password", ""),
            "db": database or self.creds.get("database") or None,
            "connect_timeout": 5,
            "autocommit": True,
        }

    async def _get_conn(self, database: str | None = None):
        return await aiomysql.connect(**self._conn_params(database))

    async def test_connection(self) -> bool:
        try:
            conn = await self._get_conn()
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"MySQL connection test failed: {e}")
            return False

    async def list_databases(self) -> list[str]:
        conn = await self._get_conn()
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys') "
                    "ORDER BY schema_name"
                )
                return [r[0] for r in await cur.fetchall()]
        finally:
            conn.close()

    async def list_tables(self, database: str) -> list[TableInfo]:
        conn = await self._get_conn(database)
        try:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT
                        table_name,
                        table_type,
                        table_rows,
                        data_length + index_length AS size_bytes
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    ORDER BY table_name
                """, (database,))
                return [
                    TableInfo(
                        name=r[0],
                        collection_type="view" if r[1] == "VIEW" else "table",
                        row_count=r[2] or 0,
                        size_bytes=r[3] or 0,
                        schema_name=database,
                    )
                    for r in await cur.fetchall()
                ]
        finally:
            conn.close()

    async def get_columns(self, database: str, table: str) -> list[ColumnInfo]:
        conn = await self._get_conn(database)
        try:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default, column_key
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """, (database, table))
                return [
                    ColumnInfo(
                        name=r[0],
                        data_type=r[1],
                        nullable=r[2] == "YES",
                        default=r[3],
                        is_primary_key=r[4] == "PRI",
                    )
                    for r in await cur.fetchall()
                ]
        finally:
            conn.close()

    async def preview_table(
        self, database: str, table: str, limit: int = 50, offset: int = 0
    ) -> TablePreview:
        conn = await self._get_conn(database)
        try:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT COUNT(*) FROM `{table}`")
                total = (await cur.fetchone())[0]

                await cur.execute(
                    f"SELECT * FROM `{table}` LIMIT %s OFFSET %s", (limit, offset)
                )
                rows = await cur.fetchall()
                columns = await self.get_columns(database, table)

                return TablePreview(
                    columns=columns,
                    rows=[list(r) for r in rows],
                    total_rows=total,
                    limit=limit,
                    offset=offset,
                    truncated=total > (offset + limit),
                )
        finally:
            conn.close()

    async def get_server_info(self) -> dict:
        conn = await self._get_conn()
        try:
            async with conn.cursor() as cur:
                await cur.execute("SELECT VERSION()")
                row = await cur.fetchone()
                return {"version": row[0]}
        finally:
            conn.close()
