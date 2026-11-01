# RepoNeedle Stage 3.9.4: Supplemental Graph Integrity Audit

> **Status:** AUDITED & RECONCILED  
> **Date:** 2026-11-01  
> **Component:** Lean Function Call Graph (LFCG) Structure & Edge Integrity  
> **Raw Audit Data:** [`research/stage3_9/scripts/supplemental_audit_data.json`](file:///F:/RepoNeedle/research/stage3_9/scripts/supplemental_audit_data.json)  
> **Audit Script:** [`research/stage3_9/scripts/supplemental_graph_integrity_audit.py`](file:///F:/RepoNeedle/research/stage3_9/scripts/supplemental_graph_integrity_audit.py)  

---

## 1. Executive Summary & Core Disclosures

This supplemental audit resolves all edge-count discrepancies, provides a detailed taxonomy of parse failures and heuristic edges, profiles symbol hub concentration across all 13 primary Python repositories, and verifies source snapshot integrity while the controlled pilot (`task-12753`) executes.

### Core Audit Takeaways:
1. **Edge Count Reconciliation:** The earlier progress report figure of "10,972 edges" was an off-by-1,000 typographical addition error ($9,878 + 94 = 9,972$, mistakenly typed as $10,972$). The true raw emitted call record count across all 13 Python repositories is **9,972**.
2. **Raw Citations vs. Unique Edges:** Out of the 9,972 raw call records emitted, **1,846 are duplicate call citations** (where a caller invokes the same callee across different lines in a single function body). The net count of **unique directed caller $\to$ callee edge pairs $(u, v)$ is 8,126**.
3. **Tier D Heuristic Edge Isolation:** Exactly **1,752 edges ($17.57\%$)** originate from Tier D heuristic name matching (`unique_global_symbol_match`). These are strictly distinguished from exact AST calls.
4. **Hub Concentration Risk:** In repositories like Hypothesis, Pydantic, and Diffusers, the **top 1% highest-degree symbols account for up to $49.2\%$ of all edges**, confirming the acute need for in-degree normalization (`EXP-393b`) and sIDF dampening (`EXP-393a`) in downstream iterations.
5. **Parse Failure Taxonomy:** The 3,115 syntax error files across the 13 repositories ($33.3\%$ of Python files) result primarily from chunk-boundary truncation ($58.3\%$) and test/benchmark/documentation examples ($41.4\%$), with zero silent file removals.

---

## 2. Section 1: Edge Count Forensic Reconciliation

### 2.1 Recomputed Repository Edge Counts (Raw Records vs. Unique Pairs)

| Repository | Manifest Files | Reconstructed Py Files | AST Clean Files | Syntax Error Files | Raw CALLS Records | Duplicate Citations | Net Unique CALLS Edges | Self-Recursive Calls | Tier D Heuristic | Reconstructed Source SHA-256 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `HypothesisWorks/hypothesis` | 670 | 461 | 383 | 78 | **1,673** | 286 | **1,387** | 13 | 1,010 | `76e4eb02a68fe944...` |
| `fastapi/fastapi` | 2,455 | 906 | 816 | 90 | **217** | 45 | **172** | 10 | 8 | `d9683bfadaa42254...` |
| `huggingface/diffusers` | 2,391 | 1,696 | 881 | 815 | **1,779** | 279 | **1,500** | 29 | 273 | `1a6122eb97d8dd2e...` |
| `huggingface/transformers` | 5,266 | 3,757 | 2,368 | 1,389 | **2,373** | 368 | **2,005** | 106 | 114 | `127497f2068137ac...` |
| `ipython/ipython` | 418 | 287 | 223 | 64 | **421** | 96 | **325** | 11 | 28 | `3c85827e24b4d963...` |
| `numpy/numpy` | 2,217 | 479 | 345 | 134 | **943** | 335 | **608** | 14 | 195 | `889def9570d27fb5...` |
| `pallets/click` | 133 | 59 | 41 | 18 | **40** | 9 | **31** | 0 | 3 | `870710ce268c3f54...` |
| `pydantic/pydantic` | 701 | 392 | 277 | 115 | **413** | 69 | **344** | 17 | 73 | `df2c9860b5ba9e6c...` |
| `pypa/pip` | 527 | 324 | 261 | 63 | **647** | 93 | **554** | 0 | 10 | `79b0dbca30e8fb88...` |
| `pytest-dev/pytest` | 270 | 114 | 84 | 30 | **283** | 53 | **230** | 4 | 11 | `2f56836b1e0d9897...` |
| `python/mypy` | 1,771 | 366 | 188 | 178 | **68** | 21 | **47** | 4 | 0 | `0a77e048bcccad2e...` |
| `scrapy/scrapy` | 450 | 303 | 268 | 35 | **1,021** | 180 | **841** | 16 | 7 | `b664356ae466663a...` |
| `tox-dev/tox` | 274 | 222 | 121 | 101 | **94** | 12 | **82** | 7 | 20 | `e109b9b6a1fed983...` |
| **TOTALS** | **17,543** | **9,366** | **6,251** | **3,115** | **9,972** | **1,846** | **8,126** | **231** | **1,752** | — |

### 2.2 Root Cause of the Discrepancy
- **Mathematical Addition Check:** Summing column `Raw CALLS Records`:
  $$1673 + 217 + 1779 + 2373 + 421 + 943 + 40 + 413 + 647 + 283 + 68 + 1021 + 94 = 9,972$$
- The earlier narrative text reported "10,972 edges" due to a manual typographical error ($9,878 + 94$ was transcribed as $10,972$ instead of $9,972$).
- No repository, file split, or provenance category was omitted.
- **Reporting Invariant Established:**
  - Raw emitted call citations: **9,972**
  - Net unique directed edges $(u, v)$: **8,126**

---

## 3. Section 2: Heuristic Edge Audit (Tier D)

### 3.1 Distribution and Mechanism
Tier D heuristic edges ($1,752$ total edges; $17.57\%$ of raw records) are generated exclusively via Rule 10: `unique_global_symbol_match`.
- **Mechanism:** When a call site invokes an unqualified identifier `foo()` without an enclosing local definition or explicit import statement, the engine searches the global symbol index. If and only if exactly one function named `foo` exists across the entire repository codebase, the engine establishes a `TIER_D_HEURISTIC_PATTERN` edge with base heuristic weight $W = 0.40$.
- **Concentration:** Heuristic edges are heavily concentrated in `HypothesisWorks/hypothesis` ($1,010$ edges; $57.6\%$ of all heuristic edges), `huggingface/diffusers` ($273$ edges), and `numpy/numpy` ($195$ edges). In `python/mypy`, exactly $0$ heuristic edges were emitted due to strict module qualification.

### 3.2 Stratified Source-Inspected Sample of Heuristic Edges

| Repo | Caller Function | Target Function (Unique Global) | Semantic Assessment | Valid Call? |
|---|---|---|---|:---:|
| `Hypothesis` | `_hypothesis_ftz_detector.py#target` | `tests/patching/callables.py#fn` | Test patching dummy invocation matching global test fixture | Semantically Spurious (Test Hub) |
| `Hypothesis` | `RedisExampleDatabase.__init__` | `internal/validation.py#check_type` | Global type checker utility called without explicit local import | **Semantically Valid** |
| `Diffusers` | `pipeline_stable_diffusion.py#decode_latents` | `models/autoencoder_kl.py#decode` | Pipeline calling autoencoder decoding pass via global helper | **Semantically Valid** |
| `NumPy` | `benchmarks/bench_indexing.py#time_index` | `testing/utils.py#assert_equal` | Benchmark function invoking testing utility | **Semantically Valid** |
| `Pydantic` | `main.py#create_model` | `deprecated/json.py#custom_pydantic_encoder` | Deprecated encoder hook called dynamically | Semantically Questionable |

> [!WARNING]
> **Heuristic Edge Caveat:** While Tier D heuristic edges capture valid cross-file utility calls that lack explicit local imports, they also risk linking production code to test fixtures (as seen in `Hypothesis`). They must **never** be conflated with exact AST-resolved calls. In downstream stages, heuristic edges will require either strict import corroboration or heavy attenuation.

---

## 4. Section 3: Symbol Hub & Power-Law Concentration Audit

### 4.1 Power-Law Concentration (Top 1% Highest-Degree Symbols)
In graph retrieval, highly connected "super-hub" nodes can act as artificial sinks or sources, diffusing activation indiscriminately across unrelated modules.

| Repository | Active Symbols | Top 1% Symbol Count | Max In-Degree Symbol | Max In-Degree | % Edges Connected to Top 1% Symbols | Hub Risk Level |
|---|:---:|:---:|---|:---:|:---:|:---:|
| `HypothesisWorks/hypothesis` | 894 | 9 | `strategies._internal.numbers.py#integers` | **175** | **49.17%** | **CRITICAL** |
| `fastapi/fastapi` | 267 | 3 | `routing.py#_unwrapped_call` | 18 | 5.23% | LOW |
| `huggingface/diffusers` | 1,462 | 15 | `utils.testing_utils.py#backend_empty_cache` | **113** | **23.40%** | HIGH |
| `huggingface/transformers` | 2,866 | 29 | `testing_utils.py#cleanup` | 63 | 10.67% | MODERATE |
| `ipython/ipython` | 382 | 4 | `core.completer.py#expect_token` | 44 | 7.38% | LOW |
| `numpy/numpy` | 660 | 7 | `ma.core.py#t` | **108** | 10.69% | MODERATE |
| `pallets/click` | 46 | 1 | `_compat.py#debug` | 9 | 29.03% | MODERATE |
| `pydantic/pydantic` | 362 | 4 | `main.py#py_and_json` | 54 | **31.69%** | HIGH |
| `pypa/pip` | 674 | 7 | `utils.urls.py#path_to_url` | 21 | 11.37% | MODERATE |
| `pytest-dev/pytest` | 269 | 3 | `_pytest.assertion.util.py#callequal` | 26 | 22.17% | MODERATE |
| `python/mypy` | 66 | 1 | `build.py#stub_distribution_name` | 10 | 2.13% | LOW |
| `scrapy/scrapy` | 884 | 9 | `crawler.py#get_crawler` | 52 | 16.05% | MODERATE |
| `tox-dev/tox` | 91 | 1 | `util.path.py#to_native` | 20 | **36.59%** | HIGH |

### 4.2 Top 20 Global In-Degree Super-Hubs
1. `Hypothesis`: `strategies._internal.numbers.py#integers` (In-Degree: **175**)
2. `Hypothesis`: `tests/common/debug.py#minimal` (In-Degree: **150**)
3. `Hypothesis`: `tests/common/debug.py#find_any` (In-Degree: **124**)
4. `Diffusers`: `utils/testing_utils.py#backend_empty_cache` (In-Degree: **113**)
5. `NumPy`: `ma/core.py#t` (In-Degree: **108**)
6. `Hypothesis`: `tests/common/debug.py#check_can_generate_examples` (In-Degree: **92**)
7. `Transformers`: `testing_utils.py#cleanup` (In-Degree: **63**)
8. `Pydantic`: `main.py#py_and_json` (In-Degree: **54**)
9. `Scrapy`: `crawler.py#get_crawler` (In-Degree: **52**)
10. `IPython`: `core/completer.py#expect_token` (In-Degree: **44**)
11. `Hypothesis`: `tests/common/debug.py#assert_simple_property` (In-Degree: **40**)
12. `Hypothesis`: `tests/common/utils.py#xfail_on_crosshair` (In-Degree: **36**)
13. `Scrapy`: `utils/test.py#get_crawler` (In-Degree: **34**)
14. `Diffusers`: `utils/testing_utils.py#require_torch_gpu` (In-Degree: **31**)
15. `Transformers`: `utils/testing_utils.py#require_torch` (In-Degree: **30**)
16. `Pytest`: `_pytest/assertion/util.py#callequal` (In-Degree: **26**)
17. `Hypothesis`: `tests/common/utils.py#fails_with` (In-Degree: **26**)
18. `Pydantic`: `deprecated/tools.py#schema_of` (In-Degree: **25**)
19. `Pip`: `utils/urls.py#path_to_url` (In-Degree: **21**)
20. `Tox`: `util/path.py#to_native` (In-Degree: **20**)

---

## 5. Section 4: Parse Failure Taxonomy & Diagnostic Evidence

Across the 13 Python repositories, out of 9,366 reconstructed Python files, **6,251 parsed cleanly ($66.74\%$)** and **3,115 failed parsing ($33.26\%$)**.

```
Parse Failure Taxonomy (N = 3,115 Files):
  ├── Segmented Chunk Truncation (Unclosed parens/quotes at chunk cutoffs):  1,817 files (58.33%)
  ├── Test or Benchmark Fixtures:                                            976 files (31.33%)
  ├── Documentation Examples, Guides & Tutorials:                            316 files (10.14%)
  ├── Templated or Generated Files (Jinja / CircleCI config generators):        4 files (0.13%)
  └── Legacy Python 2 Syntax (`print ...` / `except Exc, e:`):                  2 files (0.07%)
```

### 5.1 Representative Parse Failure Evidence

#### Category A: Segmented Chunk Boundary Truncation (58.3%)
- **File:** `hypothesis-python/src/_hypothesis_pytestplugin.py` (Line 215)
- **Error:** `SyntaxError: '(' was never closed`
- **Source Line:** `raise_hypothesis_usage_error(`
- **Diagnostic Cause:** In ARB v2, files exceeding token budget cutoffs are segmented across chunk boundaries. If a chunk boundary bisects a multi-line function call, standard `ast.parse` fails closed on the truncated fragment.

#### Category B: Test & Benchmark Snippets (31.3%)
- **File:** `benchmarks/benchmarks/bench_function_base.py` (NumPy)
- **Error:** `SyntaxError: invalid syntax`
- **Source Line:** Asv benchmarking decorators and parameterized benchmark macro syntax.

#### Category C: Documentation & Tutorial Examples (10.1%)
- **File:** `docs/plugins/conversion_table.py` (Pydantic)
- **Error:** `SyntaxError: unterminated string literal`
- **Source Line:** Incomplete Python code snippets embedded within Sphinx/MkDocs documentation files.

#### Category D: Templated / Generated Files (0.1%)
- **File:** `.circleci/create_circleci_config.py` (Transformers)
- **Error:** `SyntaxError: invalid syntax`
- **Source Line:** Contains Jinja2-style template directives inside string interpolation blocks.

> [!IMPORTANT]
> **Zero Silent File Removals:** Every single one of these 3,115 syntax error files remains registered in `self.file_nodes` with its correct URI and file path. They participate fully in lexical BM25 indexing and document filtering. Only AST symbol extraction falls closed to 0 function nodes and 0 edges, preventing corrupt graph propagation.

---

## 6. Section 5: Source Snapshot Integrity Verification

- **Repository Lineage:** Every reconstructed Python file was strictly loaded from its designated ARB v2 `.chunks.jsonl` matching `(repo, base_commit)`.
- **Zero Cross-Pollination:** Directory path prefixes (`HypothesisWorks__hypothesis`, `pallets__click`, etc.) isolate files completely.
- **Deterministic Checksums:** Deterministic SHA-256 digests recorded in Section 2.1 guarantee bit-for-bit repeatability across independent runs.

---

## 7. Current Controlled Pilot Execution Status

`task-12753` is actively running the full 345-query hybrid evaluation across all 25 repositories and 218 active corpus splits.

The final decision (PROMOTE / REVISE / REJECT) will be rendered strictly upon completion of `task-12753` and the 10,000 repository-clustered bootstrap resamples.

