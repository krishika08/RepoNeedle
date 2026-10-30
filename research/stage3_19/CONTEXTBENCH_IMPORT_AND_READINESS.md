# RepoNeedle Stage 3.19 — External Benchmark Readiness & ContextBench Import Specification

**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Date:** 2026-10-30  
**Current External Gate Status:** **`BLOCKED — OFFICIAL DATA ACQUISITION`**  
**Independent Generalization Status:** **NOT INDEPENDENTLY VALIDATED (UNTESTED ON EXTERNAL BENCHMARK)**

---

## 1. Governance Context & Anti-Shortcut Policy

RepoNeedle's internal leaderboard on Agent-Retrieval-Bench (ARB v2) is an internal development benchmark. Because all architectures (Candidates A through F, Cascaded Rankers, and ARM-101 variants) were iteratively designed and evaluated against ARB v2, internal benchmark scores cannot prove out-of-distribution generalization.

Independent empirical validation requires evaluating against the pinned, official **ContextBench** benchmark.

### Strict Governance Rules:
1. **Zero Unofficial Mirrors:** Prohibit downloading or evaluating against unofficial derivatives (such as `Schwerli/ContextBench`).
2. **Zero Synthetic Task Relabeling:** Prohibit generating synthetic or simulated tasks and relabeling them as "ContextBench-compatible."
3. **Zero Security / Sandbox Bypasses:** Network restrictions must not be circumvented with unverified proxies or disabled TLS verification.
4. **Preservation of Gate Status:** The gate remains explicitly documented as **`BLOCKED — OFFICIAL DATA ACQUISITION`** until authentic upstream parquet artifacts are delivered into the repository.

---

## 2. Pinned Upstream Dataset Manifest

The authoritative dataset manifest is recorded in [research/external_data/contextbench/dataset_manifest.json](file:///F:/RepoNeedle/research/external_data/contextbench/dataset_manifest.json):

| Property | Pinned Official Target 1: `default` | Pinned Official Target 2: `contextbench_verified` |
| :--- | :--- | :--- |
| **Upstream Repository** | `Contextbench/ContextBench` | `Contextbench/ContextBench` |
| **Source URL** | `https://huggingface.co/datasets/Contextbench/ContextBench` | `https://huggingface.co/datasets/Contextbench/ContextBench` |
| **Pinned Revision** | `c285579` | `c285579` |
| **Target Filename** | `full.parquet` | `contextbench_verified.parquet` |
| **Expected Row Count** | 1,136 tasks | 500 tasks |
| **Repository Count** | 66 repositories | 35 repositories |
| **Language Coverage** | 8 languages | 8 languages |
| **Expected File Size** | 26,102,607 bytes (~26.1 MB) | 9,558,250 bytes (~9.56 MB) |
| **Expected SHA-256 Checksum** | `2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8` | `e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791` |

---

## 3. Data Integrity & Ingestion Contract

Upon official acquisition, the ingestion pipeline must execute the cryptographic verification contract implemented in [research/external_data/contextbench/validate_contextbench.py](file:///F:/RepoNeedle/research/external_data/contextbench/validate_contextbench.py):

### 3.1 Verification Checklist:
1. **Cryptographic Checksum Verification:** Compare the SHA-256 hash of the local parquet file against the manifest.
2. **Schema Conformity Check:**
   - Must contain: `instance_id` (str), `repo` (str), `base_commit` (str), `problem_statement` (str), `gold_context` (list[str]).
3. **Data Leakage Quarantine:**
   - Strictly prohibit candidate rankers from accessing: `gold_context`, `patch`, `test_patch`, `f2p`, `p2p`.
4. **Environment Isolation:** Evaluation must execute in fresh worker processes to prevent memory carryover across repository corpora.

---

## 4. Evaluation Readiness Summary

When network access or authorized out-of-band transfer delivers the authentic files:
1. Run `python research/external_data/contextbench/validate_contextbench.py` to confirm checksums.
2. Execute the evaluation harness across the 500 verified tasks using:
   - `BASE-BM25` (production baseline)
   - `ARM-101-BASE` (prototype candidate)
   - `BASE-REPOMAP` (external benchmark reference)
3. Only upon successful execution of this contract may RepoNeedle claim **independent external validation**.
