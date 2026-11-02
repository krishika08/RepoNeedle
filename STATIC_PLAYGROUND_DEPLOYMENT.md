# RepoNeedle V1.1.0 public demo deployment

This document describes the public demo deployment. It does not change the installation path for the core Python package.

## Components

| Component | Location | Purpose |
|---|---|---|
| Core engine | `reponeedle/` | CPU-first retrieval library and CLI |
| Static frontend | `hf_artifacts/static_space/` | Browser UI hosted by Hugging Face Static Spaces |
| Demo API | `api.py` | FastAPI wrapper exposing retrieval for the embedded demo corpora |
| Demo snapshots and bundled UI engine | `hf_artifacts/space/` | Small Flask and Requests snapshots and synchronized RepoNeedle package used by the API |
| Dataset | `hf_artifacts/dataset/` | Lightweight synthetic demonstration benchmark |

## Deploy the API on Render

Create a Web Service connected to this repository and use:

- Runtime: Python 3
- Branch: `main`
- Root directory: repository root (blank)
- Build command: `pip install -r requirements-api.txt`
- Start command: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`
- Instance: Free (optional; subject to provider limits)

The API imports the embedded corpora and engine from `hf_artifacts/space/`. Do not remove that directory while deploying this backend.

Verify `https://YOUR-SERVICE.onrender.com/health`. A healthy response is:

```json
{"status":"ok","service":"reponeedle-demo-api","version":"1.1.0"}
```

## Deploy the frontend on Hugging Face

Create a public Static Space. Upload the contents of `hf_artifacts/static_space/` to the Space root. The `README.md` front matter must retain `sdk: static`.

The UI defaults to `https://reponeedle.onrender.com`. Users can change the Backend API URL field and click **Connect API** to use another deployment.

## API contract

- `GET /` returns service metadata and a scope disclosure.
- `GET /health` is the health check.
- `POST /api/retrieve` accepts `repo_name`, `ranker`, `task_mode`, `budget_tokens`, `seed_files`, and `query`.
- Supported demo repositories: `pallets/flask`, `psf/requests`.
- Supported rankers: `legacy` (default), `change_impact`.
- The API validates query length, budget limits, repository choice, and seed count using Pydantic.

## Limitations and security boundaries

- This is a public, unauthenticated demonstration API. Do not send secrets, proprietary source code, or personal data.
- CORS is open so the public Hugging Face frontend can call the API. This is not an authentication or abuse-prevention control.
- The API only retrieves from the two embedded demonstration snapshots. It does not index arbitrary repositories or expose a general upload endpoint.
- The API does not persist visitor queries. Its in-memory caches reset when the service restarts.
- Free hosting may sleep after inactivity and has limited CPU/RAM. Cold starts and request latency can vary.
- The dataset is a small synthetic demo dataset, not the complete Agent Retrieval Bench v2 corpus.
- Selective abstention is experimental and should not be presented as reliable; see `KNOWN_LIMITATIONS.md`.

## Local development and tests

Install the package and development/API test extras:

```bash
pip install -e ".[dev,api]"
pytest -q
```

The API tests use FastAPI's `TestClient` and the public-demo corpus shipped with the repository.
