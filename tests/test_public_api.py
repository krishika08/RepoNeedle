"""Integration tests for the public RepoNeedle demonstration API."""

import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import api
from api import app

ROOT = Path(__file__).resolve().parent.parent
PROJECT_VERSION = re.search(
    r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M
).group(1)

# Clearly out of scope for the embedded Flask snapshot (the selective example in the Space).
OUT_OF_SCOPE_QUERY = "Fix compilation error in Cargo.toml regarding serde_json feature flag dependency in rust kernel."


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_root_discloses_demo_scope(client):
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "RepoNeedle Demo API"
    assert payload["version"] == PROJECT_VERSION
    assert "Embedded demonstration snapshots only" in payload["disclosure"]


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "reponeedle-demo-api",
        "version": PROJECT_VERSION,
    }


def test_reported_versions_come_from_the_imported_engine(client):
    assert api.ENGINE_VERSION == api.reponeedle.__version__ == PROJECT_VERSION
    assert client.get("/openapi.json").json()["info"]["version"] == PROJECT_VERSION


def test_api_imports_the_bundled_space_engine():
    """In a fresh process (as on Render), api.py must load the engine bundled in hf_artifacts/space,
    not an installed copy of the package."""
    code = (
        "import sys; sys.path.insert(0, '.');"
        "import api, reponeedle;"
        "print(reponeedle.__file__); print(reponeedle.__version__); print(api.ENGINE_VERSION)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True, timeout=120
    ).stdout.split()
    engine_file, engine_version, api_version = Path(out[-3]).resolve(), out[-2], out[-1]
    assert engine_file == (ROOT / "hf_artifacts" / "space" / "reponeedle" / "__init__.py").resolve()
    assert engine_version == api_version == PROJECT_VERSION


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


def test_requests_snapshot_retrieval(client):
    response = client.post(
        "/api/retrieve",
        json={
            "repo_name": "psf/requests",
            "ranker": "legacy",
            "task_mode": "code2test",
            "budget_tokens": 4000,
            "query": "Find test suites that verify HTTPBasicAuth headers and authentication credentials formatting.",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["repository"] == "psf/requests"
    assert payload["task_type"] == "code2test"
    assert payload["decision"] == "RETRIEVED CONTEXT"
    assert payload["selected_files"]
    assert payload["tokens_used"] <= payload["token_budget"]


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
    assert "seed-relative dependency boosts" in payload["ranker_note"].lower()
    assert payload["tokens_used"] <= payload["token_budget"]
    selected_paths = [item["path"] for item in payload["selected_files"]]
    assert selected_paths
    # Seed File Suppression should keep the seed from occupying the first result.
    assert selected_paths[0] != "src/flask/sessions.py"


def test_experimental_abstention_is_disabled_by_default(client):
    response = client.post(
        "/api/retrieve",
        json={"repo_name": "pallets/flask", "task_mode": "selective", "query": OUT_OF_SCOPE_QUERY},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["abstention"] == {
        "enabled": False,
        "status": "disabled",
        "experimental": True,
        "calibrated": False,
    }
    assert payload["abstained"] is False
    assert payload["decision"] == "RETRIEVED CONTEXT"
    assert payload["selected_files"]


def test_experimental_abstention_explicit_opt_in(client):
    response = client.post(
        "/api/retrieve",
        json={
            "repo_name": "pallets/flask",
            "task_mode": "selective",
            "query": OUT_OF_SCOPE_QUERY,
            "enable_experimental_abstention": True,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["abstention"] == {
        "enabled": True,
        "status": "evaluated",
        "experimental": True,
        "calibrated": False,
    }
    # On this toy out-of-scope query the heuristic abstains; the response must stay consistent.
    assert payload["abstained"] is True
    assert payload["decision"] == "ABSTAINED"
    assert payload["selected_files"] == []
    assert payload["tokens_used"] == 0
    assert payload["preview"] is None


def test_explicit_opt_out_matches_default(client):
    body = {"repo_name": "pallets/flask", "task_mode": "selective", "query": OUT_OF_SCOPE_QUERY}
    default = client.post("/api/retrieve", json=body).json()
    opted_out = client.post("/api/retrieve", json={**body, "enable_experimental_abstention": False}).json()
    assert opted_out["abstention"] == default["abstention"]
    assert [f["path"] for f in opted_out["selected_files"]] == [f["path"] for f in default["selected_files"]]


def test_invalid_abstention_flag_is_rejected(client):
    response = client.post(
        "/api/retrieve",
        json={"repo_name": "pallets/flask", "query": "find request handling", "enable_experimental_abstention": "maybe"},
    )
    assert response.status_code == 422


def test_internal_errors_do_not_leak_details(client, monkeypatch):
    def boom(repo_name):
        raise RuntimeError(r"C:\secret\internal\path.py exploded")

    monkeypatch.setattr(api, "get_engine", boom)
    response = client.post("/api/retrieve", json={"repo_name": "pallets/flask", "query": "find request handling"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Retrieval failed due to an internal error."}
    assert "secret" not in response.text and "RuntimeError" not in response.text


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
