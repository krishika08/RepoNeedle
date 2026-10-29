# RepoNeedle Stage 3.15: Locked Evaluation Protocol for ContextBench

**Stage**: Stage 3.15 — Official ContextBench Acquisition and Independent Evaluation Gate  
**Date**: October 2026  
**Document ID**: `STAGE3-15-PROTO-001`  
**Status**: Authoritative Pre-Registered Evaluation Protocol  
**Branch**: `research-program`  
**Base Commit**: `3e889fc`  

---

## 1. Executive Protocol Charter

To maintain experimental integrity and eliminate post-hoc parameter tuning, this protocol establishes the **pre-registered, locked evaluation procedure** for RepoNeedle on ContextBench.

### Guiding Principles:
1. **Zero Hyperparameter Tuning**: All retrieval weights, BM25 constants ($k_1=1.5, b=0.75$), subword parameters, candidate pooling depths ($K=50$), and documentation penalty factors ($0.5\times$) are permanently frozen prior to evaluating on ContextBench.
2. **Standardized Candidate Pool**: Every system must be evaluated on identical repository snapshots checked out at the exact `base_commit` specified by each ContextBench task instance.
3. **Fail-Closed Failure Accounting**: Any task instance where a repository cannot be checked out, an indexing exception occurs, or retrieval fails must be explicitly recorded as a failure ($MRR=0.0$, $Recall=0.0$) and counted in the evaluation denominator. Silently dropping failed instances is strictly prohibited.
4. **Scope Demarcation**: Retrieval metrics (MRR, Recall@K, BCY@8k) must not be conflated with or claimed as downstream coding agent patch success (SWE-bench).

---

## 2. Evaluated Systems & Configuration Freeze

Four distinct systems are evaluated:

| System ID | Canonical Label | Configuration Description | Key Hyperparameters (FROZEN) |
| :--- | :--- | :--- | :--- |
| **`BASE-BM25`** | `CONFIG-01` | Official Pure BM25 Baseline | Okapi $k_1 = 1.5$, $b = 0.75$; full file content tokens; coupled symbol lengths. |
| **`CONFIG-09`** | `CONFIG-09` | RepoNeedle Hybrid Quality Winner | Decoupled lexical BM25 + Subword TF-IDF + Documentation Filter ($0.5\times$). Zero PageRank diffusion. |
| **`CONFIG-10`** | `CONFIG-10` | Sparse Cascaded Production Reranker | Top-50 BM25 initial candidate pool + Sliced Subword TF-IDF reranking. |
| **`BASE-REPOMAP`** | `BASE-REPOMAP` | Official RepoMap Reference (`9e4d689`) | Pinned Aider tree-sitter call-graph and PageRank reference implementation. |

---

## 3. Official Metric Specifications

The evaluation protocol adopts the documented ContextBench metrics:

### 3.1 Primary Retrieval Metrics
1. **Mean Reciprocal Rank (MRR)**:
   $$\text{MRR} = \frac{1}{N} \sum_{i=1}^N \frac{1}{\min \{r : \text{path}_r \in \text{gold}_i\}}$$
   Evaluated over top-20 retrieved candidates. If no gold file is within the top 20, reciprocal rank is $0.0$.
2. **Recall@K ($K \in \{5, 10, 20\}$)**:
   $$\text{Recall@K} = \frac{1}{N} \sum_{i=1}^N \frac{|\text{gold}_i \cap \text{ranked}_{i, :K}|}{|\text{gold}_i|}$$
3. **Precision@K ($K \in \{5, 10, 20\}$)**:
   $$\text{Precision@K} = \frac{1}{N} \sum_{i=1}^N \frac{|\text{gold}_i \cap \text{ranked}_{i, :K}|}{\min(K, |\text{ranked}_i|)}$$
4. **Token Budget-Constrained Yield (BCY@8k)**:
   $$\text{BCY@8k} = \frac{1}{N} \sum_{i=1}^N \frac{|\text{gold}_i \cap \text{packed}_{i, 8000\text{ tokens}}|}{|\text{gold}_i|}$$
   Evaluated using greedy context packing under an exact 8,000 tiktoken token budget.

