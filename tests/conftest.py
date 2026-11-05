import os
import sys
import tempfile
from pathlib import Path

# These must be set before the app is imported: the tests use a throwaway
# database, the public demo password, and never call the paid AI service.
os.environ["BUGLENS_DB"] = str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["TEAM_PASSWORD"] = "test-password"
os.environ["SECRET_KEY"] = "test-secret"
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from database import get_connection
from main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        with get_connection() as conn:
            conn.execute("DELETE FROM bugs")
        yield test_client


@pytest.fixture
def team_client(client):
    response = client.post("/api/login", json={"password": "test-password"})
    assert response.status_code == 200
    return client
