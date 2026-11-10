# RepoNeedle 1.2.0 Release-Readiness Audit

**Date**: 2026-11-10 · **Branch**: `feat/cli-json-anchor-support` (base: `main` @ `82d7fb3`, package version 1.1.0) · **Scope**: audit only. No production code, version, benchmark result or release artifact was changed.

## Verdict: **READY AFTER MINOR CORRECTIONS**

The new features work as designed in clean installs (Python 3.11 base, Python 3.12 with MCP), packaging is clean, and claims are properly separated. Three corrections are required before the version bump (§10): one security hardening in indexing, one regression against the published 1.1.0 wheel, and documentation fixes.

---

## 1. Scope inspected

Cumulative change vs 1.1.0: 23 tracked files changed (+1,086 / −229), plus new files. Production package changes: `reponeedle/__init__.py`, `cli.py`, `core/abstention.py` (docstrings only; executable code AST-identical to 1.1.0), `engine.py`, `models.py`, new `reponeedle/mcp/` (5 modules), and `pyproject.toml` (new `mcp` extra and `reponeedle-mcp` script). `reponeedle/` is byte-identical to its state at the start of Milestone 2A, so Milestones 2A–2C changed no production code.

## 2. Product feature audit (clean installs from the built wheel)

| Feature | Result |
| :--- | :--- |
| CLI `--json` produces one valid JSON document; stderr empty when nothing is skipped | PASS |
| Diagnostics never contaminate JSON stdout (skip warning on stderr only; no file contents) | PASS |
| CLI anchors: valid anchor accepted; `../` traversal, absolute outside path and missing file rejected with exit 1, error on stderr, empty stdout | PASS |
| API anchors (`Query.anchor_files`, `retrieve(anchor_files=...)` with path normalisation) | PASS |
| MCP registers exactly `reponeedle_retrieve`, `reponeedle_change_impact`, `reponeedle_inspect` with the intended arguments; abstention argument defaults to `false` | PASS |
| MCP tool path arguments reject traversal and outside absolute paths | PASS |
| MCP optional: base install works; `reponeedle-mcp` without the extra prints the install hint and exits 1 with no traceback | PASS |
| Experimental abstention disabled by default (API, CLI, MCP); opt-in via `BudgetConfig`, per-call argument, `--enable-experimental-abstention`, MCP argument | PASS |
| `max_file_size_bytes` limit, rejection of 0 / negative values, `indexing_diagnostics` (API), `indexing` (CLI JSON), `reponeedle_inspect` (MCP) | PASS |
| Existing API backward compatibility (1.1.0 call signatures, all 1.1.0 `RetrievalResult` fields) | PASS |

Results: **35 / 35** checks (Python 3.11.9, base wheel, `mcp` absent) and **45 / 45** checks (Python 3.12.10, wheel + `[mcp]`, `mcp` 1.30.0, live STDIO JSON-RPC session). Console-script `.exe` launchers could not be executed on this machine (Windows Application Control); the same entry points were exercised via `python -m`.

## 3. Backward compatibility

| Change | Compatible? | Notes |
| :--- | :--- | :--- |
| New `retrieve()` keywords (`anchor_files`, `enable_experimental_abstention`), new `from_directory(max_file_size_bytes=...)` | Yes | Appended keywords with defaults |
| New optional `RetrievalResult.abstention`, new `IndexingDiagnostics` | Yes | Additive |
| **Abstention default: always on → off** | **Behaviour change** | Out-of-scope queries now return results instead of abstaining. Restore 1.1.0 behaviour with `BudgetConfig(enable_experimental_abstention=True)` or `--enable-experimental-abstention`. Empty repositories still abstain |
| New stderr `WARNING` (logger `reponeedle.engine`) when files are skipped | Mostly | New output on stderr for library users when files exceed the size limit |
| `api` extra (present in published 1.1.0, absent from this source) | **Breaking for `pip install reponeedle[api]`** | pip will warn that the extra does not exist. It only installed `fastapi`, `httpx`, `uvicorn`; no package code used them |
| `change_impact` task label for `AUTO` queries | **Regression vs published 1.1.0** | See §10, B2 |

## 4. Security and path validation

