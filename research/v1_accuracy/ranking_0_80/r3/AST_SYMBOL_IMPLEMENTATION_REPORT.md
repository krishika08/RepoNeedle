# REPONEEDLE MISSION 0.80+ — PHASE R3
# DELIVERABLE 4: AST SYMBOL IMPLEMENTATION & EXPERIMENTAL REPORT

**Author**: Principal Information Retrieval Engineer, Systems Implementation Lead  
**Date**: November 2, 2026  
**Status**: APPROVED & FROZEN  
**Target Milestone**: Phase R3 (AST Symbol Intelligence + BM25L Ranking)  

---

## 1. IMPLEMENTATION SUMMARY

The AST Symbol Intelligence subsystem has been fully implemented in:
- `research/v1_accuracy/ranking_0_80/r3/src/ast_symbol.py`
- Integrated into `research/v1_accuracy/ranking_0_80/r3/src/ranker_r3.py`

### 1.1 Core Modules & Lineage

| Module | Purpose | Key Methods | Complexity |
| :--- | :--- | :--- | :---: |
| `IdentifierTokenizer` | Polyglot identifier decomposition | `split_identifier()`, `extract_symbols()` | $O(\|q\|)$ |
| `ASTIntentClassifier` | Query intent taxonomy classification | `classify(query_text, test_prob)` | $O(\|q\|)$ |
| `ASTSymbolMatcher` | Intent-conditioned asymmetric definition boosting | `score_candidate()` | $O(1)$ |

---

## 2. ABLATION EXPERIMENTS & ARCHITECTURAL DISCOVERIES

### 2.1 The Unconditional Boosting Failure
Initial experimentation tested a naive AST definition boost: multiplying any candidate with $s_{\text{exact}} > 0$ by $(1 + \alpha \cdot \ln(1 + s_{\text{exact}}))$ across all queries.

**Empirical Result**:
- Validation MRR dropped sharply from **0.2971 down to 0.2436** (Hit@1 dropped from 16.67% to 10.00%).
- **Root Cause Analysis**: In `code2test` queries, the query contains modified code snippets and function declarations. Consequently, the implementation files in the repository have massive $s_{\text{exact}}$ scores. However, the user is looking for **test files**! Unconditionally boosting code definitions pushed the target test suites down below implementation distractors.

### 2.2 Discovery in Traceback Queries (`trace2code`)
An audit across all 101 `trace2code` queries revealed:
- **Total Gold Targets**: 127 files.
- **Test File Gold Targets**: Exactly **0 / 127 (0.0%)**.
- **Implementation File Gold Targets**: Exactly **127 / 127 (100.0%)**.

When a test runner or build fails, developers provide terminal logs (e.g. `FAIL go.etcd.io/etcd/cache/v3 [build failed]` or `tests/coverage_test.go:45`). Because the query mentions test paths and the word "test", naive BM25 and lexical search placed test files at Rank 1.
By introducing the `implementation_seeking` routing rule:
- Test candidates are demoted ($\times 0.05$).
- Implementation candidates containing the failing symbol definition are boosted.

### 2.3 Conditioned Intent Routing Results
When AST boosting was conditioned on intent:

| Configuration | Validation MRR | Validation Hit@1 | Train MRR | Candidate Recall |
| :--- | :---: | :---: | :---: | :---: |
| **Treatment A (Frozen R2 Baseline)** | 0.2971 | 16.67% | 0.4544 | 100.0% (514/514) |
| **Treatment B (AST Alone, unconditioned)** | 0.1927 | 5.00% | 0.4557 | 100.0% (514/514) |
| **Treatment F (Treatment E + Conditioned AST)**| 0.2876 | 15.00% | 0.4796 | 100.0% (514/514) |
| **Treatment I (Combined Champion + Routing)** | **0.3124** | **18.33%** | **0.5278** | **100.0% (514/514)** |

---

## 3. PROFILING & RUNTIME PERFORMANCE

Benchmarked across 345 queries:
- **Identifier Decomposition Latency**: $0.082 \text{ ms}$ per query.
- **Intent Classification Latency**: $0.045 \text{ ms}$ per query.
- **Candidate Scoring Latency**: $0.210 \text{ ms}$ for 100 candidates.
- **Total Overhead**: $< 0.35 \text{ ms}$ per query, adding negligible cost to the ranking pipeline.

