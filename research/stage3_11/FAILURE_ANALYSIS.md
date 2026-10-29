# RepoNeedle Stage 3.11: Failure Analysis and Root-Cause Investigation

**Document**: `research/stage3_11/FAILURE_ANALYSIS.md`  
**Stage**: Stage 3.11 — Function-Level Graph Retrieval Research  
**Date**: October 29, 2026  

---

## 1. Overview of Retrieval Regressions and Ties

While `FUNCTION-GRAPH` achieved 38 wins and improved aggregate MRR from $0.1882$ to $0.1901$ over `CONTROL-CASCADE`, it introduced **24 losses** and left **283 queries (82.0%) as exact ties**. 

This forensic investigation analyzes the root causes of these failure modes to inform future algorithmic refinements.

---

## 2. Categorization of Failure Modes

Across the 24 regression queries, three primary failure mechanisms were identified:

### 2.1 Hub-and-Spoke Utility Sinks (45.8% of Losses, 11 / 24 queries)
- **Mechanism**: General-purpose helper functions (e.g., `format_error`, `validate_params`, `to_dict`, `normalize_path`) defined in utility modules (`utils.py`, `helpers.py`, `compat.py`) are invoked by hundreds of functions across the codebase.
- **Pathology**: When a high-scoring lexical seed calls a utility function, the forward graph edge pushes score into the utility file. Despite degree normalization, the accumulated boost from multiple call sites elevates the utility file into the top 5, displacing the true domain-specific target file.
- **Example**: In repository `pallets/flask`, a query targeting `blueprints.py` had `app.py` as a top lexical seed. `app.py` makes 4 calls into `helpers.py` (`_endpoint_from_view_func`, `find_package`). `helpers.py` jumped from rank 7 to rank 4, pushing `blueprints.py` down from rank 4 to rank 5 (MRR delta $-0.050$).

### 2.2 Sibling Package Distraction (29.2% of Losses, 7 / 24 queries)
- **Mechanism**: In modular packages (e.g., `requests.auth` calling `requests.cookies`), tightly coupled sibling modules exchange verified call edges.
- **Pathology**: When both modules share lexical overlap with the query, graph propagation between siblings can invert their correct relative order, promoting the collaborating module rather than the primary entrypoint.
- **Example**: In `requests`, an authentication query targeted `auth.py`. The top seed `models.py` called `extract_cookies_to_jar` in `cookies.py`. `cookies.py` received a graph boost that moved it ahead of `auth.py` at rank 5, causing an MRR regression.

### 2.3 Dynamic Dispatch and Unresolved Symbols (25.0% of Losses, 6 / 24 queries)
- **Mechanism**: Codebases utilizing dynamic dispatch (`getattr()`, dependency injection containers, factory maps, or RPC reflection) do not contain static AST call sites.
- **Pathology**: Over 2.98 million calls were unresolved statically across the corpus, and 731,300 calls were ambiguous (>3 candidates without qualifying imports). For queries in dynamic architectures (such as `tiangolo/fastapi` route handlers or `tornado` event loop callbacks), the function graph remained completely sparse, defaulting back to file-level BM25 without graph assistance.

---

## 3. Analysis of the Lexical Freeze Paradox

### 3.1 The Freeze as a Protective Mechanism
The Stage 3.9 and 3.10 architecture enforced a rigid safeguard: **the top 3 BM25 candidates were frozen in their exact positions and never re-ranked**.
- In Stage 3.9, this safeguard was essential because heuristic file-level graphs were noisy, and unconstrained graph diffusion corrupted early lexical ranks.
- In Stage 3.11, the safeguard prevented utility hub corruption from damaging ranks 1, 2, and 3.

### 3.2 The Freeze as an Artificial Ceiling
However, the freeze created a critical unintended consequence:
- If BM25 ranked a gold file at rank 4, 5, or 6, and the function-level call graph provided undeniable verified evidence (e.g. direct function call with confidence 1.0) connecting it to the rank 1 seed, **the frozen ranker was forbidden from promoting it into ranks 1, 2, or 3**.
- The maximum possible MRR gain for any query under the freeze was capped at $\frac{1}{4} - \frac{1}{5} = +0.050$.
- When the freeze was relaxed in `FUNCTION-GRAPH-NO-FREEZE`, the model achieved **139 wins and only 23 losses** ($6.04 : 1$ ratio), propelling MRR from $0.1882$ to **$0.2082$** ($+10.6\%$ relative gain).

---

## 4. Recommendations for Stage 3.12

1. **Soft Lexical Anchoring**: Replace the rigid binary Rank 1–3 freeze with a continuous lexical confidence penalty (e.g. requiring graph boost to exceed a dynamic threshold proportional to the BM25 gap before re-ranking rank 1).
2. **In-Degree Hub Attenuation**: Penalize target files whose in-degree across the function graph exceeds the 90th percentile (e.g. scaling boost by $\frac{1}{\log(1 + \text{in\_degree})}$).
3. **Verified-Only Default**: Adopt `FUNCTION-GRAPH-VERIFIED` as the base edge set, discarding unverified Level 2 structural method edges which contributed noise without measurable recall benefit.
