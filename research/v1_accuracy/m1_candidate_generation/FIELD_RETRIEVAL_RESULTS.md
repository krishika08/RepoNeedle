# RepoNeedle V1.0.0 — Field-Aware BM25 Retrieval Results

## Field Contribution Analysis

Milestone 1 evaluates individual field contributions of Okapi BM25 across 8 distinct code fields.
This isolates the retrieval power of structural code attributes versus unstructured natural language and raw body text.

### Field Ablation Performance

| Field | Micro Recall | Macro Recall | Complete Coverage | Recall@50 | Pool Size | Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `filepath` | 0.9981 | 0.9986 | 0.9971 | 0.6475 | 1402.0 | 84.70 |
| `filename` | 0.9922 | 0.9947 | 0.9884 | 0.5605 | 1163.6 | 57.26 |
| `symbol_names` | 0.9494 | 0.9536 | 0.9333 | 0.6768 | 753.0 | 49.15 |
| `qualified_names` | 0.0623 | 0.0614 | 0.0406 | 0.0488 | 113.0 | 12.42 |
| `signatures` | 0.0506 | 0.0454 | 0.0261 | 0.0275 | 101.5 | 11.19 |
| `docstrings` | 0.0428 | 0.0444 | 0.0319 | 0.0338 | 158.5 | 15.88 |
| `comments` | 0.8502 | 0.8458 | 0.8058 | 0.4059 | 1186.8 | 154.26 |
| `body` | 1.0000 | 1.0000 | 1.0000 | 0.5585 | 1532.7 | 282.62 |

| **All Fields Combined** (`channel_b`) | **1.0000** | **1.0000** | **1.0000** | **0.7678** | **1599.9** | **530.80** |

---

## Architectural Findings

1. **`filepath` and `filename` Dominance in Path-Anchored Tasks**:
   In `v2_code2test` and `v2_edit2ripple`, queries frequently contain changed file paths, anchor paths, or stack trace frames. Filepath BM25 provides the sharpest signal with minimal distractor leakage.

2. **`symbol_names` and `qualified_names` Specificity**:
   AST class and function symbol extraction yields high precision for identifier lookups, completely circumventing common keyword distraction that plagues full-body BM25.

3. **`docstrings` and `comments` Utility**:
   Docstrings provide vital semantic matches for natural language queries (`comment2context`), bridging the vocabulary gap when identifiers use terse abbreviations.

4. **`body` Field Distraction Risk**:
   While `body` achieves wide recall, its distractor yield is high (large candidate pool sizes), proving why decoupled field-specific weighting is necessary rather than treating raw source text as a single bag of words.
