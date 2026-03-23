"""
Base Adapter — abstract interface all DB adapters must implement.
"""

from abc import ABC, abstractmethod
from app.models import DetectedDatabase, TableInfo, TablePreview, ColumnInfo


class BaseAdapter(ABC):
    def __init__(self, db: DetectedDatabase, credential_override: dict | None = None):
        self.db = db
        self.creds = {**db.credentials, **(credential_override or {})}

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if connection is possible."""
        ...

    @abstractmethod
    async def list_databases(self) -> list[str]:
        """Return list of database/schema names."""
        ...

    @abstractmethod
    async def list_tables(self, database: str) -> list[TableInfo]:
        """Return tables/collections in a database."""
        ...

    @abstractmethod
    async def get_columns(self, database: str, table: str) -> list[ColumnInfo]:
        """Return column metadata for a table."""
        ...

    @abstractmethod
    async def preview_table(
        self, database: str, table: str, limit: int = 50, offset: int = 0
    ) -> TablePreview:
        """Return a preview of rows from a table."""
        ...

    @abstractmethod
    async def get_server_info(self) -> dict:
        """Return server version and metadata."""
        ...
