# RepoNeedle Stage 3.9: Independent Metric Verification & Hand-Calculated Edge Audits

**Document ID**: `STAGE3-9-VERIFY-001`  
**Date**: October 2026  
**Stage**: Stage 3.9 Gate A — Metric Reconciliation and Independent Verification  
**Branch**: `research-program`  
**Verification Script**: [`research/stage3_9/generate_gate_a_deliverables.py`](file:///F:/RepoNeedle/research/stage3_9/generate_gate_a_deliverables.py)  

---

## 1. Zero-Import Independent Calculation Contract

To ensure metric integrity, the Gate A verifier implements all formulas from mathematical specifications without importing any functions from `reponeedle` or `agent_retrieval_bench`.

### Metric Definitions:
1. **Full-Rank Reciprocal Rank (RR)**:
   $$\text{RR}_{\text{full}} = \frac{1}{\min \{r : \text{ranked}_r \in \text{gold}\}} \quad (\text{if gold found, else } 0.0)$$
2. **Top-20 Cutoff Reciprocal Rank (RR@20)**:
   $$\text{RR}_{@20} = \begin{cases} \frac{1}{\min \{r : \text{ranked}_r \in \text{gold}\}}, & \text{if } \min r \le 20 \\ 0.0, & \text{otherwise} \end{cases}$$
3. **Fractional Multi-Target Recall@K**:
   $$\text{Recall@K}_{\text{frac}} = \frac{|\text{gold} \cap \text{ranked}_{:K}|}{|\text{gold}|}$$
4. **Binary Hit@K**:
   $$\text{Hit@K} = \mathbb{I}(|\text{gold} \cap \text{ranked}_{:K}| \ge 1)$$
5. **Precision@K**:
   $$\text{Precision@K} = \frac{|\text{gold} \cap \text{ranked}_{:K}|}{\min(K, |\text{ranked}|)}$$

---

## 2. Validation Against Hand-Calculated Test Fixtures

The verifier was validated against hand-calculated multi-target edge cases before processing benchmark outputs:

### Fixture 1: Multi-Target Query ($|\text{gold}| = 3$)
- **Gold Files**: `{"src/auth.py", "src/models.py", "src/views.py"}`
- **Ranked Predictions**: `["README.md", "src/models.py", "docs/index.md", "src/auth.py", "tests/test_auth.py"]`
- **Hand Calculations**:
  - First relevant target is `src/models.py` at rank 2 $\implies \text{RR} = 1/2 = \mathbf{0.500000}$.
  - Top 5 contains 2 targets (`src/models.py`, `src/auth.py`) $\implies \text{Recall@5} = 2/3 = \mathbf{0.666667}$.
  - Binary Hit@5 contains $\ge 1$ target $\implies \text{Hit@5} = \mathbf{1.000000}$.
  - Precision@5 is $2 / 5 \implies \text{Precision@5} = \mathbf{0.400000}$.
- **Verifier Assertion**: Passed with absolute delta $< 10^{-6}$.

### Fixture 2: Deep Relevant Target Beyond Cutoff ($|\text{gold}| = 1$)
- **Gold Files**: `{"deep/target.py"}`
- **Ranked Predictions**: 24 noise files followed by `deep/target.py` at rank 25.
- **Hand Calculations**:
  - Full-rank Reciprocal Rank is $1/25 = \mathbf{0.040000}$.
  - Top-20 Cutoff Reciprocal Rank is $\mathbf{0.000000}$ (cutoff strictly enforced).
  - Binary Hit@20 is $\mathbf{0.000000}$.
- **Verifier Assertion**: Passed with absolute delta $< 10^{-6}$.

---

## 3. Independent System Metric Recomputations ($N = 345$)

| System Identifier | Full-Rank MRR | Top-20 Cutoff MRR | Recall@5 (Frac) | Recall@10 (Frac) | Recall@20 (Frac) | Hit@20 (Binary) | Precision@5 (Indep) | Token BCY@8k | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`BASE-BM25`** | **0.1735** | **0.1649** | 0.1986 | 0.3118 | 0.4549 | 0.5304 | 0.0568 | 0.1957 | **VERIFIED EXACT** |
| **`CAND-C`** | 0.1399 | 0.1326 | **0.2111** | 0.3196 | **0.5105** | 0.6000 | 0.0557 | 0.2034 | **VERIFIED EXACT** |
| **`CAND-F`** | 0.1351 | 0.1277 | 0.1824 | **0.3316** | 0.5078 | **0.6029** | 0.0504 | 0.1775 | **VERIFIED EXACT** |
| **`BASE-REPOMAP`**| **0.2293** | **0.2242** | **0.3337** | **0.5110** | **0.6599** | **0.7478** | **0.0910** | **0.3177** | **VERIFIED / P@5 CORRECTED** |

---

## 4. Breakdown by Task Track & Language

### 4.1 Task Track Breakdown ($N = 345$)
| Task Track | Sample Count ($N$) | BM25 MRR | Cand C MRR | Cand F MRR | RepoMap MRR | Cand F R@20 | RepoMap R@20 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `code2test` | 106 | 0.0685 | 0.0638 | 0.0601 | **0.2284** | 0.3384 | **0.6123** |
| `comment2context`| 80 | **0.1657** | 0.1176 | 0.1240 | 0.1590 | 0.3312 | **0.4937** |
| `edit2ripple` | 58 | **0.2452** | 0.1356 | 0.1284 | 0.2344 | 0.5718 | **0.6164** |
| `trace2code` | 101 | 0.2487 | 0.2397 | 0.2265 | **0.2829** | 0.7888 | **0.8663** |

### 4.2 Language Breakdown ($N = 345$)
| Primary Language | Sample Count ($N$) | BM25 MRR | Cand F MRR | Net MRR Delta | Cand F R@20 | RepoMap R@20 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Go** | 142 | **0.2665** | 0.1587 | **-0.1078** | 0.6511 | **0.7786** |
| **Python** | 98 | 0.1274 | **0.1417** | **+0.0143** | 0.5272 | **0.6718** |
| **Rust** | 48 | 0.1223 | **0.1441** | **+0.0218** | 0.3733 | **0.6372** |
| **JavaScript** | 26 | 0.0204 | 0.0265 | +0.0061 | 0.0641 | **0.1410** |
| **TypeScript** | 10 | 0.0584 | 0.0473 | -0.0111 | 0.3000 | **0.6500** |
| **Other (Java/Doc)**| 21 | 0.1412 | 0.1205 | -0.0207 | 0.4444 | **0.5185** |

