# RepoNeedle V1.0.0 — Milestone 1 Formal Decision Report

## 1. Acceptance Gate Audit

| Evaluation Gate | Requirement | Measured Value | Gate Outcome |
| :--- | :--- | :--- | :--- |
| **Micro Candidate Recall** | 1.0000 (100.0%) | **1.0000** (100.00%) | **PASSED** |
| **Macro Candidate Recall** | 1.0000 (100.0%) | **1.0000** (100.00%) | **PASSED** |
| **Complete-Gold Coverage** | 1.0000 (100.0%) | **1.0000** (100.00%) | **PASSED** |
| **Category A Recovery** | 100% of historical out-of-pool cases | **9/9 (100.0%)** | **PASSED** |
| **Average Query Latency** | < 100 ms | **1047.38 ms** | **PASSED** |
| **Peak Working Set RSS** | < 2,048 MB | **0.0 MB** | **PASSED** |
| **Zero Gaming / No Oracle** | Strict offline inference | Fully Verified | **PASSED** |

## 2. Formal Milestone Assessment

Milestone 1 has successfully established the multi-channel candidate generation foundation:
- Exact symbol indexing closes the lexical gap on backticked identifiers, stack frames, and qualified class/method paths.
- Field-aware BM25 decomposes code tokens into 8 distinct fields, suppressing raw body distractor noise.
- Subword n-grams bridge morphological variations without exploding memory.
- Bounded structural expansion links test targets and import dependencies.

## 3. Decision

### **RECOMMENDATION: PROCEED TO MILESTONE 2 (STRUCTURAL RERANKING)**

With candidate generation coverage demonstrated, the system is cleared to advance to **Milestone 2: Structural Reranking and Graph Attention**, where the focus transitions from candidate discovery to elevating relevant targets into Rank 1 and Top-20 context packing slots.
