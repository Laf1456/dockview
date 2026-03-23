"""
DockView — Basic Tests
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.models import DetectedDatabase, DatabaseType


@pytest.fixture
def mock_inspector():
    inspector = MagicMock()
    inspector.is_connected = True
    inspector.error = None
    inspector.get_all_databases.return_value = [
        DetectedDatabase(
            id="abc123",
            container_id="abc123full",
            container_name="test-postgres",
            name="test-postgres",
            image="postgres:16",
            type=DatabaseType.POSTGRES,
            host="172.18.0.2",
            port=5432,
            credentials={"user": "postgres", "password": "test"},
            status="running",
        )
    ]
    inspector.get_database.return_value = inspector.get_all_databases.return_value[0]
    return inspector


@pytest.fixture
def client(mock_inspector):
    app.state.inspector = mock_inspector
    return TestClient(app)


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_list_databases(client):
    res = client.get("/api/databases")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["type"] == "postgres"
    assert data[0]["name"] == "test-postgres"


def test_get_database(client):
    res = client.get("/api/databases/abc123")
    assert res.status_code == 200
    assert res.json()["id"] == "abc123"


def test_containers_status(client):
    res = client.get("/api/containers/status")
    assert res.status_code == 200
    assert res.json()["connected"] is True


def test_root(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "DockView" in res.text


def test_docker_inspector_detect_type():
    from app.services.docker_inspector import DockerInspector
    inspector = DockerInspector()
    
    assert inspector._identify_type("postgres:16-alpine") == DatabaseType.POSTGRES
    assert inspector._identify_type("mysql:8.0") == DatabaseType.MYSQL
    assert inspector._identify_type("mongo:7.0") == DatabaseType.MONGO
    assert inspector._identify_type("redis:7.4-alpine") == DatabaseType.REDIS
    assert inspector._identify_type("nginx:latest") is None


def test_credential_extraction():
    from app.services.docker_inspector import DockerInspector
    inspector = DockerInspector()
    
    env_vars = {
        "POSTGRES_USER": "myuser",
        "POSTGRES_PASSWORD": "mypass",
        "POSTGRES_DB": "mydb",
    }
    creds = inspector._extract_credentials(DatabaseType.POSTGRES, env_vars)
    assert creds["user"] == "myuser"
    assert creds["password"] == "mypass"
    assert creds["database"] == "mydb"


def test_credential_defaults():
    from app.services.docker_inspector import DockerInspector
    inspector = DockerInspector()
    
    creds = inspector._extract_credentials(DatabaseType.POSTGRES, {})
    assert creds["user"] == "postgres"
    assert creds["database"] == "postgres"
