import os
import tempfile

# Configure BEFORE the app is imported: in-memory Mongo + throwaway Chroma dir, no AI keys.
os.environ["DB_BACKEND"] = "mock"
os.environ["CHROMA_DIR"] = tempfile.mkdtemp(prefix="chroma_test_")
os.environ["SECRET_KEY"] = "pytest-secret-key-pytest-secret-key-123"
os.environ["GOOGLE_API_KEY"] = ""
os.environ["TAVILY_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client():
    with TestClient(create_app()) as c:
        yield c


def register(client, email="a@example.com", name="Asha", password="password123"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


@pytest.fixture()
def auth(client):
    return register(client)[0]
