"""
Integration tests for KnowWhere API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "extraction_model" in data


def test_list_documents(client):
    response = client.get("/documents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_entities(client):
    response = client.get("/entities")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_relationships(client):
    response = client.get("/relationships")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_search_facts(client):
    response = client.get("/facts/search?q=Delhivery")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
