# RepoNeedle Stage 3.9: Cascaded Lexical-First Retrieval Architecture (Candidate G)

**Document ID**: `STAGE3-9-DESIGN-001`  
**Date**: October 2026  
**Stage**: Stage 3.9 Gate B — Cascaded Lexical-First Retrieval Experiment  
**Branch**: `research-program`  
**Base Commit**: `174c260`  
**Implementation**: [`reponeedle/core/cascade.py`](file:///F:/RepoNeedle/reponeedle/core/cascade.py)  

---

## 1. Architectural Motivation & Problem Statement

Stage 3.8 conclusively proved why earlier graph candidates (Candidate C and Candidate F) failed:
1. **The Early-Rank Demotion Vulnerability**: In pure BM25, 21 queries placed gold files at Rank 1 (1.0 RR points) and 34 queries at Rank 2 (0.50 RR points), totaling 38.0 RR points. In Candidate F, graph diffusion and static PageRank demoted gold files in **70 queries** (`BM25_WIN_CAND_DEMOTED`), cutting Rank 1 hits to 7 and Rank 2 hits to 20.
2. **Convex Metric Penalty**: Because Reciprocal Rank $1/r$ is convex, losing 21.0 RR points across ranks 1–2 required 11.25 late-rank promotions for every single demotion. The 25 additional hits gained at ranks 11–20 added only $1.82$ RR points, resulting in a global MRR collapse from $0.1735 \to 0.1351$.
3. **Graph Hub Dilution**: Unnormalized graph diffusion ($0.25$ forward, $0.20$ backward without degree scaling) flooded relevance onto central utility supernodes (e.g. `errors.go`, `config.go`, `types.ts`), which overwhelmed lexical relevance on Go and monorepo codebases.

### Design Objective:
Construct a retrieval architecture that **strictly guarantees BM25 performance as an inviolable lower bound** on ranks 1–3, while unleashing bounded graph expansion to recover relevant files across ranks 4–20.

---

## 2. Core Architectural Principles of the Cascade

```
+-----------------------------------------------------------------------------+
|                               QUERY TEXT                                    |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                     STAGE 1: BM25 LEXICAL RETRIEVAL                        |
| - Computes lexical score for all documents in repository.                   |
| - Deterministic tie-breaking on (-score, filepath).                         |
+-----------------------------------------------------------------------------+
                                       |
                                       v
               +-----------------------+-----------------------+
               |                                               |
               v                                               v
+-------------------------------+             +-------------------------------+
|    TOP-3 LEXICAL FREEZE       |             |   ELIGIBLE CANDIDATE POOL     |
| - Positions 0, 1, 2 locked.   |             | - All documents at rank >= 4. |
| - Zero demotion possible.     |             | - Subject to graph reranking. |
+-------------------------------+             +-------------------------------+
               |                                               |
               |                                               v
               |                      +---------------------------------------+
               |                      | STAGE 2: DEGREE-NORMALIZED EXPANSION  |
               |                      | - Seeds: Top-3 protected files.       |
               |                      | - Symmetric norm: 1/sqrt(d_out * d_in)|
               |                      | - Package boundary fencing.           |
               |                      | - Test-to-implementation discovery.   |
               |                      +---------------------------------------+
               |                                               |
               |                                               v
               |                      +---------------------------------------+
               |                      | STAGE 3: FUSED SORT FOR RANKS >= 4    |
               |                      | - score = 0.60*BM25 + 0.15*Sem + 0.25*|
               |                      | - Doc filter penalty (0.5x).          |
               |                      +---------------------------------------+
               |                                               |
               +-----------------------+-----------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                   FINAL DETERMINISTIC RETRIEVAL RANKING                     |
|                   [r_1, r_2, r_3, r_4_cascaded, r_5_cascaded, ...]          |
+-----------------------------------------------------------------------------+
```

### 2.1 Top-3 Lexical Freeze (MRR Lower-Bound Protection)
- The top $K=3$ documents from pure BM25 are assigned directly to ranks 1, 2, and 3:
  $$\text{FinalRank}[0] = r_1^{(\text{BM25})}, \quad \text{FinalRank}[1] = r_2^{(\text{BM25})}, \quad \text{FinalRank}[2] = r_3^{(\text{BM25})}$$
- **Invariant**: No graph calculation or semantic embedding score can displace the top-3 lexical candidates. This guarantees that all 55 Rank-1 and Rank-2 lexical hits are preserved.

### 2.2 Degree-Normalized Bounded Graph Propagation
For all eligible files $v \in \{d \mid d \notin \text{Top3}\}$:
Using the protected top-3 files as query seeds $u \in \text{Top3}$:
1. **Forward Successor Propagation (Dependencies & Callees)**:
   $$P_{\text{fwd}}(v) = \max_{u \in \text{Top3}, u \to v} \left( S_{\text{BM25}}(u) \cdot 0.25 \cdot \frac{1}{\sqrt{d_{\text{out}}(u) \cdot d_{\text{in}}(v)}} \right)$$
   - *Impact*: When a seed calls a ubiquitous utility hub ($d_{\text{in}}(v) = 100$), the propagation weight is divided by $\sqrt{100} = 10$. The hub receives only $+0.025$ boost, preventing utility dilution.
2. **Backward Predecessor Propagation (Callers & Importers)**:
   $$P_{\text{bwd}}(v) = \max_{u \in \text{Top3}, v \to u} \left( S_{\text{BM25}}(u) \cdot 0.10 \cdot \frac{1}{\sqrt{d_{\text{in}}(u) \cdot d_{\text{out}}(v)}} \right)$$
   - *Impact*: Attenuated by $0.10$ and degree-normalized, preventing reverse energy bleed into unrelated caller modules.

### 2.3 Package & Workspace Boundary Fencing
- Graph edges $(u, v)$ are pruned if $u$ and $v$ belong to disparate, unlinked packages.
- Permitted edges:
  1. Identical directory or direct parent/child hierarchy.
  2. Manifest-declared crate dependencies (e.g. `Cargo.toml` path dependencies or Go module package references).
- Unfenced regex symbol collisions (e.g. two unrelated packages defining `Parse()`) are strictly rejected.

### 2.4 Evidence-Backed Test-to-Implementation Discovery
- Solves the $0.0601$ `code2test` blindspot:
- For any seed file $u$, corresponding test files are discovered via multi-language naming conventions:
  - Go: `foo.go` $\leftrightarrow$ `foo_test.go`
  - Python: `bar.py` $\leftrightarrow$ `test_bar.py`, `tests/test_bar.py`
  - Rust: `baz.rs` $\leftrightarrow$ `tests/baz.rs`, `tests/test_baz.rs`
  - TypeScript: `qux.ts` $\leftrightarrow$ `qux.test.ts`, `__tests__/qux.test.ts`
- Discovered test files receive a targeted linkage boost of $S_{\text{BM25}}(u) \times 0.35$.

### 2.5 Score Fusion for Eligible Ranks ($\ge 4$)
For each file $d \notin \text{Top3}$:
$$S_{\text{cascade}}(d) = 0.60 \cdot S_{\text{BM25}}(d) + 0.15 \cdot S_{\text{sem}}(d) + 0.25 \cdot P_{\text{graph}}(d)$$
If $d$ is a documentation file (`.md`, `.rst`, `doc/`), the score is multiplied by $0.5\times$.
Eligible candidates are sorted by $(-S_{\text{cascade}}(d), \text{filepath})$ and assigned to ranks $4, 5, 6, \dots$.

---

## 3. Ablation Protocol

To isolate the impact of each architectural mechanism, Gate B evaluates seven controlled configurations under identical benchmark conditions:

1. **`BASE-BM25`**: Pure lexical baseline.
2. **`BASE-REPOMAP`**: Pinned official RepoMap (`9e4d689`).
3. **`CAND-C`**: Canonical frozen Candidate C (static PageRank + doc filter).
4. **`CAND-F`**: Canonical Candidate F (unnormalized bidirectional diffusion).
5. **`CAND-CASCADE`**: Full proposed cascade (Top-3 freeze + degree-normalized graph + package fencing + test discovery).
6. **`CASCADE-NO-GRAPH`**: Ablation control: Top-3 freeze + BM25/semantic only, no graph propagation.
7. **`CASCADE-UNNORMALIZED`**: Diagnostic control: Top-3 freeze + unnormalized flat diffusion ($0.25/0.20$).

