# RepoNeedle Stage 3.16 — External Benchmark Metric Contract

**Document ID**: `STAGE3-16-METRIC-001`  
**Date**: October 2026  
**Status**: Authoritative Metric Contract for External Benchmark Evaluation  

---

## 1. Metric Hierarchy & Disambiguation Rules

To prevent repeats of historical reporting errors (such as Stage 3.5's relabeling of Binary Hit@20 as Recall@20 or mixing character and token budgets), the following unambiguous rules are locked:

### 1.1 Mean Reciprocal Rank (MRR)
$$\text{RR}_i = \frac{1}{\min \{ k \mid \pi_{i, k} \in \text{gold}_i \}} \quad (\text{or } 0.0 \text{ if none retrieved})$$
$$\text{MRR} = \frac{1}{N} \sum_{i=1}^N \text{RR}_i$$
MRR measures the rank position of the **first relevant file**.

### 1.2 Multi-Target Fractional Recall@K
$$\text{Recall@K} = \frac{1}{N} \sum_{i=1}^N \frac{|\text{gold}_i \cap \pi_{i, :K}|}{|\text{gold}_i|}$$
Measures the proportion of all gold needles retrieved within the top $K$ ranks. This is the **only metric permitted to be called Recall@K**.

### 1.3 Binary Hit@K (Hit Rate)
$$\text{Hit@K} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(|\text{gold}_i \cap \pi_{i, :K}| \ge 1)$$
Measures whether at least one gold needle was retrieved in the top $K$.
> [!CAUTION]
> **Prohibition Against Relabeling**:
> Because queries frequently have multiple relevant files, $\text{Hit@K} \ge \text{Recall@K}$. Relabeling Binary Hit@K as "Recall@K" is strictly prohibited.

### 1.4 Token-Budgeted Context Yield (Token BCY@8k)
$$\text{BCY@8k} = \frac{1}{N} \sum_{i=1}^N \frac{|\text{gold}_i \cap \text{packed}_{i, 8k}|}{|\text{gold}_i|}$$
Measures prompt packing efficiency within an 8,000 token limit (`cl100k_base`).
> [!CAUTION]
> **Prohibition Against Conflating Packing Yield with Retrieval Recall**:
> Context packing file yield (BCY) measures how many files can be packed into an LLM prompt window using skeletonization. It is **NOT** a substitute for retrieval ranking Recall@20.

---

## 2. ContextBench Multi-Granularity Metrics

ContextBench supports three distinct granularities:
1. **File-Level**: Target paths must match normalized gold file paths.
2. **Symbol-Level**: Retrieved function and class definitions must overlap with the symbols modified by the solution patch.
3. **Span-Level**: Character and line spans identified by the retriever must intersect the ground-truth edit regions.

If an adapter does not support span extraction natively, that metric must be explicitly labeled **`UNSUPPORTED`**, rather than manufacturing a proxy and presenting it as official.