| Finding | Severity | Status |
| :--- | :--- | :--- |
| **Indexing follows file symlinks without a root check.** `from_directory` uses `os.walk` (symlinked directories are not descended) but opens symlinked files, so a file inside the repository that links outside it (e.g. `docs/notes.md → ~/.aws/credentials`) is indexed and its contents can be returned via `rendered_context` and the MCP `reponeedle_retrieve` tool. Pre-existing behaviour, but the new MCP server exposes it to agents working on untrusted clones. Verified by code inspection (symlinks cannot be created in this Windows environment). | **Medium** | **Blocker B1** |
| `docs/MCP_INTEGRATION.md` "Symlink Escape Prevention" applies only to tool path arguments, not to indexing | Medium (documentation accuracy) | Part of B1 |
| MCP tool paths use `realpath` and reject traversal and escapes (tested live) | — | OK |
| CLI anchors use `normpath`, not `realpath` (a symlinked anchor could point outside). Anchors are only matched as names and never read | Low | Optional |
| `relpath(...).startswith("..")` also rejects legitimate names beginning with `..` (e.g. `..cache/x`) | Low (false positive) | Optional |
| No `print()` in the package outside the CLI output path; MCP STDIO and JSON stdout stay clean | — | OK |
| The MCP symlink-escape test has never run: it is skipped on Windows, and CI does not install `mcp` | Medium (test gap) | S1 |

## 5. Packaging and dependencies

- Runtime dependencies unchanged from 1.1.0 (`numpy`, `scipy`, `networkx`, `pydantic`, `pathspec`, `rich`, `tomli` on < 3.11). `mcp>=1.28,<2` is optional.
- Python ≥ 3.10: every package module parses with the 3.10 grammar; `tomllib` has a `tomli` fallback; CI matrix covers 3.10–3.12; clean installs verified on 3.11 and 3.12 (3.10 not available locally).
- Console scripts: `reponeedle = reponeedle.cli:main`, `reponeedle-mcp = reponeedle.mcp.server:main`.
- Metadata 2.4, `License-Expression: MIT`; `twine check --strict` PASSED for wheel and sdist.
- **Provenance**: the published PyPI 1.1.0 wheel was not built exactly from this repository's 1.1.0 source. It declares the extra `api`, and its `engine.py` contains a 4-line change absent from `main`. The other 17 modules are byte-identical. 1.2.0 should be built only by the release workflow from the tagged commit.
- `pytest-asyncio` (needed by 4 test files) is not declared in any extra.

## 6. Test suite

`python -m pytest -q -rs`: **446 passed, 1 skipped** (`tests/test_mcp_server.py:121`, symlink creation not permitted on Windows). In CI, which installs only `.[dev]`, the MCP tests in 5 files are skipped via `importorskip("mcp")`.

## 7. Clean installs

See §2: base wheel (3.11) 35/35; wheel + `[mcp]` (3.12) 45/45.

## 8. Wheel and sdist contents

- **Wheel** (83 KB): `reponeedle/` (including all 5 `reponeedle/mcp/` modules) and `reponeedle-1.1.0.dist-info/` only. No tests, benchmarks, research, reports, external data, scratch files, `.pyc` or `__pycache__`.
- **sdist** (189 KB, 95 files): package, `tests/`, README, LICENSE, `pyproject.toml`, `setup.cfg`, egg-info. No research, reports, benchmarks or external data. Some included tests import `benchmarks/` modules that are not shipped, so the sdist test suite is not self-contained (acceptable; not a supported workflow).

## 9. Documentation and claims

| Check | Result |
| :--- | :--- |
| Historical ARB results labelled with engine provenance (commit `8e00425`, 2026-10-28) | OK |
| Current-engine official-harness results, supplemental (Part G), Phase 2 and Phase 3 kept separate and labelled experimental / not official | OK |
| No claim that the documentation filter or lexical changes are validated | OK |
| No conversational-retrieval claim based on ARB v2 | OK in README / MCP docs. **`KNOWN_LIMITATIONS.md` §4 "Root Cause" is inaccurate** (see B3) |
| Abstention behaviour change documented (README warning, KNOWN_LIMITATIONS, MCP guide) | OK |
| Pre-release wording ("planned for 1.2.0", "unreleased", "MCP from source only", "PyPI installs 1.1.0") | 18 lines in 7 files must be updated at the bump (README, KNOWN_LIMITATIONS, CLAIMS_AND_EVIDENCE, docs/MCP_INTEGRATION, docs/ROADMAP, docs/BENCHMARK_CONFIGURATION, docs/ANNOUNCEMENT) |
| CHANGELOG | None in repository; proposal in `PROPOSED_CHANGELOG_1.2.0.md` |
| Hugging Face Space bundles the 1.1.0 engine (abstention always on) | Out of scope for the package; update separately after release |

