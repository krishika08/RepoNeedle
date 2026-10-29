# RepoNeedle Stage 3.7: Canonical Evaluation Contract

**Document ID**: `STAGE3-7-CONTRACT-001`  
**Date**: October 2026  
**Stage**: Stage 3.7 — Canonical Evaluation Reconciliation and Research Integrity Gate  
**Branch**: `research-program`  
**Base Commit**: `9a9944a`  
**Evaluator Reference**: Version-pinned Agent Retrieval Bench (ARB v2) at commit `9e4d68937f29`  

---

## 1. Scope & Benchmark Demarcation

This contract defines the single, immutable evaluation protocol governing all retrieval comparisons in RepoNeedle. All systems—baselines, frozen historical candidates, and active experimental configurations—must be evaluated strictly under this contract.

### 1.1 In-Distribution vs. Independent Benchmark Scope
- **Agent Retrieval Bench (ARB v2)**: Serves strictly as the **in-distribution development and regression benchmark**. Because all 427 instances (345 positive, 82 no-gold) were accessible during Stage 1 and Stage 2 exploratory research, evaluations on ARB v2 cannot and will not be claimed as independent generalization evidence.
- **ContextBench**: Serves as the **independent generalization benchmark**. Independent validation status remains formally `BLOCKED — DATA ACCESS` until official artifacts are acquired outside sandbox isolation.

---

## 2. Benchmark Corpus & Query Partitioning

### 2.1 Sample Partitions
The ARB v2 benchmark comprises exactly $427$ task instances across $K = 25$ diverse repositories:
1. **Positive Retrieval Set ($N = 345$)**:
   - Queries with $|\text{gold}_i| \ge 1$ ground-truth relevant files.
   - Evaluated across four realistic software engineering workflow tracks:
     - `code2test` ($N = 106$): Mapping implementation code to corresponding test suites.
     - `comment2context` ($N = 80$): Retrieving context for code review comments and docstrings.
     - `trace2code` ($N = 101$): Pinpointing defect root causes from runtime stack traces.
     - `edit2ripple` ($N = 58$): Surface blast-radius caller/callee files affected by code edits.
2. **Abstention Set ($N = 82$)**:
   - Queries with $|\text{gold}_i| = 0$ (no relevant files exist in the repository).
   - Evaluated strictly and reported separately for abstention precision, recall, and F1. Never mixed into the positive retrieval denominator.

### 2.2 Eligible Document Pool (Full Corpus Contract)
- **Mandatory Requirement**: Every candidate must index and search the **entire repository corpus** (all valid source code, tests, documentation, scripts, and configuration files).
- **Prohibition of Candidate Pre-Filtering**: Restricting the candidate pool prior to retrieval (e.g. `tests_only` on `code2test`, `code_only` on `trace2code`, or limiting to pre-indexed AST subsets) is strictly prohibited. All queries must search across the full repository.
- **Normalization**: All file paths are normalized using POSIX-style forward slashes (`/`), stripped of leading `./`, and validated against the repository file manifest.

---

## 3. Mathematical Metric Contract

### 3.1 Mean Reciprocal Rank (MRR)
$$\text{MRR} = \frac{1}{N} \sum_{i=1}^N \text{RR}_i, \quad \text{RR}_i = \begin{cases} \frac{1}{\min \{r : \text{ranked}_{i, r} \in \text{gold}_i\}}, & \text{if } \exists r \le 20 \text{ s.t. } \text{ranked}_{i, r} \in \text{gold}_i \\ 0.0, & \text{otherwise} \end{cases}$$
- Evaluated strictly over the top 20 retrieved files ($r \in [1, 20]$).
- If no gold target appears within the top 20 ranks, reciprocal rank is strictly $0.0$.

### 3.2 Multi-Target Fractional Recall@K
$$\text{Recall@K}_{\text{frac}} = \frac{1}{N} \sum_{i=1}^N \frac{|\text{gold}_i \cap \text{ranked}_{i, :K}|}{|\text{gold}_i|}, \quad K \in \{5, 10, 20\}$$
- Measures the proportion of relevant files retrieved.
- Every query is scored in $[0.0, 1.0]$. This is the canonical definition of Recall@K.

### 3.3 Binary Hit@K (Separate Diagnostic Metric)
$$\text{Hit@K} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(|\text{gold}_i \cap \text{ranked}_{i, :K}| \ge 1), \quad K \in \{5, 10, 20\}$$
- Indicates whether *at least one* gold file was retrieved.
- Must always be explicitly labeled as **Hit@K** and never confused with or reported as fractional Recall@K.

### 3.4 Precision@K
$$\text{Precision@K} = \frac{1}{N} \sum_{i=1}^N \frac{|\text{gold}_i \cap \text{ranked}_{i, :K}|}{\min(K, |\text{ranked}_i|)}, \quad K \in \{5, 10, 20\}$$

### 3.5 Token Budgeted Context Yield (BCY@8k)
$$\text{BCY@8k} = \frac{1}{N} \sum_{i=1}^N \frac{|\text{gold}_i \cap \text{packed}_{i, 8000\text{ tokens}}|}{|\text{gold}_i|}$$
- Evaluates the retrieval yield when top-ranked files are packed into an 8,000 tiktoken token budget (`cl100k_base`) using greedy packing (`agent_retrieval_bench.bcy_curve.pack_files`).

---

## 4. Operational & Measurement Rules

1. **Deterministic Tie-Breaking**:
   - If two candidates receive identical scoring floats, ties must be broken deterministically by sorting on `(-score, filepath)` lexicographically.
2. **Timing & Latency Measurement**:
   - Query latency is measured as wall-clock stopwatch milliseconds over 20 repeated warm runs after 1 mandatory cold-start iteration.
   - Both p50 (median) and p95 percentiles must be reported.
3. **Memory Working Set (RSS)**:
   - Measured via Windows PSAPI `K32GetProcessMemoryInfo` (`PROCESS_MEMORY_COUNTERS_EX.WorkingSetSize`).
   - Reports Total Process Working Set alongside Python `tracemalloc` index heap delta.
