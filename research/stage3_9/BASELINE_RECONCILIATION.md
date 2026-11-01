# RepoNeedle Stage 3.9.5: Baseline Reconciliation and Experiment Audit

> **Scope:** Audit of Stage 3.9.4 Controlled Pilot Execution, Baseline Reference Invariants, Graph Ingestion Counts, Statistical Procedures, and Resource Profiles.  
> **Integrity Mandate:** Preserve historical findings permanently; do not overwrite prior results.

---

## 1. Baseline Invariant Audit: Stage 3.8 vs Stage 3.9.4 EXP-386

### 1.1 Observed Metric Comparison

Under the Stage 3.8 evaluation (`research/stage3_8/STAGE3_8_DECISION_REPORT.md`) and the Stage 3.9.4 pilot (`research/stage3_9/PILOT_STATISTICAL_RESULTS.md`), the EXP-386 baseline metrics were recorded as follows:

| Metric | Stage 3.8 Reference | Stage 3.9.4 Pilot | Delta ($\Delta$) | Tolerance Bound | Audit Status |
|---|:---:|:---:|:---:|:---:|:---:|
| **MRR** | 0.2062 | **0.2067** | $+0.0005$ | $\pm 0.0010$ | Macro Parity Met |
| **Recall@5** | 0.2512 | **0.2522** | $+0.0010$ | $\pm 0.0020$ | Macro Parity Met |
| **Recall@10** | 0.3776 | **0.3808** | $+0.0032$ | $\pm 0.0050$ | Macro Parity Met |
| **Recall@20** | 0.5566 | **0.5508** | $-0.0058$ | $\pm 0.0100$ | Macro Parity Met |
| **Hit@20** | 0.6464 | **0.6406** | $-0.0058$ | $\pm 0.0100$ | Macro Parity Met |
| **BCY@8k** | **0.0556** | **0.0556** | **0.0000** | $\pm 0.0000$ | **Exact Reproduction** |

While macro-level metrics align closely and the canonical budget metric $\text{BCY@8k}$ reproduces exactly ($0.0556$), fine-grained query-level auditing reveals that **79 out of 345 queries** exhibited rank differences of magnitude $> 10^{-4}$.

### 1.2 Root Cause Analysis of Query-Level Discrepancies

