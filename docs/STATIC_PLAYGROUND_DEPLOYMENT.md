# RepoNeedle 1.2.0 public demo deployment

This document describes the public demo deployment. It does not change the installation path for the core Python package (`pip install reponeedle`).

## Components

| Component | Location | Purpose |
|---|---|---|
| Core engine | `reponeedle/` | CPU-first retrieval library and CLI |
| Static frontend | `hf_artifacts/static_space/` | Browser UI hosted by a Hugging Face **Static** Space |
| Demo API | `api.py` | FastAPI wrapper exposing retrieval for the embedded demo corpora (hosted on Render) |
| Demo snapshots and bundled engine | `hf_artifacts/space/` | Small Flask and Requests snapshots (`app.py`) and the bundled `reponeedle` package used by the API and the Gradio Space |
| Gradio Space | `hf_artifacts/space/` | Self-contained Gradio Playground that runs the bundled engine in-process |
| Dataset | `hf_artifacts/dataset/` | Lightweight synthetic demonstration benchmark (unchanged in 1.2.0) |

### Hugging Face repositories

| Repository | Type | Source in this repository |
|---|---|---|
| `Krishikax/RepoNeedle-Playground` | Space, **static** SDK (frontend) | README badge; `hf_artifacts/static_space/` |
| `RepoNeedle/RepoNeedle-Playground` | Space, **Gradio** SDK | README badge; default target of `scripts/prepare_hf_release.py` (`--org RepoNeedle`) |
| `RepoNeedle/RepoNeedle-Bench` | Dataset | README badge; `hf_artifacts/dataset/`; default target of `scripts/prepare_hf_release.py` |

Both Spaces are named `RepoNeedle-Playground` but live in different namespaces and use different SDKs. Never publish one directory to the other's repository.

### How the pieces fit together

```
Static Space (index.html) ──HTTPS──► Render API (api.py) ──imports──► hf_artifacts/space/reponeedle (bundled engine)
                                                         └─imports──► hf_artifacts/space/app.py (embedded Flask/Requests snapshots)
Gradio Space (app.py) ──in-process──► hf_artifacts/space/reponeedle (bundled engine)
```

- The static Space runs no Python. It calls the API URL shown in its **Backend API URL** field (default `https://reponeedle.onrender.com`).
- `api.py` puts `hf_artifacts/space/` first on `sys.path`, so it runs the **bundled** engine, not the copy that `requirements-api.txt` installs from the repository root.
- The bundled engine is an exact copy of `reponeedle/` **except** the optional `reponeedle/mcp/` package, which the demo does not need. `tests/test_hf_space_bundle.py` fails if the two diverge, and `scripts/prepare_hf_release.py` refuses to publish a diverged bundle. After changing `reponeedle/`, copy the changed files into `hf_artifacts/space/reponeedle/`.
- The API's reported version is read from the imported engine's `reponeedle.__version__`, so it always reflects the code actually running.

## Deployment sequence for 1.2.0

The order is API first, then the frontends. The 1.2.0 static UI also works against a 1.1.0 API: the older API ignores the new opt-in field, and its heuristic is always on.

1. **Merge to `main`** once CI passes.
2. **Render API.** Render builds from `main`. If auto-deploy is enabled for the service, merging starts a deploy; otherwise start a manual deploy in the Render dashboard. Then verify:
   - `GET https://YOUR-SERVICE.onrender.com/health` returns `{"status":"ok","service":"reponeedle-demo-api","version":"1.2.0"}`;
   - `GET /` reports `"version": "1.2.0"`.
3. **Static Space.** Upload `README.md` and `index.html` from `hf_artifacts/static_space/` to the static Space root. This is a manual step; the release script does not publish the static Space. Verify that the page shows `PLAYGROUND · V1.2.0` and that **Connect API** reports `Connected · RepoNeedle API 1.2.0`.
4. **Gradio Space** (if it is maintained). Run the preflight, then publish the Space only:
   ```bash
   python scripts/prepare_hf_release.py --check-only --space-only --org <namespace>
   python scripts/prepare_hf_release.py --space-only --org <namespace>
   ```
   - `--space-only` does not upload the dataset.
   - The script checks that the bundled engine matches the root package and `pyproject.toml`, never prints the token, and verifies that the Space's head is the uploaded commit.
   - It refuses to upload into an existing Space whose SDK is not `gradio`, such as the static frontend Space. The Gradio and static Spaces must be different repositories.
   - The Space installs Gradio `sdk_version` 4.29.0 from its README front matter. `requirements.txt` pins `fastapi<0.113`, which keeps Starlette at 0.38.x: Gradio 4.x cannot serve its page with Starlette 1.x.
