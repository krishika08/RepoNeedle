# REPONEEDLE MISSION 0.80+ — PHASE R3
# DELIVERABLE 7: FEATURE SCHEMA SPECIFICATION & RUNTIME CONTRACT

**Author**: Principal Information Retrieval Engineer, Data Contracts Architect  
**Date**: November 2, 2026  
**Status**: APPROVED & FROZEN  
**Target Milestone**: Phase R3 (AST Symbol Intelligence + BM25L Ranking)  

---

## 1. FEATURE SCHEMA SPECIFICATION

Phase R3 introduces formal contracts for all ranking features evaluated in Treatments A through I. Every feature operates under strict zero-oracle constraints.

### 1.1 Complete Feature Registry

| Feature Key | Type | Value Domain | Provenance | Formula / Extraction Logic | Fallback Value |
| :--- | :---: | :---: | :--- | :--- | :---: |
| `sfs_demoted` | `bool` | `{True, False}` | SeedExtractor | `intent == 'relational' and norm_path in seeds` | `False` |
| `sfs_factor` | `float` | `[0.01, 1.0]` | Configuration | Multiplied by $0.01$ when `sfs_demoted` is True | `1.0` |
| `test_intent_prob` | `float` | `[0.0, 1.0]` | TestIntentClassifier | Calibrated regex token scoring on query text | `0.0` |
| `tip_boosted` | `bool` | `{True, False}` | TestIntentPrior | `test_intent_prob >= 0.5 and is_test_path(path)` | `False` |
| `tip_multiplier` | `float` | `[1.0, 2.5]` | TestIntentPrior | $1.0 + 1.5 \times \text{test\_intent\_prob}$ | `1.0` |
| `classified_intent` | `enum` | 5 categories | ASTIntentClassifier | `{test, impl, def, ref, general}` | `'general_search'` |
| `exact_symbol_score`| `float` | $[0.0, \infty)$ | M1 Channel A | Inverted index match of query identifiers in AST | `0.0` |
| `ast_multiplier` | `float` | `[0.05, 5.0]` | ASTSymbolMatcher | Intent-conditioned asymmetric definition multiplier | `1.0` |
| `field_bm25_score` | `float` | $[0.0, \infty)$ | M1 Channel B | Multi-field term frequency score across 8 fields | `0.0` |
| `bm25_boosted` | `bool` | `{True, False}` | BM25 Variants | Set True when BM25L/BM25+ length damping is active | `False` |
| `bm25_damping_factor`| `float`| `[1.0, 1.5]` | BM25 Variants | $1.0 + 0.5 \times \frac{\ln(1 + s_{\text{bm25}})}{1 + \ln(1 + s_{\text{bm25}})}$ | `1.0` |
| `final_score` | `float` | $[0.0, \infty)$ | Composite Ranker | $\text{base\_score} \times \text{sfs} \times \text{tip} \times \text{ast} \times \text{bm25}$ | `0.0` |

---

## 2. RUNTIME CONTRACTS & ZERO-ORACLE CONSTRAINTS

### 2.1 Forbidden Signals (Strictly Audited)
- `gold_files`: Ground-truth target paths must never be read, matched, or passed into scoring functions.
- `task_type`: Benchmark suite category tags (`code2test`, `trace2code`, etc.) must never be accessed.
- `base_commit`: Commit hashes or Git repository log history are prohibited from inference.
- `repo_name`: No rule may condition on repository identity (e.g. `if repo == "playwright"`).

### 2.2 Input Contract
```python
def rank(
    candidates: List[dict],
    query_text: str,
    treatment: str = "I"
) -> Tuple[List[dict], Dict[str, any]]:
    ...
```
- `candidates`: List of dictionary items containing `path`, `m1_score`, `m1_rank`, and `scores`.
- `query_text`: Raw string containing the developer query, issue description, diff, or traceback.
- `treatment`: Treatment code `'A'` through `'I'`.

---

## 3. COMPLEXITY & SYSTEM PERFORMANCE

- **Time Complexity**:
  - Feature extraction: $O(|q|)$ where $|q|$ is query length.
  - Candidate scoring: $O(K)$ where $K = |candidates| \le 100$.
  - Candidate sort: $O(K \log K)$ with stable tie-breaking on `m1_rank`.
  - Overall latency: $< 0.4 \text{ ms}$ per query on standard single-core execution.
- **Space Complexity**:
  - Memory allocation: $O(|q| + K)$, requiring $< 50 \text{ KB}$ working memory per query.
  - Zero dynamic heap allocation for large indexes at inference time.

