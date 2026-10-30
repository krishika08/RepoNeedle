# RepoNeedle Stage 3.16 — Official ContextBench Acquisition & Independent Validation Gate Report

**Document ID**: `STAGE3-16-REPORT-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `143e8bca174b9deb2d3dcb498dbd9db0b04178bd`  
**Production Code Reference**: `12142e8`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`) — **VERIFIED UNCHANGED**  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`) — **VERIFIED UNCHANGED**  
**Final Governance Verdict**: **`BLOCKED — EXTERNAL DATA ACQUISITION REQUIRED`**  

---

## 1. Executive Summary & Mission Charter

Stage 3.16 establishes the formal governance, intake infrastructure, and adapter pipeline for independent external validation using the **official ContextBench dataset** (`Contextbench/ContextBench`, official EuniAI benchmark).

In strict adherence to Stage 3.16 governance:
1. **Zero retrieval or algorithm tuning on ARB v2**: Production code in `reponeedle/` was held completely frozen.
2. **Authoritative dataset endpoints verified**: Official sources were cataloged from Hugging Face Hub, GitHub (`https://github.com/EuniAI/ContextBench`), and official documentation (`https://euniai.github.io/ContextBench/`).
3. **In-sandbox acquisition probed and documented**: All 5 attempted public download routes returned `HTTP Error 403: Forbidden` due to sandbox container network isolation. In accordance with security boundaries, no proxy workarounds or credential intercepts were attempted.
4. **Unofficial mirrors and synthetic datasets prohibited**: The unofficial `Schwerli/ContextBench` mirror was inspected and formally rejected due to differing row counts and unverified schema modifications. Fabricating synthetic Parquet files was strictly prohibited.
5. **Deterministic intake layer built**: An automated validator ([`research/external_data/contextbench/validate_contextbench.py`](file:///F:/RepoNeedle/research/external_data/contextbench/validate_contextbench.py)) was implemented, enforcing the exact official schema (1,136 tasks for full, 500 for verified, 66 repositories, 8 languages) with fail-closed exit codes.
6. **Zero-leakage evaluation adapter built**: An adapter ([`research/contextbench_evaluation/adapter.py`](file:///F:/RepoNeedle/research/contextbench_evaluation/adapter.py)) and security guard ([`research/contextbench_evaluation/leakage_guard.py`](file:///F:/RepoNeedle/research/contextbench_evaluation/leakage_guard.py)) were implemented, strictly isolating retrieval from ground-truth fields (`gold_context`, `patch`, `test_patch`, `f2p`, `p2p`) and preserving the evaluation denominator on checkout failures.
7. **Evaluation preregistered**: Frozen configurations (`ARM-101-BASE`, `BASE-BM25`, `BASE-REPOMAP`) and repository-clustered bootstrap confidence interval protocols were preregistered before inspecting external results.

---

## 2. Frozen Starting Point & Tag Immutability

- **Current Audit HEAD**: `143e8bca174b9deb2d3dcb498dbd9db0b04178bd`
- **Working Tree**: Clean (`nothing to commit, working tree clean`)
- **Tag Verification**:
  - `v0.1.0-baseline` resolves to `8e0042553a14b6e3c6cf5b35823c4da84181a8e9`
  - `stage3-candidate-freeze` resolves to `cd7f3b01e28695f9a9357e0815069e0eae85baca`
- **Production Code Reference**: `12142e8` (`reponeedle/` untouched).

---

## 3. Dataset Intake & Integrity Layer

Created under [`research/external_data/contextbench/`](file:///F:/RepoNeedle/research/external_data/contextbench):

1. **[`README.md`](file:///F:/RepoNeedle/research/external_data/contextbench/README.md)**: Acquisition instructions, expected configurations, file placement, and warning on `Schwerli/ContextBench`.
2. **[`validate_contextbench.py`](file:///F:/RepoNeedle/research/external_data/contextbench/validate_contextbench.py)**: Production validator checking:
   - Full dataset (`default`): exactly 1,136 rows, 66 repositories, 8 languages.
   - Verified subset (`contextbench_verified`): exactly 500 rows.
   - Required columns: `instance_id`, `repo`, `base_commit`, `problem_statement`, `gold_context`.
   - Non-emptiness and global uniqueness of `instance_id`.
   - Valid, non-empty `gold_context` structure.
   - SHA-256 calculation and file integrity.
3. **[`dataset_manifest.json`](file:///F:/RepoNeedle/research/external_data/contextbench/dataset_manifest.json)**: Machine-readable specification.
4. **[`.gitignore`](file:///F:/RepoNeedle/research/external_data/contextbench/.gitignore)**: Rules preventing accidental commits of large Parquet or JSONL benchmark artifacts.
5. **[`ACQUISITION_BLOCKER.md`](file:///F:/RepoNeedle/research/external_data/contextbench/ACQUISITION_BLOCKER.md)**: Exhaustive blocker forensics documenting HTTP 403 network isolation.

---

## 4. Evaluation Adapter & Zero-Leakage Architecture

Created under [`research/contextbench_evaluation/`](file:///F:/RepoNeedle/research/contextbench_evaluation):

1. **[`leakage_guard.py`](file:///F:/RepoNeedle/research/contextbench_evaluation/leakage_guard.py)**:
   - Validates that retrieval input packets contain ONLY `instance_id`, `repo`, `base_commit`, `problem_statement`, and `language`.
   - Immediately raises `DataLeakageSecurityException` if any forbidden evaluation targets (`gold_context`, `patch`, `test_patch`, `f2p`, `p2p`) are detected.
2. **[`adapter.py`](file:///F:/RepoNeedle/research/contextbench_evaluation/adapter.py)**:
   - Freezes RepoNeedle configurations: `ARM-101-BASE` and `BASE-BM25`.
   - Formats predictions conforming to official ContextBench trajectory format.
   - Denominator preservation: records checkout failures as `ERROR_CHECKOUT_FAILED` with empty predictions (0.0 scores), strictly preserving the full 1,136 and 500 task denominators.
3. **[`evaluator.py`](file:///F:/RepoNeedle/research/contextbench_evaluation/evaluator.py)**:
   - Implements file-level MRR, multi-target fractional Recall@K, and Binary Hit@K.
   - Computes repository-clustered bootstrap confidence intervals (10,000 resamples clustered by repository).

---

## 5. Preregistered Evaluation Configurations

| System ID | Architecture Configuration | ARB v2 Development MRR | ARB v2 Recall@20 | ARB v2 P50 Latency (ms) | Role in External Evaluation |
|---|---|---|---|---|---|
| **`ARM-101-BASE`** | Soft Lexical Damping ($\tau=0.25$) + Level 1 Verified Call Edges | **0.2078** | **0.5648** | **12.92** | **Preregistered RepoNeedle Candidate Champion** |
| **`BASE-BM25`** | Decoupled Okapi BM25 length-normalized scoring | **0.1752** | **0.4535** | **10.24** | **Preregistered Lexical Baseline** |
| **`BASE-REPOMAP`** | Official RepoMap reference (commit `9e4d689`) | **0.2293** | **0.6599** | **180.20** | **Preregistered External Reference Leader** |

---

## 6. Research Claims Boundary Ledger

### 6.1 Established on Internal ARB v2 Development Data
- `ARM-101-BASE` achieves **0.2078 MRR**, **0.5648 Recall@20**, and **0.2822 Token BCY@8k**.
- `ARM-101-BASE` achieves **$12.92\text{ ms}$ P50 query latency** ($>13.9\times$ faster than RepoMap at $180.20\text{ ms}$).
- `ARM-101-BASE` outperforms RepoMap on Go repositories (**$0.3125$ vs $0.2866$ MRR**).
- `BASE-REPOMAP` holds the highest ARB v2 MRR point estimate (**0.2293**), but its advantage over `ARM-101-BASE` was not statistically significant at the 0.05 level ($p = 0.0559$).
- Candidate F collapses to **0.1351 MRR** on unconstrained candidate pools ($p = 0.0122$ worse than BM25).
- Universal 100 MB process memory claim is disproven (Caddy requires 198.0 MB RSS, 272.8 MB peak).

### 6.2 NOT YET ESTABLISHED (Forbidden Claims)
- **Generalization to independent repositories or SWE-bench**: Not demonstrated.
- **Performance on official ContextBench**: Unmeasured; zero external tasks evaluated.
- **Superiority over RepoMap in retrieval quality**: Not established.

---

## 7. Deliverables Catalog

All deliverables created and verified:
1. [`research/external_data/contextbench/README.md`](file:///F:/RepoNeedle/research/external_data/contextbench/README.md)
2. [`research/external_data/contextbench/validate_contextbench.py`](file:///F:/RepoNeedle/research/external_data/contextbench/validate_contextbench.py)
3. [`research/external_data/contextbench/dataset_manifest.json`](file:///F:/RepoNeedle/research/external_data/contextbench/dataset_manifest.json)
4. [`research/external_data/contextbench/ACQUISITION_BLOCKER.md`](file:///F:/RepoNeedle/research/external_data/contextbench/ACQUISITION_BLOCKER.md)
5. [`research/external_data/contextbench/.gitignore`](file:///F:/RepoNeedle/research/external_data/contextbench/.gitignore)
6. [`research/contextbench_evaluation/leakage_guard.py`](file:///F:/RepoNeedle/research/contextbench_evaluation/leakage_guard.py)
7. [`research/contextbench_evaluation/adapter.py`](file:///F:/RepoNeedle/research/contextbench_evaluation/adapter.py)
8. [`research/contextbench_evaluation/evaluator.py`](file:///F:/RepoNeedle/research/contextbench_evaluation/evaluator.py)
9. [`research/stage3_16/STAGE3_16_REPORT.md`](file:///F:/RepoNeedle/research/stage3_16/STAGE3_16_REPORT.md)
10. [`research/stage3_16/ACQUISITION_REPORT.md`](file:///F:/RepoNeedle/research/stage3_16/ACQUISITION_REPORT.md)
11. [`research/stage3_16/DATASET_INTEGRITY_REPORT.md`](file:///F:/RepoNeedle/research/stage3_16/DATASET_INTEGRITY_REPORT.md)
12. [`research/stage3_16/EVALUATION_PROTOCOL.md`](file:///F:/RepoNeedle/research/stage3_16/EVALUATION_PROTOCOL.md)
13. [`research/stage3_16/METRIC_CONTRACT.md`](file:///F:/RepoNeedle/research/stage3_16/METRIC_CONTRACT.md)
14. [`research/stage3_16/EXPERIMENT_REGISTRY.jsonl`](file:///F:/RepoNeedle/research/stage3_16/EXPERIMENT_REGISTRY.jsonl)
15. [`research/stage3_16/REPRODUCE.md`](file:///F:/RepoNeedle/research/stage3_16/REPRODUCE.md)
16. [`research/stage3_16/DECISION_REPORT.md`](file:///F:/RepoNeedle/research/stage3_16/DECISION_REPORT.md)
17. [`research/stage3_16/dataset_manifest.json`](file:///F:/RepoNeedle/research/stage3_16/dataset_manifest.json)
18. [`research/stage3_16/evaluation_manifest.json`](file:///F:/RepoNeedle/research/stage3_16/evaluation_manifest.json)
19. [`tests/test_stage3_16_contextbench_gate.py`](file:///F:/RepoNeedle/tests/test_stage3_16_contextbench_gate.py)

---

## 8. Final Governance Verdict

```
[VERDICT] BLOCKED — EXTERNAL DATA ACQUISITION REQUIRED
```

Stage 3.16 establishes a rigorous, fail-closed intake and evaluation pipeline for official ContextBench evaluation. Independent external validation is formally **GATED** until an external operator acquires `full.parquet` (1,136 tasks) and `contextbench_verified.parquet` (500 tasks) outside the sandbox environment.

**Stage 3.17 algorithm tuning is strictly prohibited until this evaluation gate is resolved.**
