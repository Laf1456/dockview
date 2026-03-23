"""
DockView — Core Data Models
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class DatabaseType(str, Enum):
    POSTGRES = "postgres"
    MYSQL = "mysql"
    MONGO = "mongo"
    REDIS = "redis"
    SQLITE = "sqlite"


DB_DISPLAY_NAMES = {
    DatabaseType.POSTGRES: "PostgreSQL",
    DatabaseType.MYSQL: "MySQL / MariaDB",
    DatabaseType.MONGO: "MongoDB",
    DatabaseType.REDIS: "Redis",
    DatabaseType.SQLITE: "SQLite",
}

DB_COLORS = {
    DatabaseType.POSTGRES: "#336791",
    DatabaseType.MYSQL: "#f29111",
    DatabaseType.MONGO: "#47a248",
    DatabaseType.REDIS: "#dc382d",
    DatabaseType.SQLITE: "#003b57",
}

DB_ICONS = {
    DatabaseType.POSTGRES: "🐘",
    DatabaseType.MYSQL: "🐬",
    DatabaseType.MONGO: "🍃",
    DatabaseType.REDIS: "⚡",
    DatabaseType.SQLITE: "🗃️",
}


class DetectedDatabase(BaseModel):
    id: str
    container_id: str
    container_name: str
    name: str
    image: str
    type: DatabaseType
    host: str
    port: int
    credentials: dict[str, str] = Field(default_factory=dict)
    status: str = "running"
    env_vars: dict[str, str] = Field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return DB_DISPLAY_NAMES.get(self.type, self.type.value)

    @property
    def color(self) -> str:
        return DB_COLORS.get(self.type, "#888")

    @property
    def icon(self) -> str:
        return DB_ICONS.get(self.type, "🗄️")


class TableInfo(BaseModel):
    name: str
    row_count: int | None = None
    size_bytes: int | None = None
    schema_name: str | None = None
    collection_type: str | None = None  # "table" | "view" | "collection"


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False
    default: str | None = None


class TablePreview(BaseModel):
    columns: list[ColumnInfo]
    rows: list[list[Any]]
    total_rows: int | None = None
    limit: int = 50
    offset: int = 0
    truncated: bool = False


class DatabaseMeta(BaseModel):
    id: str
    name: str
    type: DatabaseType
    display_name: str
    icon: str
    color: str
    status: str
    host: str
    port: int
    container_name: str
    image: str


class CredentialInput(BaseModel):
    user: str | None = None
    password: str | None = None
    database: str | None = None
    host: str | None = None
    port: int | None = None
