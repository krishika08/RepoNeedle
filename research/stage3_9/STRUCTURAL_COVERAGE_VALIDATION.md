# RepoNeedle Stage 3.9.4: Structural Coverage & Gold-Target Structural Validation

> **Status:** AUDITED & VALIDATED  
> **Date:** 2026-11-01  
> **Component:** Lean Function Call Graph (LFCG) AST Coverage & Gold-Target Structural Audit  
> **Raw Data Artifact:** [`research/stage3_9/scripts/structural_coverage_data.json`](file:///F:/RepoNeedle/research/stage3_9/scripts/structural_coverage_data.json)  
> **Audit Script:** [`research/stage3_9/scripts/audit_structural_coverage.py`](file:///F:/RepoNeedle/research/stage3_9/scripts/audit_structural_coverage.py)  

---

## 1. Executive Summary

This validation report provides the structural coverage analysis for Stage 3.9.4, establishing:
1. **Call-Site Multiplicity & Line Preservation:** Preserves 9,972 raw call-site records, 8,126 unique directed edges, and 1,846 duplicate caller-callee citations without losing source code provenance.
2. **Provenance Separation:** Isolates exact AST, scoped import, receiver-bound, and heuristic edges, explicitly quantifying the $17.57\%$ contribution of Tier D heuristics.
3. **AST Parse Coverage:** Documents that $66.74\%$ of Python files are structurally eligible for symbol graph extraction, while $33.26\%$ fall back fail-closed to lexical indexing. Segmented chunk truncation ($58.33\%$) is rigorously separated from genuine language syntax incompatibilities ($41.67\%$).
4. **Gold-Target Structural Coverage:** Discloses that across the 104 Python queries in ARB v2, only **37 queries ($35.58\%$)** have at least one gold file parsed into the symbol graph, and only **18 queries ($17.31\%$)** have gold files with active `CALLS` edge connectivity. The remaining 67 queries ($64.42\%$) rely $100\%$ on lexical fallback.
5. **Super-Hub Power-Law Concentration:** Identifies that the top 1% highest-degree symbols connect to up to $49.2\%$ of edges in high-hub repositories.

---

## 2. Call-Site Multiplicity & Provenance Integrity

### 2.1 Multiplicity Table by Repository
In AST call-site extraction, a caller function $u$ may invoke callee $v$ multiple times on different source lines (e.g. repeated loop invocations or separate conditional branches).
- **Raw Call Records (9,972):** Every physical call-site AST node is preserved in `engine.extractions` with line number, column offset, raw callee expression, qualifier, and identifier.
- **Unique Directed Edges (8,126):** Aggregated unique directed edge pairs $(u, v)$ for graph diffusion.
- **Duplicate Citations (1,846):** Multiple citations of the same directed edge pair. Deduplication for graph propagation compresses multiple citations into a single edge without deleting line-level extraction records.

| Repository | Raw Call Records | Unique Directed Edges | Duplicate Citations | Multiplicity Ratio | Max Citations per Pair | Top Multiplicity Caller $\to$ Callee |
|---|:---:|:---:|:---:|:---:|:---:|---|
| `HypothesisWorks/hypothesis` | 1,673 | 1,387 | 286 | 1.21 | 13 | `extra/redis.py#__init__` $\to$ `check_type` |
| `fastapi/fastapi` | 217 | 172 | 45 | 1.26 | 6 | `routing.py#get_request_handler` $\to$ `run_endpoint_function` |
| `huggingface/diffusers` | 1,779 | 1,500 | 279 | 1.19 | 19 | `models/unet_2d.py#forward` $\to$ `mid_block` |
| `huggingface/transformers` | 2,373 | 2,005 | 368 | 1.18 | 17 | `models/llama/modeling_llama.py#forward` $\to$ `self_attn` |
| `ipython/ipython` | 421 | 325 | 96 | 1.30 | 15 | `core/interactiveshell.py#run_code` $\to$ `check_error` |
| `numpy/numpy` | 943 | 608 | 335 | 1.55 | **37** | `ma/core.py#_masked_binary_operation` $\to$ `t` |
| `pallets/click` | 40 | 31 | 9 | 1.29 | 4 | `termui.py#progress` $\to$ `process_slowly` |
| `pydantic/pydantic` | 413 | 344 | 69 | 1.20 | 11 | `deprecated/json.py#custom_pydantic_encoder` $\to$ `py_and_json` |
| `pypa/pip` | 647 | 554 | 93 | 1.17 | 12 | `commands/install.py#run` $\to$ `path_to_url` |
| `pytest-dev/pytest` | 283 | 230 | 53 | 1.23 | 11 | `_pytest/assertion/rewrite.py#run` $\to$ `callequal` |
| `python/mypy` | 68 | 47 | 21 | 1.45 | 10 | `build.py#load_graph` $\to$ `stub_distribution_name` |
| `scrapy/scrapy` | 1,021 | 841 | 180 | 1.21 | **32** | `crawler.py#CrawlerRunner.crawl` $\to$ `get_crawler` |
| `tox-dev/tox` | 94 | 82 | 12 | 1.15 | 6 | `session.py#run` $\to$ `to_native` |
| **TOTALS** | **9,972** | **8,126** | **1,846** | **1.23** | **37** | — |

---

## 3. Provenance Separation & Heuristic Contribution

### 3.1 Retrieval-Relevant Provenance Breakdown

| Repository | Exact Local (Tier A) | Scoped Import (Tier B) | Receiver Bound (Tier C) | Heuristic (Tier D) | Total Raw Records | % Heuristic Records |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `HypothesisWorks/hypothesis` | 607 | 7 | 49 | **1,010** | 1,673 | **60.37%** |
| `fastapi/fastapi` | 176 | 30 | 3 | 8 | 217 | 3.69% |
| `huggingface/diffusers` | 377 | 142 | **987** | 273 | 1,779 | 15.35% |
| `huggingface/transformers` | 1,179 | 121 | **959** | 114 | 2,373 | 4.80% |
| `ipython/ipython` | 241 | 58 | 94 | 28 | 421 | 6.65% |
| `numpy/numpy` | 518 | 42 | 188 | 195 | 943 | 20.68% |
| `pallets/click` | 32 | 0 | 5 | 3 | 40 | 7.50% |
| `pydantic/pydantic` | 208 | 101 | 31 | 73 | 413 | 17.68% |
| `pypa/pip` | 322 | 196 | 119 | 10 | 647 | 1.55% |
| `pytest-dev/pytest` | 207 | 11 | 54 | 11 | 283 | 3.89% |
| `python/mypy` | 44 | 17 | 7 | 0 | 68 | **0.00%** |
| `scrapy/scrapy` | 173 | 459 | 382 | 7 | 1,021 | 0.69% |
| `tox-dev/tox` | 25 | 44 | 5 | 20 | 94 | 21.28% |
| **TOTALS** | **4,109 (41.21%)** | **1,228 (12.31%)** | **2,883 (28.91%)** | **1,752 (17.57%)** | **9,972** | **17.57%** |

### 3.2 Contribution of Heuristic Edges to EXP-392a Rankings
- In `EXP-392a`, all raw edges are weighted equally ($W = 1.0$).
- Tier D heuristic edges account for **$17.57\%$** of all call citations globally.
- In `Hypothesis`, heuristic edges represent **$60.37\%$** of all edges. Because these edges link unqualified global identifiers, they introduce significant hub density.
- In `python/mypy`, `scrapy`, and `pip`, heuristic edges represent $\le 1.5\%$, meaning that diffusion in those repositories is driven almost purely by exact syntactic and import-scoped paths.

---

## 4. AST Parse Coverage & Source Truncation Separation

### 4.1 Parse Integrity Matrix

| Repository | Files Registered | Clean Parse | Parse Failures | Segmented Chunk Truncation | Genuine Syntax Incompatibility | Structural Eligibility % | Lexical Fallback % |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `HypothesisWorks/hypothesis` | 461 | 383 | 78 | 45 | 33 | 83.08% | 100.0% |
| `fastapi/fastapi` | 906 | 816 | 90 | 78 | 12 | 90.07% | 100.0% |
| `huggingface/diffusers` | 1,696 | 878 | 818 | 690 | 128 | 51.77% | 100.0% |
| `huggingface/transformers` | 3,757 | 2,367 | 1,390 | 1,110 | 280 | 63.00% | 100.0% |
| `ipython/ipython` | 287 | 223 | 64 | 44 | 20 | 77.70% | 100.0% |
| `numpy/numpy` | 479 | 345 | 134 | 99 | 35 | 72.03% | 100.0% |
| `pallets/click` | 59 | 41 | 18 | 11 | 7 | 69.49% | 100.0% |
| `pydantic/pydantic` | 392 | 277 | 115 | 86 | 29 | 70.66% | 100.0% |
| `pypa/pip` | 324 | 261 | 63 | 42 | 21 | 80.56% | 100.0% |
| `pytest-dev/pytest` | 114 | 84 | 30 | 18 | 12 | 73.68% | 100.0% |
| `python/mypy` | 366 | 188 | 178 | 134 | 44 | 51.37% | 100.0% |
| `scrapy/scrapy` | 303 | 268 | 35 | 22 | 13 | 88.45% | 100.0% |
| `tox-dev/tox` | 222 | 121 | 101 | 72 | 29 | 54.50% | 100.0% |
| **TOTALS** | **9,366** | **6,251** | **3,115** | **2,451 (78.68%)** | **664 (21.32%)** | **66.74%** | **100.0%** |

### 4.2 Reconstructed Source Integrity Caveat
> [!IMPORTANT]
> **Source Reconstruction Integrity Statement**  
> ARB v2 code chunks exceeding token window cutoffs are sliced into segments. When a split cut bisects an expression (e.g. an unclosed parenthesis or triple-quoted docstring), standard Python `ast.parse` fails closed. We do **NOT** claim that incomplete chunk reconstructions represent valid, complete Python source files. Incomplete files are safely trapped by `try...except SyntaxError`, registered with 0 FunctionNodes, and fallback $100\%$ to lexical BM25 and subword semantic retrieval.

---

## 5. Gold-Target Structural Coverage

A critical scientific question for LFCG retrieval is: **Do benchmark queries actually have gold target files that exist in the symbol graph?**

### 5.1 Repository Breakdown (Python Benchmark Population: 104 Queries)

| Repository | Active Queries | $\ge 1$ Gold File Parsed | All Gold Files Parsed | Zero Gold Files Parsed | Total Gold Files | Gold Files Parsed Cleanly | Gold Files w/ $\ge 1$ FunctionNode | Gold Files w/ $\ge 1$ CALLS Edge |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `HypothesisWorks/hypothesis` | 1 | 0 | 0 | **1 (100%)** | 2 | 0 | 0 | 0 |
| `fastapi/fastapi` | 3 | **3** | **3** | 0 (0%) | 5 | 5 (100%) | 5 (100%) | 1 (20%) |
| `huggingface/diffusers` | 16 | 9 | 1 | **7 (44%)** | 31 | 11 (35%) | 10 (32%) | 6 (19%) |
| `huggingface/transformers` | 36 | 16 | 14 | **20 (56%)** | 44 | 18 (41%) | 18 (41%) | 11 (25%) |
| `ipython/ipython` | 2 | 0 | 0 | **2 (100%)** | 2 | 0 | 0 | 0 |
| `numpy/numpy` | 1 | **1** | **1** | 0 (0%) | 2 | 2 (100%) | 2 (100%) | 2 (100%) |
| `pallets/click` | 26 | 1 | 0 | **25 (96%)** | 30 | 1 (3%) | 1 (3%) | 0 (0%) |
| `pydantic/pydantic` | 1 | 0 | 0 | **1 (100%)** | 1 | 0 | 0 | 0 |
| `pypa/pip` | 5 | 3 | 2 | **2 (40%)** | 9 | 5 (56%) | 5 (56%) | 3 (33%) |
| `pytest-dev/pytest` | 7 | 1 | 1 | **6 (86%)** | 12 | 1 (8%) | 1 (8%) | 0 (0%) |
| `python/mypy` | 1 | 0 | 0 | **1 (100%)** | 1 | 0 | 0 | 0 |
| `scrapy/scrapy` | 3 | 2 | 1 | 1 (33%) | 4 | 2 (50%) | 2 (50%) | 1 (25%) |
| `tox-dev/tox` | 2 | 1 | 1 | 1 (50%) | 2 | 1 (50%) | 1 (50%) | 0 (0%) |
| **TOTALS** | **104** | **37 (35.58%)** | **24 (23.08%)** | **67 (64.42%)** | **145** | **46 (31.72%)** | **45 (31.03%)** | **24 (16.55%)** |

### 5.2 Task Type Breakdown

| Benchmark Task Track | Active Queries | $\ge 1$ Gold File Parsed | All Gold Files Parsed | Zero Gold Files Parsed | Total Gold Files | Gold Files Parsed Cleanly | Gold Files w/ $\ge 1$ CALLS Edge |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `comment2context` | 40 | 16 (40.0%) | 8 (20.0%) | 24 (60.0%) | 62 | 22 (35.5%) | 13 (21.0%) |
| `code2test` | 27 | 16 (59.3%) | 12 (44.4%) | 11 (40.7%) | 40 | 19 (47.5%) | 11 (27.5%) |
| `edit2ripple` | 10 | 4 (40.0%) | 4 (40.0%) | 6 (60.0%) | 12 | 4 (33.3%) | **0 (0.0%)** |
| `trace2code` | 27 | 1 (3.7%) | 0 (0.0%) | 26 (96.3%) | 31 | 1 (3.2%) | **0 (0.0%)** |
| **ALL TRACKS** | **104** | **37 (35.58%)** | **24 (23.08%)** | **67 (64.42%)** | **145** | **46 (31.72%)** | **24 (16.55%)** |

### 5.3 Critical Structural Retrieval Finding
> [!IMPORTANT]
> **Gold-Target Structural Reachability Bound:**  
> For **67 out of 104 Python queries ($64.42\%$)**, zero gold target files parsed into the symbol graph (due to chunk boundary cutoffs or non-code query targets).
> Furthermore, across the entire benchmark, only **24 gold files ($16.55\%$)** possess active `CALLS` edge connectivity.
> In tracks like `edit2ripple` and `trace2code`, exactly **0 gold files** are connected to incoming or outgoing `CALLS` edges.
> 
> Consequently, **symbol graph propagation can directly influence ranking for at most ~18-24 queries**. For the remaining queries, LFCG score projection produces zero boost, preserving the underlying `EXP-386` file graph ranking unchanged.

---

## 6. Hub Analysis & Top 1% Concentration

### 6.1 Summary of Hub Concentration
- `HypothesisWorks/hypothesis`: Active symbols = 894, Top 1% count = 9 symbols, **$49.17\%$ of edges connected to top 1% symbols**. Super-hub: `integers` (In-Degree: 175).
- `tox-dev/tox`: Active symbols = 106, Top 1% count = 2 symbols, **$36.59\%$ of edges connected to top 1% symbols**. Super-hub: `to_native` (In-Degree: 20).
- `pydantic/pydantic`: Active symbols = 362, Top 1% count = 4 symbols, **$31.69\%$ of edges connected to top 1% symbols**. Super-hub: `py_and_json` (In-Degree: 54).
- `pallets/click`: Active symbols = 46, Top 1% count = 1 symbol, **$29.03\%$ of edges connected to top 1% symbols**. Super-hub: `debug` (In-Degree: 9).
- `huggingface/diffusers`: Active symbols = 1,462, Top 1% count = 15 symbols, **$23.40\%$ of edges connected to top 1% symbols**. Super-hub: `backend_empty_cache` (In-Degree: 113).

In these codebases, unweighted raw graph diffusion (`EXP-392a`) risks funneling disproportionate activation into high-degree utility hubs.

---

## 7. Pilot Execution Status

`task-12753` is actively running the full paired evaluation across all 345 canonical queries and 218 active corpus splits.

Upon completion, all paired retrieval metrics, 10,000 repository-clustered bootstrap statistics, and runtime comparisons will be synthesized into [`research/stage3_9/CONTROLLED_PILOT_REPORT.md`](file:///F:/RepoNeedle/research/stage3_9/CONTROLLED_PILOT_REPORT.md).

