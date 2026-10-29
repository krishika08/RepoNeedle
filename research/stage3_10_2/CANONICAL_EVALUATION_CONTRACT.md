# RepoNeedle Stage 3.10.2: Canonical Evaluation Contract

## 1. Scope & Governance Authority

This contract establishes the sole binding evaluation protocol for comparing RepoNeedle candidate architectures against baseline Okapi BM25 and RepoMap on Agent Retrieval Bench (ARB) v2.

Every system evaluated under this contract must strictly adhere to the candidate universe, tie-breaking, metric formulas, and budget definitions declared herein.

---

## 2. Evaluation Cohort & Candidate Universe

### 2.1 Benchmark Query Cohort
- **Dataset**: Agent Retrieval Bench v2 (`external/agent-retrieval-bench`).
- **Denominator**: Exactly **345 positive benchmark queries** across 218 distinct repository snapshots.
- **Task Composition**:
  - `v2_code2test`: 106 queries
  - `v2_comment2context`: 80 queries
  - `v2_trace2code`: 101 queries
  - `v2_edit2ripple`: 58 queries
- **Exclusion Policy**: Zero queries may be excluded, dropped, or marked missing.

### 2.2 Unconstrained Candidate Universe
- **Rule**: Every file in the repository snapshot is an eligible candidate for retrieval.
- **Prohibitions**:
  - Zero task-specific candidate filtering (e.g. no test-only candidate filtering on `code2test`).
  - Zero oracle exclusions of documentation or helper files before scoring.
  - Zero diagnostic string bypasses or gold-label-derived signals.

### 2.3 Deterministic Tie-Breaking
When candidate scores are tied, candidates must be ordered in **deterministic ascending lexicographical order by relative file path**:
```python
sorted_candidates = sorted(candidates, key=lambda idx: (-scores[idx], docs[idx].path))
```

---

## 3. Metric Definitions & Formulas

### 3.1 Mean Reciprocal Rank (MRR)
For query $i$, let $\text{Rank}_i$ be the 1-based rank position of the first matching gold file in the ranked list:

$$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\min \{ r \ge 1 \mid \text{File}_{i, r} \in \text{Gold}_i \} \cup \{\infty\}}$$

If no gold file is retrieved in the ranked list, the reciprocal rank is $0.0$.

### 3.2 Fractional Multi-Target Recall@k (k = 5, 10, 20)
For top $k$ retrieved files $\text{TopK}_i$:

$$\text{Recall@k} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{|\text{TopK}_i \cap \text{Gold}_i|}{|\text{Gold}_i|}$$

The denominator is strictly $|\text{Gold}_i|$, representing the total number of gold files for that query.

### 3.3 Binary Hit@k (k = 20)
Hit@k measures whether at least one relevant file is present in the top $k$:

$$\text{Hit@k} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \mathbb{I}(|\text{TopK}_i \cap \text{Gold}_i| > 0)$$

Hit@k must never be substituted for or labeled as Fractional Recall@k.

### 3.4 Context Budget Metrics

#### A. Character-Based Coverage (`char_cov@8k`)
Measures raw character length (`len(text)`) under ARB v2 baseline greedy-stop:
- Budget: 8,000 characters.
- Stopping condition: Breaks immediately when `used + len(chunk) > 8000 and used > 0`.
- Labeling: Must strictly be reported as `char_cov@8k`, **never** as token BCY@8k.

#### B. Token-Budgeted Coverage (`token_bcy@4k`, `token_bcy@8k`, `token_bcy@16k`)
Measures code tokens using the pinned regex tokenizer:
- Tokenizer: `[a-zA-Z0-9_]+|[^\s\w]`.
- Boundary Policy: Truncation packing (files are packed in rank order; the boundary file is partially truncated to fill remaining budget).
- Target Budgets: 4,000, 8,000, and 16,000 code tokens.

---

## 4. Ranking Procedure & Invariants

1. **Rank 1–3 BM25 Freeze**:
   The top 3 files ranked by Okapi BM25 are unconditionally locked. Graph expansion may only re-rank positions $\ge 4$.
2. **Degree Normalization**:
   Graph score propagation between seeds and targets must be attenuated by symmetric degree normalization:
   $$\text{norm} = \frac{1}{\sqrt{\text{deg}_{\text{out}}(\text{seed}) \cdot \text{deg}_{\text{in}}(\text{target})}}$$
3. **Package Fencing**:
   Graph diffusion is confined to files sharing directory or crate manifest boundaries.
