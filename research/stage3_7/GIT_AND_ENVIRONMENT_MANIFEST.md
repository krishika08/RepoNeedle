# RepoNeedle Stage 3.7: Git & Environment Manifest

**Generated**: October 31, 2026  
**Stage**: Stage 3.7 — Retrieval Failure Deconstruction & Controlled Component Isolation  
**Workspace**: `F:\RepoNeedle`  

---

## 1. Git Repository State

- **Active Branch**: `research/stage3_7`
- **Starting Audit Commit**: `f61c6be926fa4df0caaba5a1bff5a0c2a00794d2` (Stage 3.6 audit completion)
- **Base Historical Commits**:
  - `4f78cc3` (Stage 3.5 report)
  - `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` (`v0.1.0-baseline`)
  - `cd7f3b01e28695f9a9357e0815069e0eae85baca` (`stage3-candidate-freeze`)
- **Immutable Tag Verification**:
  - `v0.1.0-baseline^{commit}`: `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` [VERIFIED UNCHANGED]
  - `stage3-candidate-freeze^{commit}`: `cd7f3b01e28695f9a9357e0815069e0eae85baca` [VERIFIED UNCHANGED]
- **Git Security & Access Control Review**:
  - Stage 3.6 noted permission failures due to Windows Low Mandatory Level sandbox execution when attempting file renames (`os.replace` / `MoveFileEx`) inside `.git/`.
  - The working branch `research/stage3_7` was created directly at commit `f61c6be`, ensuring strict branch isolation without modifying history or using dangerous recursive permission grants.
  - No commit history rewritten. No historical stage results modified.

---

## 2. Hardware and Environment Specification

- **Operating System**: Microsoft Windows 11 Home Single Language (10.0.26100 Build 26100)
- **Host System**: KRISHIKA_HP
- **CPU Architecture**: AMD64 Family 25 Model 80 Stepping 0 (x86_64, Multi-core)
- **Python Runtime**: Python 3.12.10 (tags/v3.12.10:0db02e6, Oct 8 2024, 15:47:00) [MSC v.1941 64 bit (AMD64)]
- **Shell**: Microsoft PowerShell 5.1 / PowerShell Core

---

## 3. Python Dependency Manifest

| Package | Version | Purpose |
|---|---|---|
| `python` | `3.12.10` | Base interpreter |
| `numpy` | `2.2.6` | Numerical linear algebra, array indexing, and vectorization |
| `scipy` | `1.15.3` | Statistical hypothesis testing, paired Wilcoxon, bootstrap sampling |
| `networkx` | `3.4.2` | Graph construction, directed dependency graph, degree analysis |
| `pydantic` | `2.11.1` | Data models and configuration validation |
| `pytest` | `9.1.1` | Regression and unit test suite |
| `anyio` | `4.15.1` | Async test fixtures |

---

## 4. Benchmark & Data Assets

- **Corpus Location**: `external/agent-retrieval-bench/data/corpus/v2_selective_mixed/`
  - Corpus Manifest: `corpus_manifest.jsonl` (271 corpus entries, 218 active benchmark corpora)
- **Benchmark Tracks** (`external/agent-retrieval-bench/data/benchmark/`):
  - `v2_code2test`: 106 samples
  - `v2_comment2context`: 80 samples
  - `v2_trace2code`: 101 samples
  - `v2_edit2ripple`: 58 samples
  - **Total Positive Population**: 345 samples ($N=345$)
  - **Zero-Gold Population**: 82 samples ($N=82$, 50 natural no-gold + 32 counterfactual)
- **Authoritative Baselines**:
  - Aider RepoMap reference: `external/agent-retrieval-bench/data/eval/.../repomap_code_only_details.jsonl` (MRR 0.2293)
  - Pure BM25 baseline: Stage 2 EXP-016 (MRR 0.1735)

---

## 5. Deliverables Directory Manifest (`research/stage3_7/`)

| File | Type | Description |
|---|---|---|
| `STAGE3_7_DECISION_REPORT.md` | Report | Comprehensive final report answering all 16 research questions |
| `EXPERIMENT_REGISTRY.jsonl` | Data | Registry of configurations and results for EXP-371 to EXP-378 |
| `BM25_LENGTH_DIAGNOSTICS.csv` | Data | Per-file, per-repo, and per-query BM25 length inflation measurements |
| `GRAPH_HUB_DIAGNOSTICS.csv` | Data | Graph topology, degree distributions, max degrees, hub concentration |
| `GRAPH_DIFFUSION_RESULTS.csv` | Data | Per-query score and rank deltas before and after directional diffusion |
| `RANKING_RESULTS.csv` | Data | Canonical evaluation metrics across all 8 experimental configurations |
| `PER_QUERY_RESULTS.jsonl` | Data | 2,760 per-query records (345 queries $\times$ 8 systems) |
| `STATISTICAL_COMPARISON.md` | Report | 10,000 repo-clustered bootstrap CIs, paired tests, effect sizes |
| `RUNTIME_AND_MEMORY.csv` | Data | Isolated runtime latency, index time, heap, and process RSS |
| `FAILURE_ANALYSIS.md` | Analysis | Forensic deconstruction of BM25 inflation, hubs, and PageRank dilution |
| `REPRODUCE.md` | Guide | End-to-end reproducible execution guide |
| `GIT_AND_ENVIRONMENT_MANIFEST.md`| Manifest | This document |
| `scripts/audit_bm25_length.py` | Script | Diagnostic script for BM25 length inflation |
| `scripts/audit_graph_hubs.py` | Script | Diagnostic script for graph topology and diffusion |
| `scripts/evaluate_experiment_matrix.py` | Script | Evaluator for EXP-371 through EXP-378 |
| `scripts/compute_paired_statistics.py` | Script | 10,000 bootstrap resampler and paired statistical testing |
| `scripts/benchmark_runtime_and_memory.py` | Script | Efficiency and resource benchmark harness |

