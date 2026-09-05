from __future__ import annotations

import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["FRONTEND_BASE_URL"] = "http://localhost:3000"
os.environ["SEED_DEMO_CONTENT"] = "true"
os.environ["SECRET_KEY"] = "breachsim-test-signing-key-32-bytes-minimum"
os.environ["AI_PROVIDER"] = "rule_based"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-BreachSim-API-Client": "bearer"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(client: TestClient) -> dict[str, str]:
    return login(client, "admin@breachsim-lab.com", "Admin123!")


@pytest.fixture()
def manager_headers(client: TestClient) -> dict[str, str]:
    return login(client, "manager@breachsim-lab.com", "Manager123!")


@pytest.fixture()
def auditor_headers(client: TestClient) -> dict[str, str]:
    return login(client, "auditor@breachsim-lab.com", "Auditor123!")
