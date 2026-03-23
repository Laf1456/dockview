"""
MongoDB Adapter
Uses motor (async pymongo wrapper).
"""

import logging
from typing import Any

import motor.motor_asyncio

from app.adapters.base import BaseAdapter
from app.adapters.registry import register
from app.models import DatabaseType, TableInfo, TablePreview, ColumnInfo

logger = logging.getLogger("dockview.adapter.mongo")

SYSTEM_DBS = {"admin", "config", "local"}


@register(DatabaseType.MONGO)
class MongoAdapter(BaseAdapter):

    def _uri(self) -> str:
        user = self.creds.get("user")
        password = self.creds.get("password")
        host = self.db.host
        port = self.db.port

        if user and password:
            return f"mongodb://{user}:{password}@{host}:{port}/?authSource=admin&serverSelectionTimeoutMS=5000"
        return f"mongodb://{host}:{port}/?serverSelectionTimeoutMS=5000"

    def _client(self):
        return motor.motor_asyncio.AsyncIOMotorClient(self._uri())

    async def test_connection(self) -> bool:
        try:
            client = self._client()
            await client.admin.command("ping")
            client.close()
            return True
        except Exception as e:
            logger.warning(f"Mongo connection failed: {e}")
            return False

    async def list_databases(self) -> list[str]:
        client = self._client()
        try:
            dbs = await client.list_database_names()
            return [d for d in dbs if d not in SYSTEM_DBS]
        finally:
            client.close()

    async def list_tables(self, database: str) -> list[TableInfo]:
        client = self._client()
        try:
            db = client[database]
            collections = await db.list_collection_names()
            result = []
            for name in collections:
                try:
                    stats = await db.command("collStats", name)
                    count = stats.get("count", 0)
                    size = stats.get("storageSize", 0)
                except Exception:
                    count, size = None, None
                result.append(
                    TableInfo(
                        name=name,
                        row_count=count,
                        size_bytes=size,
                        collection_type="collection",
                    )
                )
            return result
        finally:
            client.close()

    async def get_columns(self, database: str, table: str) -> list[ColumnInfo]:
        """MongoDB is schema-less; infer from a sample document."""
        client = self._client()
        try:
            db = client[database]
            doc = await db[table].find_one()
            if not doc:
                return []
            return [
                ColumnInfo(
                    name=k,
                    data_type=type(v).__name__,
                    nullable=True,
                    is_primary_key=(k == "_id"),
                )
                for k, v in doc.items()
            ]
        finally:
            client.close()

    async def preview_table(
        self, database: str, table: str, limit: int = 50, offset: int = 0
    ) -> TablePreview:
        client = self._client()
        try:
            db = client[database]
            total = await db[table].count_documents({})
            cursor = db[table].find().skip(offset).limit(limit)
            docs = await cursor.to_list(length=limit)

            if not docs:
                return TablePreview(columns=[], rows=[], total_rows=0, limit=limit, offset=offset)

            # Build columns from all keys across sample
            keys: list[str] = []
            for doc in docs:
                for k in doc.keys():
                    if k not in keys:
                        keys.append(k)

            columns = [
                ColumnInfo(
                    name=k,
                    data_type="mixed",
                    nullable=True,
                    is_primary_key=(k == "_id"),
                )
                for k in keys
            ]

            rows = [[str(doc.get(k, "")) for k in keys] for doc in docs]

            return TablePreview(
                columns=columns,
                rows=rows,
                total_rows=total,
                limit=limit,
                offset=offset,
                truncated=total > (offset + limit),
            )
        finally:
            client.close()

    async def get_server_info(self) -> dict:
        client = self._client()
        try:
            info = await client.admin.command("buildInfo")
            return {"version": info.get("version", "unknown")}
        finally:
            client.close()
