# RepoNeedle Stage 3.15 — Canonical Metric & Benchmark Contract

**Document ID**: `STAGE3-15-CONTRACT-001`  
**Date**: October 2026  
**Status**: Authoritative Evaluation Contract  
**Benchmark Target**: Agent Retrieval Benchmark (ARB) v2 Development Corpus  

---

## 1. Benchmark Scope & Candidate Universe

The canonical evaluation contract governing RepoNeedle retrieval research requires strict adherence to three operational rules:

1. **Fixed Query Set ($N = 345$)**:
   - Exactly 345 positive development queries from `benchmarks/arb_v2/queries_positive.jsonl`.
   - Spans 4 task categories:
     - `code2test`: 106 queries
     - `comment2context`: 80 queries
     - `trace2code`: 101 queries
     - `edit2ripple`: 58 queries
   - Distributed across 25 polyglot repositories and 218 git commit snapshots.
2. **Unconstrained Full-Repository Candidate Universe**:
   - Every file present in the repository commit snapshot is an eligible retrieval candidate.
   - **Zero Candidate Filtering**: Historical practices of restricting candidates to `test_only` for `code2test` or `code_only` for `trace2code` are **strictly prohibited**. Full-corpus retrieval must evaluate against code, tests, documentation, and configuration files simultaneously.
3. **File-Level Granularity**:
   - Ranking is performed over unique file paths (`doc.path`), normalizing directory separators to forward slashes (`/`). Chunk-level deduplication maps chunks back to their parent file paths.

---

## 2. Mathematical Metric Definitions

### 2.1 Mean Reciprocal Rank (MRR)
For query $i$ with relevant target set $\text{gold}_i$ and ranked candidate list $\pi_i = [\pi_{i, 1}, \pi_{i, 2}, \dots, \pi_{i, M}]$:

$$\text{RR}_i = \begin{cases} 
\frac{1}{r_i} & \text{if } \exists g \in \text{gold}_i \text{ at rank } r_i = \min \{ k \mid \pi_{i, k} \in \text{gold}_i \} \\ 
0.0 & \text{if } \text{gold}_i \cap \pi_i = \emptyset 
\end{cases}$$

$$\text{MRR} = \frac{1}{N} \sum_{i=1}^N \text{RR}_i$$

MRR rewards placing at least one relevant needle as close to Rank 1 as possible.

### 2.2 Multi-Target Fractional Recall@K (Official ARB v2 Contract)
In benchmarks where queries frequently possess multiple relevant files ($|\text{gold}_i| \ge 1$), fractional recall measures the proportion of all relevant targets retrieved within the top $K$ candidates:

$$\text{Recall@K}_i = \frac{|\text{gold}_i \cap \pi_{i, :K}|}{|\text{gold}_i|}$$

$$\text{Recall@K} = \frac{1}{N} \sum_{i=1}^N \text{Recall@K}_i$$

*Example*: If a query has 2 gold files and only 1 appears in the top 20 ranks, $\text{Recall@20}_i = 0.5$.

### 2.3 Binary Hit@K (Any-Target Hit Rate)
$$\text{Hit@K}_i = \begin{cases} 
1.0 & \text{if } |\text{gold}_i \cap \pi_{i, :K}| \ge 1 \\ 
0.0 & \text{otherwise} 
\end{cases}$$

$$\text{Hit@K} = \frac{1}{N} \sum_{i=1}^N \text{Hit@K}_i$$

**Critical Forensic Finding**: Because $|\text{gold}_i| \ge 1$, $\text{Hit@K} \ge \text{Recall@K}$ always holds. Stage 3.5 computed Binary Hit@20 ($196 / 345 = 0.5681$ for RepoMap, $195 / 345 = 0.5652$ for Candidate F) but labeled them as "Recall@20" in summary tables. Multi-target fractional Recall@20 is **0.6599** for pinned RepoMap and **0.5078** for Candidate F. Conflating these definitions is mathematically invalid.

### 2.4 Token-Budgeted Context Yield (Token BCY@8k)
Measures the proportion of gold files or gold tokens successfully packed into a prompt context window of 8,000 tokens (tokenized via `cl100k_base` / `tiktoken`):

$$\text{BCY@8k} = \frac{1}{N} \sum_{i=1}^N \frac{|\text{gold}_i \cap \text{packed}_{i, 8k}|}{|\text{gold}_i|}$$

- Skeletons permitted: Retains function and class signatures while compressing method bodies.
- Character budgets (e.g. 8,000 characters $\approx 1,800$ tokens) are invalid substitutes and caused the Stage 3.6 BCY collapse erratum (ERR-306-01).

---

## 3. Operational Performance & Resource Measurement Contract

1. **Warm Query Latency**:
   - Pre-warm the indexing structures and cache.
   - Measure 5 warm query runs per query; record median (P50) and 95th percentile (P95) in milliseconds.
2. **Fresh Process Memory Isolation**:
   - Memory must be profiled in **isolated fresh processes** per repository to avoid cumulative garbage collection pollution from earlier runs.
   - Measure literal native Windows Working Set Size (Process RSS) via `K32GetProcessMemoryInfo`.
   - Distinguish CPython runtime baseline ($\approx 60-80\text{ MB}$), index heap structures, and peak working set.
3. **Disproof of Universal Memory Ceiling**:
   - Memory scales with repository size:
     - `pallets/click` (133 files): $112.7\text{ MB}$ RSS
     - `caddyserver/caddy` (605 files): $198.0\text{ MB}$ RSS (peak $272.8\text{ MB}$)
     - `etcd-io/etcd` (1,489 files): $364.1\text{ MB}$ RSS (peak $609.2\text{ MB}$)
   - Claims of a universal $\le 100\text{ MB}$ process memory ceiling on repositories exceeding 250 files are formally disproven.
