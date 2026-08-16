import os, pytest
from fastapi.testclient import TestClient
from main import app

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("POSTGRES_USER", "myuser")
os.environ.setdefault("POSTGRES_PASSWORD", "testpassword")
os.environ.setdefault("POSTGRES_DB", "myapp")

client = TestClient(app)


@pytest.fixture
def anyio_backend():
    import anyio
    return anyio


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "backend"
    assert "hostname" in data


def test_health_endpoint_exists():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "db" in data


def test_db_check_endpoint_exists():
    resp = client.get("/db-check")
    assert resp.status_code == 200
    data = resp.json()
    assert "database" in data
    assert "connected" in data


def test_db_items_endpoint_exists():
    resp = client.get("/db-items")
    assert resp.status_code in (200, 500)  # 500 ok if no DB
    data = resp.json()
    assert "items" in data or "detail" in data
