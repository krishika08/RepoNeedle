# REPONEEDLE V1.0.0 — KNOWN SCIENTIFIC & ENGINEERING LIMITATIONS

**Document ID**: `V1-LIMITATIONS-001`  
**Publication Date**: November 2, 2026  
**Auditor**: Principal Search Engineer & AI Context Engineering Architect  
**Classification**: Public Scientific Disclosure  

---

## 1. Candidate Pool Cutoff & Knapsack Saturation

### Limitation
The production context selection engine operates on a cutoff candidate pool (default: **Top-85 candidates**, configurable via `BudgetConfig.candidate_pool_cutoff`).

### Scientific Analysis
1. In the frozen M1 candidate pool, 100% of gold targets (514/514) exist within the complete unconstrained candidate set.
2. The Top-85 candidates contain 423 of the 514 gold targets (82.30%). The remaining 91 gold targets are positioned between rank 86 and rank 1,200.
3. However, empirical knapsack evaluation across candidate pool sizes (Top-50, Top-85, Top-150, Full Pool) proved that **no candidate ranked beyond position 85 is ever admitted into a packed context** under realistic agent token budgets ($\le 32,768$ tokens):
   - At 4k: Top-85 packed 45 gold targets; Full Pool packed 45 gold targets (**0 delta**).
   - At 8k: Top-85 packed 35 gold targets; Full Pool packed 35 gold targets (**0 delta**).
   - At 32k: Top-85 packed 68 gold targets; Full Pool packed 68 gold targets (**0 delta**).
4. **Root Cause**: The knapsack capacity is exhausted by higher-ranked candidates, and rank-decay utility discounting ($\propto 1/\sqrt{\text{rank}}$) renders deep candidates less dense in utility than top-ranked items.
5. **Operational Tradeoff**: Truncating the candidate scanning pool to Top-85 preserves identical packed context yield while preventing quadratic latency and unbounded memory consumption during AST parsing.

---

## 2. Multi-Target Knapsack Capacity Tradeoffs

### Limitation
Under strict low-token budgets (e.g., 2,048 or 4,096 tokens), packing multiple complete implementation files is mathematically impossible when each file exceeds 1,500 tokens.

### Scientific Analysis
- In benchmark tasks requiring 3 to 6 distinct target files (e.g. `code2test` or `edit2ripple`), a 4,096-token budget provides an average of only 680 to 1,365 tokens per target.
- If full files are forced into the knapsack, only 1 or 2 files fit, displacing the remaining targets entirely (zero coverage for displaced targets).
- **CUD-Pack Compact Mode Solution**: CUD-Pack resolves this via high-density `FOCUS_SPAN` representations ($\le 65$ lines), extracting the focal function, struct, or method along with package/import headers.
- **Limitation**: While this maximizes implementation coverage (Complete Implementation Coverage: 44.06% vs Baseline: N/A), downstream coding agents requiring deep, non-local context outside the focal span may require an expanded budget ($\ge 8,192$ or $16,384$ tokens) under Complete Context Mode.

---

## 3. Heuristic Intent Routing vs. Oracle Task Labels

### Limitation
Automatic intent classification (`TaskType.AUTO`) is heuristic and depends on query text features.

### Scientific Analysis
- In official benchmark evaluations, task labels (`code2test`, `trace2code`, etc.) were supplied directly to the `WorkflowRouter`, yielding high relative gains (+151.7% on `code2test`).
- In unassisted production deployment (`TaskType.AUTO`), the engine inspects natural-language queries for test keywords (`test`, `assert`, `pytest`), trace patterns (`Traceback`, `File "..."`, `panic:`), and edit identifiers (`diff`, `patch`).
- If a user query lacks distinctive markers (e.g., "how does request parsing work?"), the router may default to generic `comment2context`, falling back to standard BM25 + semantic retrieval weights.
- **Guidance for Production Integrations**: Upstream agent orchestrators (Aider, Claude Code, OpenHands) should pass explicit `--task` flags when the workflow context is known out-of-band.

---

## 4. Benchmark Scope vs. Monorepo Scale Boundaries

### Limitation
RepoNeedle V1.0.0 has been rigorously validated on the **Agent Retrieval Bench v2 scope (345 queries across 25 open-source repositories and 218 commit snapshots)**. It does not claim universal 100% retrieval coverage on multi-gigabyte industrial monorepos.

### Scientific Analysis
- Repositories in the ARB v2 benchmark range from 50 to 5,000 files (`etcd`, `gin`, `clap`, `caddy`, `flask`, `requests`, `transformers`, etc.).
- On single-repository codebases up to 20,000 files, RepoNeedle executes in-memory indexing in $< 5$ seconds and retrieves contexts in $< 200\text{ ms}$.
- On multi-gigabyte monorepos (e.g. Google-scale or Chromium-scale codebases with $> 100,000$ files), an in-memory graph and flat candidate generation will encounter indexing bottlenecks. Monorepo deployments require sharded inverted indexes and pre-computed dependency graphs.

---

## 5. Polyglot AST Extraction Boundaries

### Limitation
Deep AST syntax node extraction is native for Python; other languages utilize high-performance structural regex parsers.

### Scientific Analysis
- **Python**: Uses Python's native `ast` module for exact AST walk, docstring extraction, and node boundary detection.
- **Go, Rust, TypeScript, JavaScript, Java, C, C++**: Uses fast regex pattern matchers for function headers, class/struct definitions, and interface signatures.
- **Other / Plain Text Files**: Falls back to raw keyword windowing around query term occurrences.
- While structural regex achieves $> 95\%$ accuracy on common syntax definitions across Go and Rust (as verified in our polyglot tests), complex multi-line macros, heavily nested lambdas, or unconventional formatting may result in approximate span boundaries.

---

## 6. Interpretation of Evaluation Suites

### Disclosure
- The 20-query `curated_cud_pack_regression_suite.json` is a **curated integration regression test**, not an independent statistical evaluation sample. It was constructed to verify specific implementation span boundaries and prevent regressions.
- The 20-query `held_out_cud_pack_evaluation_suite.json` was drawn from 4 previously uninspected repositories (`caddyserver/caddy`, `pallets/click`, `tokio-rs/tokio`, `pytest-dev/pytest`) and achieved 95.0% pass rate.
- Neither 20-query suite should be extrapolated as a replacement for the full 345-query Agent Retrieval Bench v2 statistical distribution.

