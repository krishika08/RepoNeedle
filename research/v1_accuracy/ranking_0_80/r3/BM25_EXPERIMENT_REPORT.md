# REPONEEDLE MISSION 0.80+ — PHASE R3
# DELIVERABLE 6: BM25 VARIANT EXPERIMENTAL EVALUATION REPORT

**Author**: Principal Information Retrieval Engineer, Search Relevance Architect  
**Date**: November 2, 2026  
**Status**: APPROVED & FROZEN  
**Target Milestone**: Phase R3 (AST Symbol Intelligence + BM25L Ranking)  

---

## 1. EXPERIMENTAL DESIGN & BASELINES

This experiment systematically evaluates the standalone and integrated retrieval power of BM25 variants against the established Phase R2 reference baseline.

### 1.1 Evaluated Treatments
- **Treatment A**: Frozen R2 Champion (Treatment E: SFS + TIP) — *Authoritative Reference*
- **Treatment C**: BM25L Alone (SFS + BM25L saturation damping)
- **Treatment D**: BM25+ Alone (SFS + BM25+ additive lower bound)
- **Treatment E**: Field-Weighted BM25 (SFS + Multi-field path/symbol/body weighting)
- **Treatment G**: Treatment E + BM25L (SFS + TIP + BM25L damping)

---

## 2. EXPERIMENTAL RESULTS ACROSS SPLITS

All evaluations were executed on the canonical 345-query dataset using `research/v1_accuracy/ranking_0_80/r3/src/evaluate_r3.py`.

### 2.1 Benchmark Results Table

| Treatment | Formulation | Validation MRR | Validation Hit@1 | Validation Recall@20 | Train MRR | Held-Out MRR |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Treatment A (R2 Baseline)** | SFS + TIP | **0.2971** | **16.67%** | **0.5875** | 0.4544 | **0.2965** |
| **Treatment C** | BM25L Alone | 0.2029 | 6.67% | 0.5125 | 0.4305 | 0.1963 |
| **Treatment D** | BM25+ Alone | 0.2034 | 6.67% | 0.5292 | 0.4326 | 0.2008 |
| **Treatment E** | Field-Weighted BM25 | 0.2022 | 6.67% | 0.5125 | 0.4304 | 0.1939 |
| **Treatment G** | Treatment E + BM25L | **0.2973** | **16.67%** | **0.5875** | **0.4544** | **0.2967** |

---

## 3. ARCHITECTURAL & EMPIRICAL FINDINGS

### 3.1 Why Standalone BM25 Cannot Match Treatment A
1. **The Test-Intent Dependency**: Standalone BM25 variants (Treatments C, D, E) achieve only $\approx 0.203$ MRR on Validation, compared to $0.2971$ for Treatment A.
2. **Failure on `code2test`**: In code-to-test retrieval, queries consist of code diffs and implementation signatures. Standard lexical matching ranks code files at the top. Without the Test Intent Prior (TIP), Hit@1 collapses from 16.67% down to 6.67%.
3. **BM25+ vs BM25L**: BM25+ slightly outperformed BM25L in standalone mode ($0.2034$ vs $0.2029$ MRR, $0.5292$ vs $0.5125$ Recall@20) because its additive lower bound guarantees non-zero scoring floor for long documents.

### 3.2 Integrated Impact of BM25L (Treatment G)
When BM25L length normalization is combined with the full R2 champion pipeline (Treatment G):
- Validation MRR advances slightly: $0.2971 \to 0.2973$.
- Held-Out MRR advances slightly: $0.2965 \to 0.2967$.
- Recall@20 is fully maintained at $0.5875$.
- BM25L prevents length-dilution on lengthy core utility and engine modules without destabilizing candidate rankings.

