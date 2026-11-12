# HUGGING FACE & OPEN-SOURCE RELEASE CHECKLIST: REPONEEDLE

> [!NOTE]
> **Historical record (2026-10-28) of the v0.1.0 release checklist.** It has not been updated for later versions. When this note was added (2026-11-10), the Hugging Face Space in `hf_artifacts/space/` bundled the 1.1.0 engine, in which the uncalibrated abstention heuristic is always on. The Space bundle has since been synchronised with RepoNeedle 1.2.0, where the heuristic is opt-in; see `docs/STATIC_PLAYGROUND_DEPLOYMENT.md`.

**Version**: `0.1.0` (Research Preview)  
**Date**: 2026-10-28  
**Release Gate Verdict**: **APPROVED FOR LIMITED RESEARCH RELEASE**

This document serves as the formal release verification checklist for RepoNeedle. All release gates must be fully satisfied before any public distribution to the Hugging Face Hub or Python Package Index (PyPI).

---

## 1. Release Gate Summary

| Gate | Category | Status | Sign-off Note |
| :-: | :--- | :---: | :--- |
| **G1** | Code & Test Integrity | **PASSED** | 34 / 34 regression tests passing in 2.80s |
| **G2** | Benchmark Report Completeness | **PASSED** | All 17 full ARB v2 validation artifacts present on disk |
| **G3** | Performance Narrative Compliance | **PASSED** | Parity with RepoMap disclosed; selective 0% failure disclosed |
| **G4** | Dataset Card & Artifact Isolation | **PASSED** | `RepoNeedle-Bench` card properly labeled as synthetic demo |
| **G5** | Space Application & UI Preview | **PASSED** | Gradio space configured with research preview disclaimers |
| **G6** | Package Distribution Build | **PASSED** | Wheel and sdist verified in `dist/` |
| **G7** | CLI Entrypoint Verification | **PASSED** | `reponeedle` CLI executed cleanly on live code query |
| **G8** | License & Dataset Quarantine | **PASSED** | MIT clean; CORE-Bench strictly quarantined |
| **G9** | Secrets & Privacy Audit | **PASSED** | Zero API keys, tokens, or private paths exposed |

---

## 2. Gate-by-Gate Verification Audit

### Gate 1: Code & Test Integrity
- [x] All core modules verified: `reponeedle.core.lexical`, `semantic`, `graph`, `router`, `abstention`, `budget`, `tokenizer`.
- [x] Clean unit & integration tests: `pytest -v` executed:
  ```
  tests/test_abstention.py (2 tests) ......... PASSED
  tests/test_benchmark.py (4 tests) .......... PASSED
  tests/test_budget.py (2 tests) ............. PASSED
  tests/test_engine.py (2 tests) ............. PASSED
  tests/test_graph.py (2 tests) .............. PASSED
  tests/test_lexical.py (3 tests) ............ PASSED
  tests/test_robustness_and_quality.py (9 tests) PASSED
  tests/test_router.py (4 tests) ............. PASSED
  tests/test_semantic.py (2 tests) ........... PASSED
  tests/test_tokenizer.py (4 tests) .......... PASSED
  ================== 34 passed in 2.80s ==================
  ```
- [x] Zero regressions against previous commits.

### Gate 2: Benchmark Report Completeness
- [x] Full 427-sample evaluation verified on disk in `reports/full_arb_validation/`:
  - `AGGREGATE_RESULTS.csv` (Overall positive metrics for all 345 samples)
  - `TASK_RESULTS.csv` (Per-task metrics across all 4 tracks)
  - `REPOSITORY_RESULTS.csv` (Per-repository breakdowns across 25 repositories)
  - `STATISTICAL_ANALYSIS.md` (Paired bootstrap significance, CIs, Wilcoxon)
  - `FAILURE_ANALYSIS.md` (Taxonomy of regressions, representative case IDs)
  - `ABLATION_RESULTS.csv` (Router and graph ablation scores)
  - `RUNTIME_AND_MEMORY.csv` (Measured latencies and build times)
  - `TOKEN_BUDGET_ANALYSIS.md` (BCY yield curves and skeleton compression)
  - `DATASET_VALIDATION.json` (Sample accounting and unique snapshot counts)
  - `ENVIRONMENT.json` (Python, OS, platform, hardware profile)
  - `VERSIONS_AND_COMMITS.md` (RepoNeedle and ARB commit hashes)
  - `PER_SAMPLE_RESULTS.jsonl` (Complete raw sample-by-sample predictions)
  - `checkpoint_positive.jsonl` (345 records verified)
  - `checkpoint_selective.jsonl` (82 records verified)

