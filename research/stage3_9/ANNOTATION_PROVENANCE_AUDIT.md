# Stage 3.9.3: Annotation Provenance & Repository Reconciliation Audit
## Forensic Verification of Feasibility Evidence, Annotation Integrity & Benchmark Corpus Taxonomy

**Document ID**: `STAGE3-9-AUDIT-001`  
**Stage**: Stage 3.9.3 — Python-First LFCG Implementation and Validation  
**Date**: November 1, 2026  
**Workspace**: `F:\RepoNeedle`  
**Active Branch**: `research/stage3_9`  
**Governing Status**: **PHASE A FEASIBILITY EVIDENCE AUDIT**  
**Governing Rule**: If labels were generated using the resolution heuristics being evaluated, explicitly disclose this and do not present the results as independent precision validation. Reconcile the Stage 3.9.1 count of 10 Python repositories with the Stage 3.9.2 claim of 14 Python codebases using the actual benchmark manifest.

---

## 1. Forensic Audit of the Stage 3.9.2 Annotated Dataset

In Stage 3.9.2, an offline evaluation script ([`evaluate_edge_precision.py`](file:///F:/RepoNeedle/research/stage3_9/prototypes/evaluate_edge_precision.py)) was executed against an annotated dataset of $N = 250$ call sites ([`annotated_call_sites.json`](file:///F:/RepoNeedle/research/stage3_9/prototypes/annotated_call_sites.json)), reporting an overall precision of $98.33\%$ under Fail-Closed LFCG semantics.

A forensic inspection of [`generate_annotated_dataset.py`](file:///F:/RepoNeedle/research/stage3_9/prototypes/generate_annotated_dataset.py) was conducted in Stage 3.9.3 to establish data provenance:

### 1.1 Provenance Disclosures & Mandatory Limitations

> [!WARNING]
> **Explicit Governance Disclosure on Dataset Independence**:
> 1. **Synthetic Authoring**: The $N = 250$ call-site annotations were synthesized by a single AI research assistant based on manual inspection of benchmark source code patterns.
> 2. **Absence of Independent Double-Blind Human Panel**: The labels were **not** generated through a multi-annotator, double-blind human engineering protocol with formal inter-annotator reliability metrics (such as Cohen's Kappa or Fleiss' Kappa).
> 3. **Non-Independent Validation**: Because the ground-truth status assignments (`RESOLVABLE_EXACT`, `RESOLVABLE_RECEIVER`, `AMBIGUOUS_MULTI_TARGET`, `UNRESOLVABLE_DYNAMIC`, `UNRESOLVABLE_EXTERNAL`) were codified using the same structural taxonomy evaluated by the engine, **these results MUST NOT be presented as independent, third-party precision validation**.
> 4. **Proper Scientific Classification**: The $N = 250$ dataset constitutes an **exploratory synthetic feasibility fixture / diagnostic probe**, verifying that the Fail-Closed LFCG implementation functions consistently with its theoretical design contract. Confirmatory precision claims require an independent human-annotated benchmark.

### 1.2 Annotation Procedure & Provenance Metadata
* **Annotation Procedure**: Stratified sampling of candidate call expressions from 12 benchmark repositories representing diverse AST, receiver, dynamic, and import structures.
* **Annotator Count & Role**: 1 primary author (AI Coding Assistant), 0 independent adjudicators.
* **Disagreements & Adjudication**: No formal multi-annotator adjudication occurred. Ambiguous cases (such as generic interface methods or overloaded signatures) were conservatively tagged as `AMBIGUOUS_MULTI_TARGET` based on codebase candidate counts.
* **Sampling Distribution across 12 Repositories ($N = 250$)**:
  - `eslint/eslint` (JavaScript): 30 items (12.0%)
  - `clap-rs/clap` (Rust): 25 items (10.0%)
  - `gin-gonic/gin` (Go): 20 items (8.0%)
  - `tokio-rs/tokio` (Rust): 20 items (8.0%)
  - `vitejs/vite` (TypeScript): 20 items (8.0%)
  - `mockito/mockito` (Java): 20 items (8.0%)
  - `pallets/click` (Python): 15 items (6.0%)
  - `pytest-dev/pytest` (Python): 15 items (6.0%)
  - `fastapi/fastapi` (Python): 15 items (6.0%)
  - `huggingface/transformers` (Python): 15 items (6.0%)
  - `etcd-io/etcd` (Go): 15 items (6.0%)
  - `vuejs/core` (TypeScript): 15 items (6.0%)
  - `spring-projects/spring-boot` (Java): 15 items (6.0%)
  - `caddyserver/caddy` (Go): 10 items (4.0%)

---

## 2. Recomputed Raw Annotation Statistics & False-Positive Rates

Directly recomputed from raw records via [`recompute_raw_annotations.py`](file:///F:/RepoNeedle/research/stage3_9/prototypes/recompute_raw_annotations.py) without heuristics:

### 2.1 Full Cohort Breakdown under Fail-Closed LFCG

| Language Cohort | Sample Size ($N$) | Resolved | Correct | Incorrect | Unresolved | Precision | 95% Wilson CI | Coverage | 95% Wilson CI | False Positive Rate | 95% Wilson CI |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Python** | 60 | 30 | 30 | 0 | 30 | **100.0%** | `[88.6%, 100.0%]` | **50.00%** | `[37.7%, 62.3%]` | **0.00%** | `[0.0%, 11.3%]` |
| **Go** | 45 | 20 | 19 | 1 | 25 | **95.00%** | `[76.4%, 99.1%]` | **44.44%** | `[30.9%, 58.8%]` | **3.85%** | `[0.7%, 18.9%]` |
| **Rust** | 45 | 22 | 21 | 1 | 23 | **95.45%** | `[78.2%, 99.2%]` | **48.89%** | `[35.0%, 63.0%]` | **4.17%** | `[0.7%, 20.2%]` |
| **TypeScript** | 35 | 21 | 21 | 0 | 14 | **100.0%** | `[84.5%, 100.0%]` | **60.00%** | `[43.6%, 74.5%]` | **0.00%** | `[0.0%, 21.5%]` |
| **JavaScript** | 30 | 12 | 12 | 0 | 18 | **100.0%** | `[75.8%, 100.0%]` | **40.00%** | `[24.6%, 57.7%]` | **0.00%** | `[0.0%, 17.6%]` |
| **Java** | 35 | 15 | 15 | 0 | 20 | **100.0%** | `[79.6%, 100.0%]` | **42.86%** | `[28.0%, 59.1%]` | **0.00%** | `[0.0%, 16.1%]` |
| **OVERALL** | **250** | **120** | **118** | **2** | **130** | **98.33%** | `[94.1%, 99.5%]` | **48.00%** | `[41.9%, 54.2%]` | **1.52%** | `[0.4%, 5.4%]` |

* **Total True Positives**: 118
* **Total False Positives**: 2 (one regex associated function false match in `clap`, one unexported package call in `gin`)
* **Total True Negatives**: 130 (external stdlib, builtins, dynamic calls, and multi-target interfaces safely abstained)
* **Total False Negatives**: 0
* **False Positive Rate ($\text{FPR} = \frac{\text{FP}}{\text{TN} + \text{FP}}$)**: **$1.52\%$** (95% Wilson CI: `[0.4%, 5.4%]`).

---

## 3. Reconciliation of Python Repository Counts: 10 vs. 13 vs. 14

A discrepancy was identified between Stage 3.9.1 (which cited **10 Python repositories**) and Stage 3.9.2 (which cited **14 Python codebases**).

An audit was conducted across [`external/agent-retrieval-bench/data/repo_manifest.jsonl`](file:///F:/RepoNeedle/external/agent-retrieval-bench/data/repo_manifest.jsonl), benchmark queries, and corpus chunk distributions via [`audit_repo_languages.py`](file:///F:/RepoNeedle/research/stage3_9/prototypes/audit_repo_languages.py) and [`fast_audit_repo_file_types.py`](file:///F:/RepoNeedle/research/stage3_9/prototypes/fast_audit_repo_file_types.py).

### 3.1 Global Benchmark Repository Language Breakdown ($K = 25$)

Across all tasks in ARB v2 (`code2test`, `comment2context`, `edit2ripple`, `trace2code`, `abstention`), there are exactly **25 distinct software repositories**:

```
=== Language Breakdown across 25 Repositories ===
├── Python (13 Repositories - Primary Language .py):
│   1. HypothesisWorks/hypothesis   (32,690 lines)
│   2. fastapi/fastapi               (8,509 lines)
│   3. huggingface/diffusers        (389,448 lines)
│   4. huggingface/transformers     (457,453 lines)
│   5. ipython/ipython               (18,962 lines)
│   6. numpy/numpy                   (88,770 lines)
│   7. pallets/click                  (2,321 lines)
│   8. pydantic/pydantic             (44,846 lines)
│   9. pypa/pip                      (15,250 lines)
│  10. pytest-dev/pytest             (61,888 lines)
│  11. python/mypy                   (20,264 lines)
│  12. scrapy/scrapy                 (18,481 lines)
│  13. tox-dev/tox                    (8,362 lines)
│
├── Rust (3 Repositories - Primary Language .rs):
│   1. astral-sh/ruff               (133,016 lines Rust vs 35,675 lines Python)
│   2. clap-rs/clap                  (38,604 lines Rust)
│   3. tokio-rs/tokio                (90,944 lines Rust)
│
├── Go (3 Repositories - Primary Language .go):
│   1. caddyserver/caddy             (11,100 lines Go)
│   2. etcd-io/etcd                  (45,347 lines Go)
│   3. gin-gonic/gin                  (3,903 lines Go)
│
├── TypeScript (3 Repositories - Primary Language .ts/.tsx):
│   1. microsoft/playwright         (110,546 lines TS vs 29,766 lines JS)
│   2. vitejs/vite                   (53,148 lines TS vs 8,601 lines JS)
│   3. vuejs/core                    (90,737 lines TS vs 1,062 lines JS)
│
├── Java (2 Repositories - Primary Language .java):
│   1. mockito/mockito               (19,138 lines Java)
│   2. spring-projects/spring-boot  (139,888 lines Java)
│
└── JavaScript (1 Repository - Primary Language .js):
    1. eslint/eslint                 (39,529 lines JS)
```

### 3.2 Root Cause of the Numerical Discrepancy

1. **Origin of "10 Python Repositories" (Stage 3.9.1)**:
   In the `v2_comment2context` benchmark task split, there are exactly **10 Python repositories** evaluated:
   `hypothesis`, `diffusers`, `transformers`, `ipython`, `numpy`, `pydantic`, `pip`, `pytest`, `mypy`, `scrapy`.
   Stage 3.9.1 cited this task-specific sub-split count rather than the global repository population.
2. **Origin of "14 Python Codebases" (Stage 3.9.2)**:
   Stage 3.9.2 counted all **13 primary Python repositories** plus `astral-sh/ruff`.
   While `astral-sh/ruff` is a Python ecosystem linter CLI with 35,675 lines of Python stub/test code, its core engine is **78.9% Rust** (133,016 lines of `.rs`). Classifying Ruff as Python was linguistically imprecise.
3. **Official Reconciled Truth**:
   - There are **13 genuinely primary Python repositories** across ARB v2.
   - `astral-sh/ruff` is classified as **Rust** based on source code volume (133k lines Rust vs 35k lines Python).
   - In `repo_manifest.jsonl`, only 12 pilot repositories are listed, of which 4 are Python (`pytest`, `fastapi`, `transformers`, `diffusers`). The remaining 13 repositories were added in ARB v2 expansion splits.

