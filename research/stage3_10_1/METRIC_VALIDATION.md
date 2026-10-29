# RepoNeedle Stage 3.10.1: Metric Validation & Boundary Condition Audit

## 1. Formal Mathematical Definitions

### 1.1 Mean Reciprocal Rank (MRR)
For a set of $N$ queries $Q$, let $\text{Rank}_i$ be the 1-based rank position of the first relevant gold file in the ranked list for query $i \in Q$. If no gold file is retrieved, $\frac{1}{\text{Rank}_i} = 0$:

$$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\min \{ r \ge 1 \mid \text{File}_{i, r} \in \text{Gold}_i \} \cup \{\infty\}}$$

- **Multi-target Gold**: The reciprocal rank is determined exclusively by the **first** retrieved gold target. Subsequent targets do not affect MRR.
- **Hand-checkable test**: Verified in [`tests/test_stage3_10_1_metric_validation.py::test_hand_checkable_mrr`](file:///F:/RepoNeedle/tests/test_stage3_10_1_metric_validation.py).

---

### 1.2 Fractional Multi-Target Recall@k
For query $i$, let $\text{TopK}_i = \{ \text{File}_{i, 1}, \dots, \text{File}_{i, k} \}$ be the set of files returned in the first $k$ positions:

$$\text{Recall@k} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{|\text{TopK}_i \cap \text{Gold}_i|}{|\text{Gold}_i|}$$

> [!CAUTION]
> The denominator is **strictly** $|\text{Gold}_i|$, representing the total number of gold files for that query. It is never truncated to $\min(k, |\text{Gold}_i|)$, nor replaced with 1.

---

### 1.3 Binary Hit@k
Hit@k measures whether **at least one** relevant file was retrieved within the top $k$ positions:

$$\text{Hit@k} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \mathbb{I}(|\text{TopK}_i \cap \text{Gold}_i| > 0)$$

#### Distinction between Recall@k and Hit@k
On multi-target queries where a system retrieves 1 out of 3 gold files:
- $\text{Recall@20} = \frac{1}{3} = 0.3333$
- $\text{Hit@20} = 1.0000$

Confusing Hit@20 with Recall@20 creates an artificial $\sim 8$ to $10$ percentage point inflation on ARB v2. Both metrics are reported separately in all Stage 3.10 and 3.10.1 artifacts.
- **Hand-checkable test**: Verified in [`tests/test_stage3_10_1_metric_validation.py::test_hand_checkable_fractional_recall_vs_hit`](file:///F:/RepoNeedle/tests/test_stage3_10_1_metric_validation.py).

---

### 1.4 Context-Budgeted Coverage (BCY@8k)

#### Implementation A: ARB v2 Baseline Character Greedy-Stop (`gold_coverage_at_budget`)
```python
def gold_coverage_at_budget(gold: set[str], ranked_chunks: list[dict], budget: int) -> float:
    if not gold: return 0.0
    used = 0
    covered = set()
    for chunk in ranked_chunks:
        text = str(chunk.get("text", ""))
        if used + len(text) > budget and used > 0:
            break
        used += len(text)
        path = str(chunk.get("path", ""))
        if path in gold:
            covered.add(path)
    return len(covered) / len(gold)
```
1. **Unit**: Characters (`len(text)`), **not** tokens. In code, 8,000 characters $\approx 1,800$ to $2,500$ tokens.
2. **Greedy-Stop**: As soon as chunk 1 or 2 exceeds 8,000 characters, the loop breaks (`break`). Rank 3+ candidates are never inspected.
3. **Chunk 0 Zero-Budget Quirk**: Notice `and used > 0`. On the first iteration ($used = 0$), `used > 0` evaluates to `False`. Thus, **chunk 0 is always included, even if its length exceeds 8,000 characters, and even if budget is 0**!
- **Hand-checkable test**: Verified in [`tests/test_stage3_10_1_metric_validation.py::test_first_chunk_zero_budget_boundary`](file:///F:/RepoNeedle/tests/test_stage3_10_1_metric_validation.py).

#### Implementation B: Token-Budgeted Truncation Packing (`pack_files`)
- Uses `regex_code_tokenizer_v1` to measure true code tokens.
- Packs chunks up to 8,000 tokens, allowing partial file truncation for the final chunk.
- Under an 8,000-token budget:
  - BM25: $0.1971$
  - Candidate C: $0.2516$
  - Candidate F: $0.2412$
  - Candidate Cascade: $0.2286$
  - RepoMap: $0.3177$
