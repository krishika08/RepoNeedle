# RepoNeedle Stage 3.9.4.1: Symbol Fragment Recovery & Retrieval Coverage Investigation

> **Status:** INVESTIGATION COMPLETED & VALIDATED  
> **Date:** 2026-11-01  
> **Component:** ARB v2 Symbol Fragment AST Recovery & Safe Resolution Engine  
> **Data Artifact:** [`research/stage3_9/scripts/symbol_fragment_recovery_results.json`](file:///F:/RepoNeedle/research/stage3_9/scripts/symbol_fragment_recovery_results.json)  
> **Prototype File:** [`research/stage3_9/prototypes/symbol_fragment_recovery_engine.py`](file:///F:/RepoNeedle/research/stage3_9/prototypes/symbol_fragment_recovery_engine.py)  

---

## 1. Executive Summary & Investigation Mandate

In Stage 3.9.4, structural coverage analysis revealed a significant structural reachability bottleneck across the ARB v2 benchmark:
- Out of 9,366 reconstructed Python files, **3,115 files ($33.26\%$)** failed full-file AST parsing.
- **2,451 of those failures ($78.68\%$)** resulted from segmented chunk-boundary truncation (e.g. unclosed parentheses or multi-line string cuts where files exceeded chunk budget cutoffs).
- Consequently, only **37 out of 104 Python queries ($35.58\%$)** had at least one gold target file cleanly parsed into the symbol graph, and only **24 out of 145 gold files ($16.55\%$)** possessed active `CALLS` edge connectivity. In `trace2code` and `edit2ripple`, exactly **0 gold files** were connected to graph edges.

### Objective
This investigation evaluated whether original `kind == "symbol"` chunks in ARB v2 can be safely parsed in isolation to recover function-level representations without fabricating synthetic module source or relaxing fail-closed precision.

### Key Investigation Findings
1. **Fragment Recovery Yield:** Out of 390,277 symbol chunks inspected across all 13 Python repositories, **20,022 complete functions**, **486 async functions**, and **46,868 methods** were successfully parsed in isolation, yielding **+67,376 recovered function nodes**.
2. **Gold Target File Recovery:** Gold file function representation increased from **46 files ($31.72\%$)** to **133 files ($91.72\%$)**, providing function nodes for 103 out of 104 queries.
3. **The Missing-Context Resolution Bottleneck:** Because isolated symbol chunks lack the enclosing module's `import` statements and outer class scope, **$99.98\%$ of extracted call sites inside fragments cannot be resolved fail-closed** ($184,025$ require unavailable type/receiver info; $52,264$ require unavailable module imports). Only **52 valid fragment-local recursive or nested calls** could be resolved.
4. **Architectural Verdict:** Fragment recovery succeeds at creating isolated `FunctionNode` vertices, but produces virtually **zero new graph connectivity (+52 edges total across 390k chunks)**. The recovered nodes remain "islands" that cannot transmit diffusion activation. Generating additional edges from fragments would require speculative global name guessing, which directly violates fail-closed retrieval principles.

---

## 2. Symbol Fragment Taxonomy & Analysis

All 390,277 `kind == "symbol"` chunks across the 13 Python repositories were analyzed and classified:

```
ARB v2 Symbol Chunks Taxonomy (N = 390,277 Chunks):
  ├── Truncated Functions / Syntax Errors:              252,338 chunks (64.66%)
  ├── Partial Code Fragments (Control blocks / Stmts):   58,372 chunks (14.96%)
  ├── Methods Missing Class Context (`self`/`cls`):      46,868 chunks (12.01%)
  ├── Complete Standalone Function Definitions:          20,022 chunks  (5.13%)
  ├── Complete Class Declarations:                       12,191 chunks  (3.12%)
  └── Complete Async Function Definitions:                  486 chunks  (0.12%)
  [Duplicate Symbol Chunks across snapshots: 170,803]
```

### 2.1 Per-Repository Fragment Distribution Table

| Repository | Inspected Chunks | Complete Functions | Complete Async Funcs | Methods Missing Class Context | Class Declarations | Partial Code Fragments | Truncated / Syntax Errors | Duplicate Symbols |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `HypothesisWorks/hypothesis` | 15,953 | 1,890 | 7 | 758 | 287 | 3,474 | 9,544 | 6,810 |
| `fastapi/fastapi` | 7,601 | 2,129 | 431 | 86 | 321 | 510 | 4,126 | 2,050 |
| `huggingface/diffusers` | 95,200 | 2,335 | 3 | 7,813 | 1,559 | 11,994 | 72,498 | 43,107 |
| `huggingface/transformers` | 148,881 | 3,940 | 12 | 21,606 | 5,287 | 14,033 | 104,005 | 57,898 |
| `ipython/ipython` | 9,194 | 1,049 | 14 | 1,232 | 292 | 1,465 | 5,142 | 3,566 |
| `numpy/numpy` | 44,896 | 1,554 | 6 | 5,902 | 499 | 16,011 | 19,934 | 28,539 |
| `pallets/click` | 2,260 | 233 | 0 | 267 | 52 | 290 | 1,420 | 891 |
| `pydantic/pydantic` | 22,037 | 2,306 | 2 | 1,192 | 2,510 | 3,086 | 12,935 | 10,108 |
| `pypa/pip` | 6,685 | 1,087 | 0 | 909 | 172 | 1,121 | 3,396 | 2,012 |
| `pytest-dev/pytest` | 7,169 | 858 | 0 | 1,082 | 146 | 726 | 4,126 | 2,516 |
| `python/mypy` | 19,658 | 1,421 | 0 | 3,447 | 481 | 4,148 | 10,401 | 10,671 |
| `scrapy/scrapy` | 6,942 | 237 | 11 | 2,169 | 506 | 865 | 2,968 | 1,714 |
| `tox-dev/tox` | 3,801 | 983 | 0 | 405 | 79 | 649 | 1,843 | 921 |
| **TOTALS** | **390,277** | **20,022** | **486** | **46,868** | **12,191** | **58,372** | **252,338** | **170,803** |

---

## 3. Safe Fragment Parsing Prototype Architecture

The prototype [`research/stage3_9/prototypes/symbol_fragment_recovery_engine.py`](file:///F:/RepoNeedle/research/stage3_9/prototypes/symbol_fragment_recovery_engine.py) implements the following constraints:
1. **Isolated Ast Ingestion:** Each symbol chunk is dedented via `textwrap.dedent()` and passed to `ast.parse()`. Only nodes where the root AST body is an `ast.FunctionDef`, `ast.AsyncFunctionDef`, or `ast.ClassDef` are registered.
2. **Metadata Preservation:** Every recovered node preserves:
   - `repo`: Canonical repository identifier.
   - `base_commit`: Commit hash associated with the chunk file.
   - `path`: Normalized repository relative file path.
   - `symbol`: Declared symbol name from chunk metadata.
   - `start_line` / `end_line`: Original source line offsets from ARB v2.
   - `fragment_sha256`: SHA-256 digest of the raw fragment text.
3. **Absence of Module Pretension:** The engine explicitly acknowledges that isolated fragments do **not** possess the file's top-level `import` statements or outer class definitions.

---

## 4. Resolution Policy & The Missing-Context Bottleneck

When extracting call sites from recovered symbol fragments, the resolver applied the fail-closed resolution policy:

| Call-Site Classification | Resolution Mechanism | Emitted Edge Action | Extracted Call Count | % of Fragment Calls |
|---|---|---|:---:|:---:|
| **Fragment-Local Recursive Call** | Caller invokes itself directly inside fragment | Emits `TIER_A_EXACT_AST` | **52** | $0.02\%$ |
| **Unavailable Module Imports** | Call to imported function lacking file-level `import` table | Marked `UNRESOLVED` (Tier E) | **52,264** | $22.05\%$ |
| **Unavailable Class Scope** | Method call on `self` lacking enclosing class definition | Marked `UNRESOLVED` (Tier E) | **63** | $0.03\%$ |
| **Unavailable Runtime / Type Info** | Receiver attribute call `obj.foo()` lacking type info | Marked `UNRESOLVED` (Tier E) | **184,025** | $77.63\%$ |
| **Dynamic Dispatch** | `getattr()`, `locals()()`, subscript invocations | Marked `UNRESOLVED` (Tier E) | **711** | $0.30\%$ |
| **TOTAL EXTRACTED CALL SITES** | — | — | **237,115** | **100.0%** |

### The Critical Resolution Bottleneck
Across 237,115 extracted call sites inside recovered fragments:
- **236,252 call sites ($99.98\%$)** cannot be resolved fail-closed.
- $52,264$ calls reference functions that were imported at the top of the original module. Because symbol chunks do not contain the module's import header, the target file cannot be determined without speculative guessing.
- Only **52 calls ($0.02\%$)** were self-recursive or nested helper invocations.

---

## 5. Coverage Recalculation: Before vs. After

Using benchmark gold labels strictly for evaluation, we measured the coverage impact of symbol fragment recovery:

### 5.1 Gold Target File Representation (Before vs. After)

| Repository | Active Queries | Gold Files Total | Cleanly Parsed Gold Files (Full-File Baseline) | Recovered Gold Files w/ Functions (Fragment Recovery) | Net Gold File Recovery Delta |
|---|:---:|:---:|:---:|:---:|:---:|
| `HypothesisWorks/hypothesis` | 1 | 2 | 0 (0.0%) | **2 (100.0%)** | +2 (+100%) |
| `fastapi/fastapi` | 3 | 5 | 5 (100.0%) | 5 (100.0%) | 0 (0%) |
| `huggingface/diffusers` | 16 | 31 | 11 (35.5%) | **27 (87.1%)** | +16 (+51.6%) |
| `huggingface/transformers` | 36 | 44 | 18 (40.9%) | **43 (97.7%)** | +25 (+56.8%) |
| `ipython/ipython` | 2 | 2 | 0 (0.0%) | **2 (100.0%)** | +2 (+100%) |
| `numpy/numpy` | 1 | 2 | 2 (100.0%) | 2 (100.0%) | 0 (0%) |
| `pallets/click` | 26 | 30 | 1 (3.3%) | **30 (100.0%)** | +29 (+96.7%) |
| `pydantic/pydantic` | 1 | 1 | 0 (0.0%) | **1 (100.0%)** | +1 (+100%) |
| `pypa/pip` | 5 | 9 | 5 (55.6%) | **9 (100.0%)** | +4 (+44.4%) |
| `pytest-dev/pytest` | 7 | 12 | 1 (8.3%) | **5 (41.7%)** | +4 (+33.3%) |
| `python/mypy` | 1 | 1 | 0 (0.0%) | **1 (100.0%)** | +1 (+100%) |
| `scrapy/scrapy` | 3 | 4 | 2 (50.0%) | **4 (100.0%)** | +2 (+50.0%) |
| `tox-dev/tox` | 2 | 2 | 1 (50.0%) | **2 (100.0%)** | +1 (+50.0%) |
| **TOTALS** | **104** | **145** | **46 (31.72%)** | **133 (91.72%)** | **+87 (+60.0%)** |

### 5.2 Task Track Breakdown

| Task Track | Total Queries | Gold Files Total | Baseline Parsed Gold Files | Fragment-Recovered Gold Files | Baseline Queries w/ Gold Function | Fragment-Recovered Queries w/ Gold Function |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `comment2context` | 40 | 62 | 22 (35.5%) | **57 (91.9%)** | 16 (40.0%) | **40 (100.0%)** |
| `code2test` | 27 | 40 | 19 (47.5%) | **37 (92.5%)** | 16 (59.3%) | **27 (100.0%)** |
| `edit2ripple` | 10 | 12 | 4 (33.3%) | **9 (75.0%)** | 4 (40.0%) | **10 (100.0%)** |
| `trace2code` | 27 | 31 | 1 (3.2%) | **30 (96.8%)** | 1 (3.7%) | **27 (100.0%)** |
| **ALL TRACKS** | **104** | **145** | **46 (31.72%)** | **133 (91.72%)** | **37 (35.58%)** | **104 (100.0%)** |

---

## 6. Engineering Cost & Recommendation

### 6.1 Computational & Memory Cost
- **Node Growth:** Adding recovered fragment functions increases graph vertices from 29,324 to **96,700 nodes ($+230\%$)**.
- **Memory Footprint:** Peak process heap increases by **$+118.4\text{ MB}$**, approaching the $250\text{ MB}$ engineering ceiling on large repositories.
- **Indexing Latency:** Sifting, dedenting, and parsing 390,277 symbol chunks adds **$+42.6\text{ seconds}$** of indexing overhead per snapshot.

### 6.2 Architectural Verdict: NOT RECOMMENDED FOR RETRIEVAL PILOT
While fragment recovery successfully elevates gold-target FunctionNode presence from $35.58\%$ to $100.0\%$, it creates an **unconnected "orphan node" graph**:
1. Because isolated fragments lack import headers and class scopes, $99.98\%$ of calls cannot be resolved fail-closed.
2. Only 52 new call edges are emitted across 390,277 chunks.
3. Without incoming or outgoing edges, recovered function nodes cannot receive or propagate diffusion activation during 2-hop graph propagation.
4. Attempting to artificially link these nodes via global symbol name matching would re-introduce catastrophic false-positive edge injection.

### Conclusion
Fragment recovery is valuable as an offline indexing diagnostic, but **must NOT be integrated into the active retrieval pipeline**. The active `EXP-392a` / `EXP-392b` pilot remains isolated and protected.

