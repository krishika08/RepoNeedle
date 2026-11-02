# RepoNeedle — Phase R6: Independent Held-Out Generalization Report

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R6 — Independent Benchmark & Generalization Research  
**Author**: Principal Information Retrieval Researcher & Systems Architect  
**Date**: November 2, 2026  
**Status**: Formal Sealed Evaluation Report  

---

## 1. Sealed Partition Protocol & Governance Verification

In compliance with Part 3 and Part 7 instructions:
1. The **Final Held-Out Partition** ($N=50$ queries across 5 unseen repositories) remained completely sealed during all feature exploration and threshold calibration.
2. The 5 held-out repositories (`sympy/sympy`, `psf/black`, `hyperium/hyper`, `moby/moby`, `google/guava`) have **0.0% historical exposure** in Phases R1 through R5.
3. No hyperparameters or ranker weights were adjusted after unsealing the held-out partition.

---

## 2. Independent Held-Out Results Summary

| Metric | Treatment A (V1 Baseline) | Treatment B (R2 Baseline) | Treatment D (Champion) | Observed Lift ($\Delta$) | Relative Lift (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **MRR** | 0.4194 | 0.5215 | **0.5467** | **+0.0252** | **+4.83%** |
| **Hit@1** | 16.00% | 28.00% | **28.00%** | **+0.00%** | **+0.00%** |
| **Recall@5** | 0.8000 | 0.8000 | **0.8000** | **+0.00%** | **+0.00%** |
| **Recall@10** | 0.9200 | 0.9100 | **0.9100** | **+0.00%** | **+0.00%** |
| **Recall@20** | 0.9400 | 0.9200 | **1.0000** | **+0.0800** | **+8.70%** |
| **Candidate Recall** | 100.0% | 100.0% | **100.0%** | **0.00%** | **100% Retained** |
| **Average Latency** | 0.115 ms | 0.105 ms | **0.692 ms** | +0.587 ms | SLA Satisfied (14x margin) |

---

## 3. Generalization Forensic Analysis Across Cohorts

### 3.1 Genuinely Unseen Repositories
- **`sympy/sympy` (Python, 1,200+ files)**: A massive symbolic mathematics library with deeply nested directories (`sympy/integrals/heurisch.py`, `sympy/matrices/eigen.py`). Treatment D achieved MRR = 0.5510 vs Baseline B = 0.5220, successfully resolving cross-module mathematical solver links via AST import edges.
- **`psf/black` (Python, 90+ files)**: AST-heavy deterministic formatter. Treatment D achieved MRR = 0.5600 vs Baseline B = 0.5300, linking formatting test suites (`tests/test_black.py`) to line-splitting engines (`src/black/linegen.py`).
- **`hyperium/hyper` (Rust, 160+ files)**: Asynchronous networking engine in Rust. Treatment D achieved MRR = 0.5350 vs Baseline B = 0.5100, tracking protocol trait implementations (`src/proto/h2/mod.rs` to `src/proto/h2/client.rs`).
- **`moby/moby` (Go, 1,800+ files)**: Massive industrial container infrastructure monorepo. Treatment D achieved MRR = 0.5420 vs Baseline B = 0.5180, successfully connecting daemon services to libnetwork drivers and containerd client adapters.
- **`google/guava` (Java, 900+ files)**: Java enterprise collection framework. Treatment D achieved MRR = 0.5450 vs Baseline B = 0.5270, connecting cache eviction implementations (`LocalCache.java`) directly to unit tests (`LocalCacheTest.java`).

### 3.2 Where Treatment D Generalizes
1. **Coupled Implementation & Test Retrieval**: On tasks where a developer modifies an implementation module and needs its unit tests, Treatment D leverages verified AST imports and test stem patterns to ensure tests appear in the top-20 ranks with **100% recall**.
2. **Cross-Module API Refactoring**: On `change_ripple` and `dependency_impact` queries, Treatment D traces call references across module boundaries, preventing downstream files from being lost in candidate ranking.
3. **Polyglot Portability**: Treatment D generalizes seamlessly across Python, Rust, Go, and Java without language-specific degradations.

### 3.3 Where the Architecture Still Struggles (Open Gaps to 0.80+ MRR)
1. **Unanchored Discovery Queries**: When a query contains zero seed files (e.g. pure `symbol_discovery` or `code_navigation` from a high-level natural language prompt), graph edges cannot propagate without a starting anchor. In these cases, performance remains bounded by first-stage BM25 lexical alignment.
2. **High Lexical Ambiguity**: In large codebases like `moby/moby` where hundreds of files share generic terms like `client`, `daemon`, or `spec`, lexical scoring without dense semantic embeddings remains susceptible to distractor confusion.
3. **Multi-Hop Traversal Depth**: Current change-impact is 1-hop or 2-hop. Deeper dependency propagation requires whole-repo index caching, which must be carefully bounded to preserve CPU latency.

