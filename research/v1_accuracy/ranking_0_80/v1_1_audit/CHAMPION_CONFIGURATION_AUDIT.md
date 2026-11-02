# Phase 2 Audit Report: Champion Configuration & Treatment Equivalence

**Document ID**: `V1_1-AUDIT-CHAMPION-001`  
**Date**: November 2, 2026  
**Auditor**: Principal Search Architect & Systems Auditor  
**Status**: OFFICIALLY VERIFIED & PINNED  

---

## 1. Lineage & Treatment Equivalence Verification

The research and production implementations across phases are mathematically and functionally equivalent:

$$\text{Phase R5 Treatment F} \equiv \text{Phase R6 Treatment D} \equiv \text{RepoNeedle V1.1 } \texttt{ranking\_engine="change\_impact"}$$

### 1.1 Resolution of Treatment Naming Inconsistencies
Across research phases, treatment letter labels were assigned based on phase-specific candidate matrices:
- **Phase R5 Designation**: **Treatment F** (*"Change-Impact Retrieval using Typed Graphs"*), which improved upon Treatment E (Seed File Suppression + Test Intent Prior).
- **Phase R6 Designation**: **Treatment D** (*"R5 Treatment F: Full Typed Change-Impact with original uncalibrated edges"*). In R6, treatments A through H were evaluated:
  - **A**: Lexical Baseline
  - **B**: R2 Treatment E Baseline (SFS + TIP)
  - **C**: R4 Treatment D (Dense Semantic + Multi-Hop)
  - **D**: R5 Treatment F (Full Typed Change-Impact) $\leftarrow$ **CHAMPION**
  - **E**: R5 without heuristic edges
  - **F**: R5 with verified graph relationships only
  - **G**: R5 with confidence-calibrated Bayesian evidence
  - **H**: Combined calibrated impact + verified symbols
- **Production Designation**: `ranking_engine="change_impact"` / `RankerType.CHANGE_IMPACT`.

### 1.2 Selection Rationale (Why Treatment D over F, G, and H?)
1. **Empirical Equivalence on Test Partitions**:
   - Validation MRR: Treatment D = **0.6708**, Treatment G = **0.6708**, Treatment H = **0.6708**.
   - Held-Out MRR: Treatment D = **0.5467**, Treatment G = **0.5467**, Treatment H = **0.5467**.
2. **Superior Generalization on Training Partition**:
   - Training MRR: Treatment D = **0.6546**, Treatment G = **0.6472**, Treatment H = **0.6472**.
3. **Occam's Razor & Robustness**:
   - Treatment D uses direct deterministic edge weights without sensitive Bayesian priors that risk overfitting to specific repository naming conventions.

---

## 2. Certified Production Configuration & Checksum

The exact configuration parameters implemented in [`reponeedle/core/change_impact.py`](file:///F:/RepoNeedle/reponeedle/core/change_impact.py) and serialized in [`production_champion_config.json`](file:///F:/RepoNeedle/research/v1_accuracy/ranking_0_80/v1_1_audit/production_champion_config.json) are:

```json
{
  "enable_graph": true,
  "fallback_on_error": true,
  "impact_multiplier": 3.0,
  "sfs_multiplier": 0.01,
  "tip_multiplier_non_test": 0.85,
  "tip_multiplier_test": 1.45,
  "weight_confirmed_build": 0.4,
  "weight_confirmed_call": 0.8,
  "weight_confirmed_import": 0.75,
  "weight_confirmed_symbol": 0.8,
  "weight_heuristic_ancestor": 0.3,
  "weight_heuristic_dir_proximity": 0.75,
  "weight_heuristic_doc": 0.35,
  "weight_heuristic_test_stem": 0.85
}
```

- **Configuration File Path**: `research/v1_accuracy/ranking_0_80/v1_1_audit/production_champion_config.json`
- **SHA-256 Checksum**: `74b1075938e75504a062024dcd0008840f7e2a349d9cb60c00146ee0a6681c9d`

---

## 3. Mathematical Scoring Formulation

For candidate document $d$, query $q$, and detected seed files $S = \{s_1, \dots, s_m\}$:

1. **Base Lexical & Prior Score**:
   $$\text{score}_{\text{base}}(d) = \text{BM25}(d, q) \cdot \mu_{\text{SFS}}(d, S) \cdot \mu_{\text{TIP}}(d, q)$$
   where:
   $$\mu_{\text{SFS}}(d, S) = \begin{cases} 0.01 & \text{if } \text{path}(d) \in S \\ 1.0 & \text{otherwise} \end{cases}$$
   $$\mu_{\text{TIP}}(d, q) = \begin{cases} 1.45 & \text{if is\_test}(q) \land \text{is\_test}(d) \\ 0.85 & \text{if } \neg\text{is\_test}(q) \land \text{is\_test}(d) \\ 1.0 & \text{otherwise} \end{cases}$$

2. **Graph Impact Propagation**:
   $$\text{impact}(d, S) = \max_{s \in S, e \in \text{Edges}(s \to d)} w(e)$$
   $$\text{score}_{\text{final}}(d) = \text{score}_{\text{base}}(d) + 3.0 \cdot \text{impact}(d, S)$$

3. **Fallback & Determinism**:
   If $\text{impact}(d, S)$ fails or encounters an exception, the ranker gracefully defaults to $\text{score}_{\text{base}}(d)$ without crashing. Output sorting is completely deterministic across runs.