5. **Dataset.** No upload is needed; the demonstration dataset is unchanged in 1.2.0.

Do not describe a remote Space or API as upgraded until its live version has been checked as above.

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
{"status":"ok","service":"reponeedle-demo-api","version":"1.2.0"}
```

## Deploy the frontend on Hugging Face

Create a public Static Space. Upload the contents of `hf_artifacts/static_space/` to the Space root. The `README.md` front matter must retain `sdk: static`.

The UI defaults to `https://reponeedle.onrender.com`. Users can change the Backend API URL field and click **Connect API** to use another deployment.

## API contract

- `GET /` returns service metadata (including `version`) and a scope disclosure.
- `GET /health` is the health check: `{"status": "ok", "service": "reponeedle-demo-api", "version": "<engine version>"}`.
- `POST /api/retrieve` accepts:
  - `repo_name`, `ranker`, `task_mode`, `budget_tokens`, `seed_files` and `query`;
  - optional `enable_experimental_abstention` (boolean, default `false`), new in 1.2.0.
- Response fields are unchanged from 1.1.0, plus an additive `abstention` object: `{"enabled", "status", "experimental": true, "calibrated": false}`. `status` is `"disabled"` by default and `"evaluated"` when opted in.
- Supported demo repositories: `pallets/flask`, `psf/requests`.
- Supported rankers: `legacy` (default), `change_impact`.
- The API validates query length, budget limits, repository choice, seed count and the abstention flag type using Pydantic.
- Internal errors return HTTP 500 with a generic message. Exception details are written to the server log only and are never returned to callers.

## Experimental abstention (1.2.0 default: off)

- In 1.2.0 the out-of-scope abstention heuristic is **disabled by default**. The API, the static UI and the Gradio Space return ranked context for every query unless the caller opts in.
- The static UI and the Gradio Space have an unchecked **Experimental abstention** control.
- Choosing the `selective` task does not enable abstention.
- The heuristic is experimental and **uncalibrated**: on the ARB v2 selective split it correctly abstained on 0 of 82 out-of-scope queries. An abstention on a demo query is a diagnostic, not a reliable out-of-scope signal. See `KNOWN_LIMITATIONS.md`.
- In 1.1.0 (the previous demo) the heuristic was always on.

## Limitations and security boundaries

- This is a public, unauthenticated demonstration API. Do not send secrets, proprietary source code, or personal data.
- CORS is open so the public Hugging Face frontend can call the API. This is not an authentication or abuse-prevention control.
- The API only retrieves from the two embedded demonstration snapshots. It does not index arbitrary repositories or expose a general upload endpoint.
- The demos rank in-memory documents (`RepoNeedleEngine.from_documents`). They do not index a directory, so they do not exercise 1.2.0's filesystem indexing safeguards (link containment, directory-link traversal limits) or show indexing diagnostics.
- The API does not persist visitor queries. Its in-memory caches reset when the service restarts.
- Free hosting may sleep after inactivity and has limited CPU/RAM. Cold starts and request latency can vary.
- The dataset is a small synthetic demo dataset, not the complete Agent Retrieval Bench v2 corpus.
- Demo results are not benchmark results; see the README for the documented evaluations and their qualifications.

## Local development and tests

Install the package and development/API test extras:

```bash
pip install -e ".[dev,api]"
pytest -q
```

- The API tests (`tests/test_public_api.py`) use FastAPI's `TestClient` and the demo corpora shipped with the repository.
- `tests/test_hf_space_bundle.py` checks the bundled engine against the root package and smoke-tests the Gradio app without Gradio installed.
- It also checks the release script's safeguards using a fake Hub client, so nothing is uploaded.