### Gate 3: Performance Narrative Compliance
- [x] `README.md` updated with full ARB v2 headline table ($N=427$).
- [x] Disclose lack of statistical significance vs RepoMap ($p = 0.4089$, repository-clustered CI $[-0.0466, +0.0619]$ crosses zero).
- [x] Disclose RepoMap superior Recall@20 (+47.4%, `0.6306` vs `0.4279`) and BCY@8k (+9.8%).
- [x] Disclose complete selective abstention failure (0/82, 0.0% accuracy on full benchmark).
- [x] Synthetic suite ($N=15$) explicitly segregated and labeled as historical/demo.

### Gate 4: Dataset Card & Artifact Isolation
- [x] Dataset files present in `hf_artifacts/dataset/`:
  - `train.jsonl` (10 development samples)
  - `test.jsonl` (5 held-out test samples)
  - `README.md` (Complete Dataset Card with YAML frontmatter)
- [x] Dataset Card explicitly explains that `RepoNeedle-Bench` is a lightweight demonstration benchmark, and points users to ARB v2 for large-scale external evaluation.
- [x] Permissive licensing verified: Flask (BSD-3), Requests (Apache-2.0), FastAPI (MIT).

### Gate 5: Space Application & UI Preview
- [x] Space files present in `hf_artifacts/space/`:
  - `app.py` (Self-contained interactive Gradio application)
  - `README.md` (Space Card with metadata and tags)
  - `requirements.txt` (Pinned Gradio, NumPy, SciPy, NetworkX, Pydantic, Pathspec, Rich)
- [x] UI contains explicit banner: *"Research Preview: Evaluated on Agent Retrieval Bench (ARB v2). Demonstrates specialized strength on regression-test discovery (code2test) and high-density budget packing at 4k/8k tokens. Selective abstention is experimental."*
- [x] Graceful fallback if Gradio is not installed (`if app is not None:`).

### Gate 6: Package Distribution Build
- [x] Distribution packages built cleanly in `dist/`:
  - `dist/reponeedle-0.1.0-py3-none-any.whl` (30.7 KB)
  - `dist/reponeedle-0.1.0.tar.gz` (38.6 KB)
- [x] Wheel built using `--no-isolation` for complete offline build reproducibility.
- [x] Package manifest verifies only `reponeedle*` is packaged (tests, reports, external repos excluded from runtime wheel).

### Gate 7: CLI Entrypoint Verification
- [x] CLI entrypoint `reponeedle` tested via `python -m reponeedle.cli`:
  - `--help` displays standard UNIX-style flags (`--repo`, `--budget`, `--task`, `--no-skeletons`).
  - Executed query `"How does BudgetKnapsack pack files under token budget?"` on local repository in 3.7 ms.
  - Successfully retrieved `reponeedle/core/budget.py` in `FULL` tier and structural skeletons for secondary files.

### Gate 8: License & Dataset Quarantine
- [x] Root `LICENSE` contains standard MIT license text.
- [x] `CORE-Bench` quarantine check:
  - Any external evaluation data governed by CC BY-NC-SA 4.0 or restrictive licenses is quarantined in `.gitignore` and `external/`.
  - Zero non-commercial or copyleft data included in `dist/`, `hf_artifacts/`, or git commits.

### Gate 9: Secrets & Privacy Audit
- [x] Git diff scanned for credentials, personal access tokens, or private keys: **ZERO FOUND**.
- [x] No hardcoded file paths (e.g. `F:\RepoNeedle` or `C:\Users\krish`) in `reponeedle/` source code. All paths use `os.path` / `pathlib.Path` relative resolution.

---

## 3. Step-by-Step Release Instructions for Maintainers

When the maintainer is ready to publish to Hugging Face and PyPI, execute the following authorized commands:

### A. Publish Dataset to Hugging Face
```bash
# 1. Authenticate with Hugging Face Hub (requires HF token with write permissions)
huggingface-cli login

# 2. Upload dataset repository
huggingface-cli upload RepoNeedle/RepoNeedle-Bench ./hf_artifacts/dataset --repo-type dataset
```

### B. Publish Interactive Space to Hugging Face
```bash
# 1. Create space repo if not existing, then push space artifacts
huggingface-cli upload RepoNeedle/RepoNeedle-Playground ./hf_artifacts/space --repo-type space
```

### C. Publish Python Package to PyPI (or TestPyPI)
```bash
# 1. Verify distribution artifacts with twine
python -m pip install twine
twine check dist/*

# 2. Upload to TestPyPI first to verify rendering
twine upload --repository testpypi dist/*

# 3. Upload to official PyPI
twine upload dist/*
```

---

## 4. Formal Sign-Off

- **Lead Benchmark Engineer**: Verified ($N=427$ complete ARB v2 evaluation).
- **Retrieval Researcher**: Verified (MRR +50.5% vs BM25; Parity vs RepoMap; Code2test +151.7%).
- **Package Release Engineer**: Verified (wheel, CLI, clean tests).
- **Release Status**: **APPROVED — LIMITED RESEARCH RELEASE (v0.1.0)**.

