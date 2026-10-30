# ARM-101 Research-to-Production Parity Audit & Discrepancy Reconciliation

**Date:** 2026-10-30  
**Stage:** 3.21  
**Experiment ID:** `EXP-321-02`  
**Status:** FULLY RECONCILED & PROVEN  
**Deterministic Run Fingerprint:** `25769a23a06bbb68588e8be0f52c5e1c2c13344bee825257ecaf1f4059d4b295`  

---

## 1. Executive Summary

In Stage 3.20, the full corpus reproduction report claimed:
- Research ARM-101 MRR: `0.2078`
- Production ARM-101 MRR: `0.2078`
- Reported MRR Difference: `0.000010`
- Exact Ranking Matches: `345 / 345`

Phase 2 was mandated to reconcile the apparent contradiction between an exact $345/345$ ranking match and a reported non-zero delta of $0.000010$, independently audit tie-breaking and abstention behaviors, and produce an auditable deterministic run fingerprint.

---

## 2. Root Cause of the Reported `0.000010` Difference

A line-by-line inspection of [research/stage3_20/generate_production_reproduction_records.py](file:///F:/RepoNeedle/research/stage3_20/generate_production_reproduction_records.py) revealed the exact mathematical origin of the `0.000010` figure:

1. **The Code:**
   Lines 310–315 of the Stage 3.20 reproduction script implemented the parity gate comparison as:
   ```python
   mean_mrr_arm101 = np.mean(mrr_arm101_prod_list)
   gap = abs(mean_mrr_arm101 - 0.2078)
   ```
2. **The Numerical Evaluation:**
   - The unrounded floating-point mean of reciprocal ranks across all 345 positive ARB queries is:
     $$\text{mean\_mrr\_arm101} = 0.2077904348...$$
   - The script subtracted the literal constant float `0.2078`:
     $$\text{gap} = |0.2077904348 - 0.2078000000| = 0.000009565... \approx 0.000010$$
   - Formatted with `f"{gap:.6f}"`, this printed as **`0.000010`**.

3. **True Production vs. Research Parity:**
   When comparing the production implementation ([reponeedle/core/arm101.py](file:///F:/RepoNeedle/reponeedle/core/arm101.py)) directly against the research prototype ([research/stage3_14/pilot_attenuation.py](file:///F:/RepoNeedle/research/stage3_14/pilot_attenuation.py)) query by query:
   $$\text{RR}_{\text{prod}}(q) - \text{RR}_{\text{research}}(q) = \mathbf{0.0000000000} \quad \forall q \in Q$$
   The aggregate difference between the two implementations is **`0.0000000000`** (exactly zero). The previously reported delta was an artifact of comparing the exact floating-point mean to a 4-decimal rounded constant scalar.

---

## 3. Algorithmic and Behavioral Audit

### 3.1 Ranking and Tie-Breaking Determinism
Both research `ExperimentalLanguageRanker` and production `ARM101Ranker` sort candidate indices using the identical tuple key:
```python
sorted_by_fused = sorted(range(n_docs), key=lambda idx: (-fused[idx], docs[idx].path))
```
- Primary sort: Decreasing fused score (`-fused[idx]`).
- Secondary sort: Lexicographically ascending normalized path (`docs[idx].path`).
- Guarantee: Tie-breaking is completely deterministic across operating systems and runtimes.

### 3.2 Soft Lexical Damping (Rank 1 Guard)
The Rank 1 guard evaluates:
$$\Theta_{\text{guard}} = \tau \cdot \max(0.0, S_{\text{lex}}(s_1) - S_{\text{lex}}(s_2)) \quad (\tau = 0.25)$$
- If top fused candidate equals $s_1$ or exceeds $s_1$ by $\ge \Theta_{\text{guard}}$, the graph-ordered list is returned.
- Otherwise, $s_1$ is promoted to Rank 1:
  $$\text{ranking} = [s_1] + [i \in \text{sorted\_by\_fused} \mid i \neq s_1]$$
- In production, `fused[s1]` is assigned `fused[best] + 1e-4` to preserve monotonic score consistency if scores are inspected.

### 3.3 Fail-Closed Abstention
When a query contains no vocabulary tokens matching the corpus:
- Okapi BM25 scores evaluate to $0.0$ for all documents.
- Seeds have zero score, disabling graph diffusion.
- `RepoNeedleEngine.retrieve()` triggers fail-closed abstention (`is_abstention = True`, empty returned files), identical to the baseline benchmark contract.

---

## 4. Query-Level Audit Results

All 345 positive benchmark queries have been verified and exported to [research/stage3_21/ARM101_PER_QUERY_PARITY.csv](file:///F:/RepoNeedle/research/stage3_21/ARM101_PER_QUERY_PARITY.csv):

| Metric | Research ARM-101 | Production ARM-101 | Delta | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Total Queries** | 345 | 345 | 0 | 100% Coverage |
| **Mean Reciprocal Rank (MRR)** | **0.207790** | **0.207790** | **0.000000** | **BIT-FOR-BIT MATCH** |
| **Recall@5** | 0.339130 | 0.339130 | 0.000000 | BIT-FOR-BIT MATCH |
| **Recall@10** | 0.449275 | 0.449275 | 0.000000 | BIT-FOR-BIT MATCH |
| **Recall@20** | 0.564783 | 0.564783 | 0.000000 | BIT-FOR-BIT MATCH |
| **Hit@20** | 0.649275 | 0.649275 | 0.000000 | BIT-FOR-BIT MATCH |
| **Exact Ranking Matches** | — | — | — | **345 / 345 (100.0%)** |

**Authoritative Deterministic Run Fingerprint:**
`25769a23a06bbb68588e8be0f52c5e1c2c13344bee825257ecaf1f4059d4b295`