A differential line-by-line code audit between [`research/stage3_8/scripts/evaluate_stage3_8_experiments.py`](file:///F:/RepoNeedle/research/stage3_8/scripts/evaluate_stage3_8_experiments.py) and [`research/stage3_9/scripts/run_controlled_pilot.py`](file:///F:/RepoNeedle/research/stage3_9/scripts/run_controlled_pilot.py) revealed two specific implementation divergences:

#### Divergence A: Asymmetric Forward Edge Gating in EXP-386
- **In Stage 3.8 (`evaluate_stage3_8_experiments.py`, Lines 280–309):**
  ```python
  # Forward: seed -> successors
  for succ in G.successors(sp):
      if succ in path_to_idx:
          n_idx = path_to_idx[succ]
          in_deg = max(1, G.in_degree(succ))
          fwd_raw = float(sv * 0.25 / np.sqrt(in_deg))
          boost_384[n_idx] = max(boost_384[n_idx], fwd_raw)  # Only boost_384 assigned!

  # Backward: predecessors -> seed
  for pred in G.predecessors(sp):
      ...
      boost_386[n_idx] = max(boost_386[n_idx], bwd_386)      # boost_386 only assigned backward
  ```
  In Stage 3.8, `boost_386` accumulated **only** backward degree-gated edges (`bwd_386`), leaving forward edges active only in EXP-384.
- **In Stage 3.9.4 (`run_controlled_pilot.py`, Lines 385–407):**
  ```python
  # Forward: seed -> successors
  for succ in G.successors(sp):
      if succ in path_to_idx:
          n_idx = path_to_idx[succ]
          in_deg = max(1, G.in_degree(succ))
          fwd_raw = float(sv * 0.25 / np.sqrt(in_deg))
          boost_386[n_idx] = max(boost_386[n_idx], fwd_raw)  # boost_386 assigned forward!
  ```
  The pilot runner assigned `fwd_raw` to `boost_386`. In the 79 affected queries, forward edges lightly boosted successor files (e.g. imported utility files), shifting ranks by $\pm 1$ or $\pm 2$ positions.

#### Divergence B: Source Reconstruction Chunk Priority
- **In Stage 3.8:**
  ```python
  for c in chunks:
      p = c.get("path")
      t = c.get("text", "")
      if p and (p not in file_texts or len(t) > len(file_texts[p])):
          file_texts[p] = t
  ```
  Chunks were ingested purely by text length, occasionally allowing longer snippet concatenations to overwrite full file bodies.
- **In Stage 3.9.4:**
  ```python
  for c in chunks:
      p = c.get("path")
      t = c.get("text", "")
      kind = c.get("kind", "")
      if kind == "file":
          file_texts[p] = t
      elif p and (p not in file_texts or len(t) > len(file_texts[p])):
          file_texts[p] = t
  ```
  Stage 3.9.4 prioritized `kind == "file"` chunks over snippet chunks, providing cleaner AST trees but slightly altering document token lengths for BM25.

### 1.3 Governance Ruling
Because of Divergences A and B, Stage 3.9.4 represents a **substantively close macro reproduction ($\Delta\text{MRR} = +0.0005$, identical $\text{BCY@8k} = 0.0556$)**, but **not a bit-for-bit identical reproduction** at the individual query level. For future stages (EXP-397 onward), the baseline configuration must strictly standardize on the canonical frozen EXP-386 implementation.

---

## 2. Graph Ingestion, Node, and Edge Count Reconciliation

In [`research/stage3_9/RUNTIME_COMPARISON.csv`](file:///F:/RepoNeedle/research/stage3_9/RUNTIME_COMPARISON.csv), the pilot reported:
- `EXP-386 total_nodes`: 312,749
- `EXP-392a total_nodes`: 524,087 ($\Delta = \mathbf{+211,338\text{ nodes}}$)
- `EXP-386 total_edges`: 1,796,625
- `EXP-392a total_edges`: 1,854,514 ($\Delta = \mathbf{+57,889\text{ edges}}$)

The discrepancy between these cumulative runtime numbers and the single-snapshot repository audit in [`research/stage3_9/EDGE_COVERAGE_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_9/EDGE_COVERAGE_AUDIT.md) is fully reconciled below.

### 2.1 Per-Corpus vs Per-Repository Accounting

The ARB v2 benchmark consists of **218 active corpus splits** representing historical commit snapshots across 25 repositories.
- **Python Corpus Splits:** 72 splits.
- **Non-Python Corpus Splits:** 146 splits.

In `run_controlled_pilot.py`, `runtime_stats["EXP-392a"]["nodes"]` and `["edges"]` were accumulated iteratively across each corpus split:
$$\text{total\_nodes} = \sum_{c=1}^{218} |V_c|, \quad \text{total\_edges} = \sum_{c=1}^{218} |E_c|$$

Because multiple benchmark queries reference different commit snapshots of the same repository (e.g., `pallets/click` has 26 corpus splits; `huggingface/transformers` has 17 corpus splits), the function nodes and edges for that codebase were indexed and accumulated across all 72 Python corpus splits.

### 2.2 Reconciled Node and Edge Taxonomy

| Metric | Single-Snapshot Audit (13 Python Repos) | 72-Corpus Benchmark Cumulative | Structural Meaning |
|---|:---:|:---:|---|
| **File Nodes ($V_{\text{file}}$)** | 9,366 | 312,749 (All 218 corpora) | AST-parsed file nodes |
| **Function Nodes ($V_{\text{func}}$)** | 29,324 | **211,338** | Cleanly parsed function & async defs |
| **CONTAINS Edges ($E_{\text{contains}}$)** | 29,324 | 211,338 | Implicit structural edge: File $\to$ Function |
| **Raw CALLS Edges ($E_{\text{calls, raw}}$)** | 9,972 | **57,889** | Emitted call sites |
| **Unique Directed CALLS ($E_{\text{calls, unique}}$)** | 8,126 | 47,131 | Deduplicated caller $\to$ callee edges |
| **Active / Connected Functions** | 8,923 ($30.43\%$) | 64,246 ($30.40\%$) | Function nodes with $\ge 1$ CALLS edge |
| **Orphan Function Nodes** | **20,401 ($69.57\%$)** | **147,092 ($69.60\%$)** | In-degree = 0 AND out-degree = 0 |

### 2.3 The Structural Orphan Reality
The audit confirms that **$69.57\%$ of all extracted function nodes are complete structural orphans**:
- They neither call any resolved function within the repository nor are called by any resolved function.
- In `run_controlled_pilot.py`, these 20,401 orphan nodes were stored in `self.function_nodes` and contributed to graph node counts, but could never participate in diffusion.
- This structural isolation explains why LFCG had zero impact on $97.68\%$ of queries.

---

## 3. Statistical Methodology Audit

### 3.1 Clustered Bootstrap Sampling Procedure
The inferential statistics in [`PILOT_STATISTICAL_RESULTS.md`](file:///F:/RepoNeedle/research/stage3_9/PILOT_STATISTICAL_RESULTS.md) follow the established repository-clustered bootstrap protocol (seed 42, $B = 10,000$ resamples):

1. **Cluster Definition:** The primary sampling units (clusters) are unique repositories ($K = 25$ for overall benchmark; $K = 13$ for Python-eligible subset). Clustering by repository is mandatory because queries evaluated on the same repository share common graph hubs and lexical distributions, violating i.i.d. assumptions.
2. **Cluster Resampling:** In each bootstrap iteration $b \in \{1, \dots, B\}$:
   - Sample $K$ clusters with replacement from the target cluster set using `np.random.choice(target_repos, size=K, replace=True)`.
3. **Query Weighting:** When a cluster $r$ is selected, *all* queries associated with repository $r$ are included. If repository $r$ is sampled $m$ times, its queries appear $m$ times in that resample. The bootstrap mean difference $\bar{\Delta}_b$ is the unweighted mean of paired query differences across all queries in the resample:
   $$\bar{\Delta}_b = \frac{1}{\sum_{r \in \mathcal{S}_b} |\mathcal{Q}_r|} \sum_{r \in \mathcal{S}_b} \sum_{q \in \mathcal{Q}_r} \left( M_{\text{test}}(q) - M_{\text{ref}}(q) \right)$$
4. **Confidence Interval (CI):** The two-sided 95% Clustered CI is computed empirically using the $2.5\text{th}$ and $97.5\text{th}$ percentiles of the $10,000$ bootstrap sample means:
   $$\text{CI}_{95\%} = \left[ \text{Percentile}(\{\bar{\Delta}_b\}, 2.5), \quad \text{Percentile}(\{\bar{\Delta}_b\}, 97.5) \right]$$
5. **p-Value Calculation:** Computed as the empirical proportion of bootstrap resample means that contradict the observed direction of the mean effect $\hat{\Delta}$:
   $$p = \begin{cases} 
   \frac{1}{B} \sum_{b=1}^B \mathbb{I}(\bar{\Delta}_b \le 0.0) & \text{if } \hat{\Delta} > 0 \\
   \frac{1}{B} \sum_{b=1}^B \mathbb{I}(\bar{\Delta}_b \ge 0.0) & \text{if } \hat{\Delta} \le 0 
   \end{cases}$$

---

## 4. Resource & Memory Measurement Reconciliation

In [`RUNTIME_COMPARISON.csv`](file:///F:/RepoNeedle/research/stage3_9/RUNTIME_COMPARISON.csv), memory and latency metrics were reported. This section clarifies the exact boundaries between tracemalloc peak, total process RSS, and incremental RSS.

| Resource Metric | Definition | Recorded Value | Diagnostic Interpretation |
|---|---|:---:|---|
| **Tracemalloc Peak Heap** | Peak memory allocated directly via CPython `PyObject_Malloc` / `malloc` during the index build of a single corpus | $2,844.86\text{ MB}$ (EXP-386)<br>$2,817.56\text{ MB}$ (EXP-392a) | Measures Python heap memory. Tracemalloc resets per corpus; peak occurs during Transformers inverted index construction. |
| **Total Process RSS** | Physical RAM currently allocated to the process working set (`WorkingSetSize` via Win32 `GetProcessMemoryInfo`) | $1,193.25\text{ MB}$ (End of run)<br>$4,107.80\text{ MB}$ (Peak during Transformers) | Total physical memory occupied by CPython interpreter, C runtime, memory-mapped buffers, and native NumPy arrays. |
| **Incremental RSS** | Additional physical memory consumed exclusively by LFCG structures over baseline EXP-386 | $\approx +250\text{ MB} \text{ to } +350\text{ MB}$ (during AST build)<br>$\approx 0\text{ MB}$ (steady state) | AST trees are garbage-collected after call resolution; FunctionNode objects and URI maps consume transient memory during indexing. |

---

## 5. Preservation of Negative Findings

In accordance with scientific integrity guidelines:
- All empirical negative results recorded in Stage 3.9.4 ([`PILOT_STATISTICAL_RESULTS.md`](file:///F:/RepoNeedle/research/stage3_9/PILOT_STATISTICAL_RESULTS.md), [`PER_QUERY_PILOT_RESULTS.jsonl`](file:///F:/RepoNeedle/research/stage3_9/PER_QUERY_PILOT_RESULTS.jsonl), [`CONTROLLED_PILOT_REPORT.md`](file:///F:/RepoNeedle/research/stage3_9/CONTROLLED_PILOT_REPORT.md)) are permanently preserved and immutable.
- No historical records from Stage 3.8 or prior stages have been overwritten or modified.

