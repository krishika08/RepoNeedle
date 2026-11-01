# RepoNeedle V1.0.0 — Milestone 1 Design Specification: Multi-Stage Candidate Generation

## 1. Architectural Mission

Milestone 1 decouples candidate generation from final ranking and context packing.
The primary goal of candidate generation is **complete candidate coverage** ($Candidate Recall = 1.000$) across the defined, independently annotated evaluation scope.

A query cannot be answered correctly by downstream AI coding agents if the relevant target files are omitted from the candidate pool during first-stage retrieval.

```
                          ┌────────────────────────┐
                          │     User Query / PR    │
                          └───────────┬────────────┘
                                      │
               ┌──────────────────────┼──────────────────────┐
               ▼                      ▼                      ▼
      ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
      │   Channel A:    │    │   Channel B:    │    │   Channel C:    │
      │  Exact Symbol   │    │ Field-Aware BM25│    │ Subword N-Grams │
      │  AST / Paths    │    │    (8 Fields)   │    │  (Morphologies) │
      └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
               │                      │                      │
               └──────────────────────┼──────────────────────┘
                                      ▼
                             ┌─────────────────┐
                             │ Seed Candidates │
                             └────────┬────────┘
                                      ▼
                             ┌─────────────────┐
                             │   Channel D:    │
                             │   1-Hop Bounded │
                             │   Structural    │
                             │    Expansion    │
                             └────────┬────────┘
                                      ▼
                             ┌─────────────────┐
                             │  Multi-Channel  │
                             │ Max-Normalized  │
                             │      Union      │
                             └────────┬────────┘
                                      ▼
                        Deduplicated Candidate Pool
                         (Candidate Recall = 1.000)
```

## 2. Channel Architecture

### Channel A: ExactSymbolIndex
Bitwise inverted index mapping normalized symbol names, qualified names (`module.Class.method`), parameter signatures, backticked identifiers, and file paths. Operates with IDF-like rarity weighting.

### Channel B: FieldAwareBM25
8-field Okapi BM25 implementation ($k_1=1.5, b=0.75$) indexing:
- `filepath`: Full relative path tokens.
- `filename`: Base file name tokens.
- `symbol_names`: Extracted function, class, and method names.
- `qualified_names`: Dotted symbol paths.
- `signatures`: Parameter argument names.
- `docstrings`: Module, class, and function docstrings.
- `comments`: Source code line comments.
- `body`: Source code body tokens.

### Channel C: SubwordChannel
Fast character 3-to-5-gram inverted index over identifier tokens and path elements, resolving abbreviations, compound naming variants, and casing mismatches.

### Channel D: BoundedStructuralExpansion
1-hop verified relationship expansion connecting:
- Target files to verified test files (`test_to_target` and `target_to_test`).
- Direct imports and reverse imports (`import_graph` and `reverse_import_graph`).
- Caller/callee linkages.

## 3. Score Combination & Normalization

To prevent channels with wide raw score distributions (such as BM25 summing across 8 fields) from drowning out high-precision channels (such as ExactSymbolIndex), scores are max-normalized per active channel:

$$\hat{s}_k(d) = \frac{s_k(d)}{\max_{d'} s_k(d') + \epsilon}$$

The final combined candidate generation score is:

$$S(d) = 0.40 \cdot \hat{s}_{\text{sym}}(d) + 0.35 \cdot \hat{s}_{\text{bm25}}(d) + 0.15 \cdot \hat{s}_{\text{sub}}(d) + 0.10 \cdot \hat{s}_{\text{struct}}(d)$$

Every candidate item retains its complete provenance, raw channel scores, and structural evidence.