### 3.2 Fine-Grained Metrics (Where Supported by Dataset Annotations)
- **Symbol / Span Recall**: Ratio of ground-truth functional spans/symbols retrieved within packed context.
- **Context Distractor Ratio**: Fraction of non-relevant files packed before all gold files are exhausted.

---

## 4. Multiplicity Control & Statistical Equivalence Protocol

To prevent selective reporting, all inferential comparisons on ContextBench must follow this pre-registered statistical analysis plan:

### 4.1 Paired Superiority: CONFIG-09 vs BASE-BM25
- **Test**: Paired Wilcoxon signed-rank test on per-task metric differences.
- **Multiplicity Control**: Holm's step-down adjustment applied across all evaluated metric families at target familywise error rate $\alpha = 0.05$.
- **Effect Size**: Paired Cohen's $d$ and 95% bootstrap confidence intervals ($B = 10,000$ iterations).

### 4.2 Equivalence Verification: CONFIG-10 vs CONFIG-09
- **Predeclared Equivalence Margin**: $\Delta = \pm 0.015$ MRR.
- **Procedure**: Two One-Sided Tests (TOST):
  $$H_{01}: \mu_{\text{diff}} \le -\Delta \quad \text{vs.} \quad H_{11}: \mu_{\text{diff}} > -\Delta$$
  $$H_{02}: \mu_{\text{diff}} \ge +\Delta \quad \text{vs.} \quad H_{12}: \mu_{\text{diff}} < +\Delta$$
  Where $d_i = y_{\text{C10}, i} - y_{\text{C09}, i}$.
- **Rejection Criterion**: Both one-sided null hypotheses must be rejected at $\alpha = 0.05$ ($p_{\text{TOST}} = \max(p_1, p_2) < 0.05$), with the 90% confidence interval strictly contained inside $[-\Delta, +\Delta]$.

---

## 5. Execution Pipeline & Adapter Architecture

The benchmark execution pipeline is implemented via a thin, non-invasive adapter:

```
[ContextBench Dataset (.parquet / .jsonl)]
                │
                ▼
┌──────────────────────────────────────────────┐
│  research/stage3_15/validate_contextbench.py │  ──> Cryptographic SHA-256 & Schema Check
└──────────────────────┬───────────────────────┘
                       │ (Valid)
                       ▼
┌──────────────────────────────────────────────┐
│ research/stage3_15/contextbench_adapter.py   │  ──> Dispatches query to frozen configurations
└──────────────────────┬───────────────────────┘
                       │
       ┌───────────────┼───────────────┬───────────────┐
       ▼               ▼               ▼               ▼
  [CONFIG-01]     [CONFIG-09]     [CONFIG-10]     [BASE-REPOMAP]
       │               │               │               │
       └───────────────┼───────────────┴───────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│     Metric Accumulator & Uncertainty Engine  │  ──> Computes MRR, Recall, BCY, TOST, Wilcoxon
└──────────────────────┬───────────────────────┘
                       ▼
    [EXTERNAL_EVALUATION_RESULTS.csv & PER_TASK_RESULTS.csv]
```

---

## 6. Failure Accounting & Exclusion Rules

1. **Missing Git Repository / Base Commit**: If a repository snapshot cannot be obtained or checked out, record task status as `FAILED_SNAPSHOT_UNAVAILABLE`. The instance is assigned 0.0 for all retrieval metrics.
2. **Token Limit Exceeded / OOM**: If a file exceeds parser limits, fallback to raw text chunking; if memory exceeds process boundaries, record as `FAILED_RESOURCE_EXHAUSTION` ($MRR = 0.0$).
3. **Zero Ground-Truth Queries**: If an instance has empty `gold_files`, it is excluded from the evaluation denominator and recorded in an explicit exclusion ledger.
