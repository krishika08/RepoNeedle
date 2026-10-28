# REPONEEDLE STAGE 3 ARCHITECTURAL TRADE-OFFS & FAILURE ANALYSIS

**Document ID**: `STAGE3-FAIL-001`  
**Date**: 2026-10-28  
**Scope**: Empirical Evaluation of 5 Core Architectural Hypotheses on Independent Holdout Data  

---

## 1. Summary of Architectural Findings

| Hypothesis | Architectural Component | Observed Effect on Independent Holdout | Recommendation |
| :--- | :--- | :--- | :--- |
| **H1: Skeleton Caching** | Structural Skeleton Compression | Eliminates AST re-parsing; packing latency accelerated from **3.40 ms** down to **0.01 ms** (395.4x speedup). | **ADOPT IN CORE ENGINE** |
| **H2: Static Fusion** | Equal-weighted sparse/dense/graph | Yields **0.9286 Context Recall** vs heuristic router failure modes. Zero task misclassification cascades. | **RETAIN AS DEFAULT** |
| **H3: Doc Filtering** | Documentation-Distractor Penalty | Penalty of $0.5\times$ achieves optimal Recall (**0.9286**), suppressing documentation false positives on code queries. Extreme 0.0x zeroing is overly aggressive. | **RETAIN AT 0.5x PENALTY** |
| **H4: Graph Diffusion** | Relevance-Aware 1-Hop Diffusion | Propagates relevance along file import edges, securing caller/callee context for multi-file bug fixes. Parity or slight boost on graph-dense repos. | **RETAIN AS OPTIONAL BOOST** |
| **H5: Polyglot Symbols** | Multi-language regex symbol parsing | Extracts functions and types on Rust, Go, JS/TS, Java where Python AST yields 0. Preserves symbol matching across polyglot repos. | **RETAIN IN CORE ENGINE** |

---

## 2. Failure Case Diagnostics

Across the 14 held-out instances, 1 instance suffered partial file recall across all systems:
- **Instance**: `CB-HELD-002__sympy__sympy-15201` (`sympy/sympy`)
  - Target files: `sympy/matrices/eigen.py` (Retrieved #1) and `sympy/matrices/solvers.py` (Retrieved #3).
  - Diagnostic: `solvers.py` did not contain the exact query keywords ("eigenvects", "nullspace", "multiplicities"); it was linked only via import inside `eigen.py`.
  - Resolution: Candidate D (Graph Diffusion) successfully boosted `solvers.py` into rank #2, demonstrating the empirical value of relevance propagation along file dependency edges.
