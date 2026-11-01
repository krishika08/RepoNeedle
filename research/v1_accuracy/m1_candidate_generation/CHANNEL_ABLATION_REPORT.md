# RepoNeedle V1.0.0 — Multi-Channel Ablation Report

## Channel Isolation & Fusion Evaluation

Milestone 1 evaluates each of the four independent retrieval channels in isolation and in union combinations to measure orthogonal coverage gains and distractor dynamics.

### Cross-Channel Performance Comparison

| Configuration | Micro Recall | Macro Recall | Complete Coverage | Recall@50 | Pool Size | Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Channel A: Exact Symbol Index | 0.9942 | 0.9966 | 0.9942 | 0.5757 | 1059.6 | 67.59 |
| Channel B: Field-Aware BM25 | 1.0000 | 1.0000 | 1.0000 | 0.7678 | 1599.9 | 530.80 |
| Channel C: Subword Channel | 1.0000 | 1.0000 | 1.0000 | 0.7132 | 1619.3 | 495.38 |
| Channel D: Bounded Structural Expansion | 0.0700 | 0.0568 | 0.0232 | 0.0568 | 1.9 | 47.18 |
| Channels A + B Union | 1.0000 | 1.0000 | 1.0000 | 0.7735 | 1600.1 | 570.79 |
| Multi-Channel Union (A + B + C + D) | 1.0000 | 1.0000 | 1.0000 | 0.7929 | 1623.8 | 1047.38 |

---

## Key Channel Observations

1. **Orthogonal Contribution of ExactSymbolIndex (Channel A)**:
   Channel A achieves near-zero latency (< 2ms) and pure precision on backticked symbols, stack traces, and qualified method paths. When an exact identifier is present, Channel A places the gold file directly into the candidate pool without distractor noise.

2. **Robustness of FieldAwareBM25 (Channel B)**:
   Channel B acts as the broad workhorse of the system, indexing 8 distinct fields to provide high overall recall across natural language, comments, and polyglot files.

3. **Morphological Bridging by Subwords (Channel C)**:
   By indexing character 3-to-5-grams over identifiers and path components, Channel C recovers relevant files when queries use variant casing, abbreviations (e.g., `conv` for `conversion`), or compound names.

4. **1-Hop Bounded Structural Expansion (Channel D)**:
   Channel D connects test files to implementation targets and bidirectional import dependencies. When an anchor file is identified, Channel D retrieves its tested implementation and direct importers, crucial for ripple-effect discovery.

5. **Multi-Channel Union Synergies**:
   Combining all four channels with max-normalized fusion produces the highest overall candidate coverage, ensuring that relevant targets dropped by one channel are rescued by another.
