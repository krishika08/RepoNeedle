"""Integration tests for the public RepoNeedle demonstration API."""

import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_root_discloses_demo_scope(client):
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "RepoNeedle Demo API"
    assert payload["version"] == "1.1.0"
    assert "Embedded demonstration snapshots only" in payload["disclosure"]


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "reponeedle-demo-api",
        "version": "1.1.0",
    }


def test_legacy_retrieval_contract(client):
    response = client.post(
        "/api/retrieve",
        json={
            "repo_name": "pallets/flask",
            "ranker": "legacy",
            "task_mode": "auto",
            "budget_tokens": 4000,
            "query": "Find the implementation of Flask request dispatching and related tests.",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ranker"] == "legacy"
    assert payload["task_type"] in {"comment2context", "code2test", "edit2ripple", "trace2code"}
    assert payload["tokens_used"] <= payload["token_budget"]
    assert isinstance(payload["selected_files"], list)
    assert isinstance(payload["comparison"], list)
    assert payload["preview"] is None or "content" in payload["preview"]


def test_change_impact_auto_infers_task_from_seed(client):
    response = client.post(
        "/api/retrieve",
        json={
            "repo_name": "pallets/flask",
            "ranker": "change_impact",
            "task_mode": "auto",
            "budget_tokens": 4000,
            "seed_files": ["src/flask/sessions.py"],
            "query": "Fix cookie attribute handling during session modification in SecureCookieSessionInterface.",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ranker"] == "change_impact"
    assert payload["task_type"] == "edit2ripple"
    assert "seed-relative dependency boosts" in payload["ranker_note"]
    assert payload["tokens_used"] <= payload["token_budget"]
    selected_paths = [item["path"] for item in payload["selected_files"]]
    assert selected_paths
    # Seed File Suppression should keep the seed from occupying the first result.
    assert selected_paths[0] != "src/flask/sessions.py"


def test_invalid_repository_is_rejected(client):
    response = client.post(
        "/api/retrieve",
        json={"repo_name": "unknown/repository", "query": "find request handling"},
    )
    assert response.status_code == 422


def test_out_of_range_budget_is_rejected(client):
    response = client.post(
        "/api/retrieve",
        json={"repo_name": "pallets/flask", "budget_tokens": 100, "query": "find request handling"},
    )
    assert response.status_code == 422


def test_cors_preflight_is_available(client):
    response = client.options(
        "/api/retrieve",
        headers={
            "Origin": "https://krishikax-reponeedle-playground.hf.space",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"
