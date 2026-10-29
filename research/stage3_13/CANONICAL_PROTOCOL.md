# RepoNeedle Canonical Evaluation Protocol

**Document**: `research/stage3_13/CANONICAL_PROTOCOL.md`  
**Stage**: Stage 3.13 — Canonical Reproducibility and Evidence Reconciliation  
**Date**: October 30, 2026  
**Status**: FROZEN AND IMMUTABLE BENCHMARK PROTOCOL  

---

## 1. Benchmark Universe Specification

### 1.1 Positive Query Universe ($N = 345$)
All evaluations must execute over the exact 345 positive queries defined in Agent Retrieval Benchmark (ARB) v2 across 218 repository snapshots:
- `code2test`: 106 queries ([`external/agent-retrieval-bench/data/benchmark/v2_code2test/samples.jsonl`](file:///F:/RepoNeedle/external/agent-retrieval-bench/data/benchmark/v2_code2test/samples.jsonl))
- `comment2context`: 80 queries ([`external/agent-retrieval-bench/data/benchmark/v2_comment2context/samples.jsonl`](file:///F:/RepoNeedle/external/agent-retrieval-bench/data/benchmark/v2_comment2context/samples.jsonl))
- `trace2code`: 101 queries ([`external/agent-retrieval-bench/data/benchmark/v2_trace2code/samples.jsonl`](file:///F:/RepoNeedle/external/agent-retrieval-bench/data/benchmark/v2_trace2code/samples.jsonl))
- `edit2ripple`: 58 queries ([`external/agent-retrieval-bench/data/benchmark/v2_edit2ripple/samples.jsonl`](file:///F:/RepoNeedle/external/agent-retrieval-bench/data/benchmark/v2_edit2ripple/samples.jsonl))

No queries may be dropped, filtered, or subsampled. All queries must resolve to valid corpus snapshots in [`external/agent-retrieval-bench/data/corpus/v2_selective_mixed/corpus_manifest.jsonl`](file:///F:/RepoNeedle/external/agent-retrieval-bench/data/corpus/v2_selective_mixed/corpus_manifest.jsonl).

### 1.2 Candidate Pool Constraint (100% Unconstrained)
Every query must rank across the **complete repository snapshot**:
- **Zero Candidate Filtering**: Pruning candidate chunks by filename or path (e.g. `tests_only` in `code2test`) is strictly prohibited.
- **Zero Synthetic Bypass**: Code must run end-to-end on real repository files without micro-fixtures or hardcoded query bypasses.
- **Blind Execution**: The ranking engine must not have access to gold target filenames or task type metadata during candidate ranking.

---

## 2. Mathematical Metric Definitions

All metrics are calculated via clean-room reference implementations in [`research/stage3_10_2/independent_metrics.py`](file:///F:/RepoNeedle/research/stage3_10_2/independent_metrics.py).

### 2.1 Mean Reciprocal Rank (MRR)
For a ranking $R = [d_1, d_2, \dots]$ and gold set $G$:
$$\text{RR} = \begin{cases} \frac{1}{\min \{r \mid d_r \in G\}}, & \text{if } \exists d_r \in G \\ 0.0, & \text{otherwise} \end{cases}$$
$$\text{MRR} = \frac{1}{N} \sum_{i=1}^N \text{RR}_i$$

### 2.2 Fractional Multi-Target Recall@k (Recall@k)
$$\text{Recall@k} = \frac{|\{d_1, \dots, d_k\} \cap G|}{|G|}$$
The denominator is strictly the total number of gold files for that query.

### 2.3 Binary Hit Rate@k (Hit@k)
$$\text{Hit@k} = \begin{cases} 1.0, & \text{if } |\{d_1, \dots, d_k\} \cap G| > 0 \\ 0.0, & \text{otherwise} \end{cases}$$
Binary Hit@k must **never** be reported as Recall@k.

### 2.4 Token-Budgeted Context Yield (Token BCY@8k)
Code tokens are counted using the official ARB v2 regex tokenizer:
```python
TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[^\s\w]", re.UNICODE)
```
Ranked files are packed greedily into an 8,000-token budget window. If adding file $d_r$ exceeds the budget, it is truncated at the token boundary:
$$\text{BCY@8k} = \frac{|\text{PackedFiles} \cap G|}{|G|}$$

### 2.5 Deterministic Tie-Breaking
When candidate retrieval scores are tied:
$$\text{SortKey}(d) = (-S(d), d.\text{path})$$
Candidates are sorted descending by score, tie-breaking alphabetically ascending by normalized document path.

---

## 3. Timing and Latency Protocol

1. **Separation of Phases**:
   - **Indexing / Build Latency**: Time required to extract polyglot AST symbols, build lexical inverted indices, and construct function call graphs.
   - **Scoring / Query Latency**: Time required to score query tokens and propagate graph boost.
   - **Output Assembly / Packing Latency**: Time required to extract and format retrieved context chunks.
2. **Warm Query Evaluation**:
   - Systems must be warmed before timing measurements.
   - Report Median (P50), 95th Percentile (P95), and Arithmetic Mean.
   - Arithmetic mean alone is invalid due to heavy right-skew across large repositories.

---

## 4. Memory Profiling Protocol

1. **Measurement Standard**:
   - Measured using native Win32 `GetProcessMemoryInfo` (via `PROCESS_MEMORY_COUNTERS_EX`).
   - Primary metric: Process Working Set Size (RSS) in megabytes.
   - Secondary metric: Peak Working Set Size and Python traced heap (`tracemalloc`).
2. **Process Isolation Requirement**:
   - Memory must be profiled in **fresh, isolated processes** per repository to avoid cumulative allocation pollution from multi-corpus loops.
   - Report baseline interpreter footprint ($\approx 66.3\text{ MB}$), incremental index overhead, and peak working set separately.