## 10. Remaining blockers and smallest corrections

**Must fix before the version bump**

- **B1, indexing symlink escape.** In `RepoNeedleEngine.from_directory`, skip any file whose `os.path.realpath` lies outside `os.path.realpath(repo_dir)`, record it in `IndexingDiagnostics` (e.g. `skipped_outside_root`), and add a Linux-run test. Narrow the MCP doc claim to what is enforced. Roughly 10 lines plus a test.
- **B2, regression vs published 1.1.0.** Port the published `engine.py` change into the `change_impact` branch of `retrieve()`:
  ```python
  if query_obj.task_type == TaskType.AUTO:
      inferred_task, _ = self.router.classify_intent(query_obj)
  else:
      inferred_task = query_obj.task_type
  ```
  It affects the reported `task_type` for `change_impact` results, not the ranking. Add a test.
- **B3, documentation accuracy.** Rewrite `KNOWN_LIMITATIONS.md` §4 "Root Cause": the queries are structured JSON PR review contexts, the weights are 0.40 / 0.40 / 0.20 with a zero structural term, the "BM25 ≥ 0.85" mitigation is contradicted by Phases 0 and 3, and the identified cause is query term frequency handling (Phase 3). Fix the matching "conversational issue comments" phrasing in `CLAIMS_AND_EVIDENCE.md` §3.

**Should fix (not blocking)**

- **S1** Add `pytest-asyncio` to the `dev` extra and a CI job on Ubuntu installing `.[dev,mcp]`, so MCP tests (including the symlink-escape test) run.
- **S2** Release workflow: before publishing, verify the tag matches `project.version` and run the test suite.
- **S3** MCP `serverInfo.version` reports the MCP SDK version (`1.30.0`), not RepoNeedle's.
- **S4** Mention removal of the `api` extra in the changelog.
- **S5** Low-severity path findings in §4.

## 11. Proposed changelog

See `PROPOSED_CHANGELOG_1.2.0.md` in this directory.

## 12. Next steps to prepare the release

1. Approve and apply B1, B2, B3 (production change for B1/B2 with tests; documentation for B3).
2. Optionally apply S1–S3.
3. Bump the version in `pyproject.toml` and `reponeedle/__init__.py` to 1.2.0.
4. Update the 18 pre-release phrases across 7 documents; change the MCP install instructions to `pip install "reponeedle[mcp]"`; add `CHANGELOG.md` from the proposal.
5. Re-run: full suite (Windows + Linux with `mcp`), `python -m build`, `twine check --strict`, clean installs (base and `[mcp]`).
6. Commit, open a PR to `main`, merge after CI passes.
7. Tag `v1.2.0` on the merge commit; let the release workflow build and publish (do not upload manually).
8. After publication: verify `pip install reponeedle==1.2.0` and `reponeedle[mcp]` from PyPI; then update the Hugging Face Space separately.

---

## Addendum (2026-11-10): Blocker resolution (Prompt 11)

| Item | Resolution |
| :--- | :--- |
| B1 indexing symlink escape | Fixed in `reponeedle/engine.py`: canonical root, `realpath(strict=True)` before open, component-aware containment, read only the resolved path, skipped links recorded as `symlink_outside_repository`. Verified empirically on Windows via an NTFS junction (1.1.0 code exposes the sentinel; fixed code does not). File-symlink tests require Linux CI (not available locally). |
| B2 PyPI 1.1.0 compatibility | Exact published `change_impact` task-inference logic ported; regression tests added. |
| B3 documentation | `KNOWN_LIMITATIONS.md` §4 and `CLAIMS_AND_EVIDENCE.md` corrected; MCP security wording updated. |
| S1 CI | `pytest-asyncio` in `dev`; Linux `mcp-security-linux` job with strict no-skip mode. |
| S2 release workflow | `validate` job (version match, full suite, strict MCP/security), build artifact version check, publish needs validate and build. |
| S3 MCP version | `serverInfo.version` reports RepoNeedle's version. |
| S4 `api` extra | Retained (optional) for 1.1.0 installation compatibility. |
| S5 anchors | Component-aware `..` check (CLI, MCP); CLI anchors use canonical containment. |
