# RepoNeedle V1.0.0 — Milestone 2 Final Statistical Reconciliation

**Role**: Independent Statistical Auditor & Principal Research Engineer  
**Scope**: 345 Benchmark Queries (514 Gold Targets across 25 Repositories)  
**Branch**: `v1.0-zero-failure` (Frozen baseline `v0.1.0-release` strictly protected)  
**Reference Source Data**:
- `research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl` (345 queries, 560,220 candidates)
- `research/v1_accuracy/m2_recovery/PER_QUERY_RANK_MOVEMENTS.jsonl` (345 per-query evaluated rank records)
- `research/v1_accuracy/m2_recovery/M2_RECOVERY_RAW_RESULTS.jsonl` (345 per-query top-50 candidate score arrays)
- `research/v1_accuracy/m2_recovery/m2_recovery_metrics_summary.json` (Raw floating-point metrics & bootstrap ledger)

---

## 1. Treatment F Metric Reconciliation

An independent statistical audit was conducted to resolve numerical discrepancies observed across the executive summary, ablation table, and bootstrap table for Treatment F (`m1_evidence_gated_combined`) versus Treatment A (`m1_baseline`).

### 1.1 Exact Unrounded Sample Metrics

All metrics were recomputed directly from the 345 raw query records and 514 annotated gold targets with IEEE 754 double-precision arithmetic:

| Metric | Treatment A (M1 Baseline) | Treatment F (Evidence-Gated) | Exact Unrounded Delta ($\text{F} - \text{A}$) |
| :--- | :---: | :---: | :---: |
| **MRR** | `0.2674802018637315` | `0.2695338064779998` | **`+0.0020536046142683`** |
| **Hit@1** | `0.0898550724637681` (31/345) | `0.0927536231884058` (32/345) | **`+0.0028985507246377`** (+1 query) |
| **Micro Recall@1** | `0.0603112840466926` (31/514) | `0.0622568093385214` (32/514) | **`+0.0019455252918288`** (+1 target) |
| **Micro Recall@5** | `0.3599221789883268` (185/514)| `0.3579766536964981` (184/514)| **`-0.0019455252918288`** (-1 target) |
| **Micro Recall@10**| `0.4902723735408560` (252/514)| `0.4883268482490272` (251/514)| **`-0.0019455252918288`** (-1 target) |
| **Micro Recall@20**| `0.5953307392996109` (306/514)| `0.5972762645914397` (307/514)| **`+0.0019455252918288`** (+1 target) |
| **Macro Recall@20**| `0.6354589371980677` | `0.6417391304347826` | **`+0.0062801932367149`** |
| **Micro Recall@50**| `0.7645914396887159` (393/514)| `0.7626459143968871` (392/514)| **`-0.0019455252918288`** (-1 target) |
| **Macro Recall@50**| `0.7943478260869565` | `0.7928985507246377` | **`-0.0014492753623188`** |
| **Complete Cov@20**| `0.5507246376811594` (190/345)| `0.5565217391304348` (192/345)| **`+0.0057971014492754`** (+2 queries) |
| **Complete Cov@50**| `0.7130434782608696` (246/345)| `0.7130434782608696` (246/345)| **`+0.0000000000000000`** (0 queries) |
| **Candidate Recall**| `1.0000000000000000` (514/514)| `1.0000000000000000` (514/514)| **`+0.0000000000000000`** |

---

### 1.2 Reconciliation of MRR Discrepancies

- **Observed Values**:
  - Executive Summary Delta: `+0.0021`
  - Ablation Table Delta: `+0.0020` (approximate)
  - Bootstrap Table Delta: `+0.0024`

- **Mathematical Reconciliation**:
  1. **Exact Sample Delta**: $\Delta \text{MRR} = 0.2695338065 - 0.2674802019 = \mathbf{+0.0020536046}$.
     When rounded to four decimal places, $0.0020536...$ rounds to **`+0.0021`**, which was reported in the executive summary.
  2. **Table Pre-Rounding Artifact**: In the ablation table, the baseline MRR was displayed as $0.2675$ and Treatment F was displayed as $0.2695$. If a reader or script takes the difference of the pre-rounded table entries:
     $$0.2695 - 0.2675 = \mathbf{+0.0020}$$
     This accounts for the reported `+0.0020` approximate figure.
  3. **Bootstrap Resampling Discrepancy**: The bootstrap table reported $\Delta \text{MRR} = \mathbf{+0.0024008794}$ (reported as `+0.0024`).
     This difference arises because the bootstrap table recorded the **mean of the 1,000 repository-cluster bootstrap replications**:
     $$\mathbb{E}^*[\Delta^*] = \frac{1}{1000} \sum_{b=1}^{1000} \Delta^{*(b)} = +0.0024008794$$
     Because repository clusters have widely varying query counts (ranging from 1 to 88 queries per repository), cluster-level resampling with replacement introduces finite-sample cluster-weighting variations. Across 1,000 replications, the cluster-resampled mean evaluates to `+0.0024`, compared to the unweighted sample mean of `+0.00205`.

---

### 1.3 Reconciliation of Recall@20 Discrepancies

- **Observed Values**:
  - Executive Summary Delta: `+0.0019`
  - Ablation Table Delta: `+0.0020` (approximate)
  - Bootstrap Table Delta: `+0.0061`

- **Mathematical Reconciliation**:
  1. **Micro vs Macro Definition Divergence**:
     The primary cause of this discrepancy is the difference between **Micro Recall@20** and **Macro Recall@20**:
     - **Micro Recall@20** pools all 514 gold targets globally across the 345 queries:
       $$\text{Recall}_{\mu}@20 = \frac{\sum_{i=1}^{345} |G_i \cap \text{Top20}_i|}{\sum_{i=1}^{345} |G_i|} = \frac{\text{Total Targets Found}}{514}$$
       - Baseline: $306 / 514 = 0.5953307393$
       - Treatment F: $307 / 514 = 0.5972762646$
       - **Exact Micro Delta**: $1 / 514 = \mathbf{+0.0019455253}$ (rounded: `+0.0019`).
       - If calculated from rounded table figures ($0.5973 - 0.5953$), it yields `+0.0020`.
     - **Macro Recall@20** computes the unweighted arithmetic mean of per-query recalls:
       $$\text{Recall}_{M}@20 = \frac{1}{345} \sum_{i=1}^{345} \frac{|G_i \cap \text{Top20}_i|}{|G_i|}$$
       - Baseline: $0.6354589372$
       - Treatment F: $0.6417391304$
       - **Exact Macro Delta**: $\mathbf{+0.0062801932}$
  2. **Bootstrap Resampling Metric**:
     In `execute_m2_recovery_full.py`, the bootstrap loop resampled per-query metric records where `"rec20"` was stored as `in_k[20] / num_golds` (the **Macro Recall@20** definition).
     Across 1,000 repository-clustered bootstrap replications, the mean of the resampled Macro Recall@20 differences was:
     $$\mathbb{E}^*[\Delta_{\text{Macro Rec@20}}^*] = \frac{1}{1000} \sum_{b=1}^{1000} \Delta^{*(b)} = \mathbf{+0.0061057124} \quad (\approx +0.0061)$$
     The bootstrap table was reporting Macro Recall@20 ($+0.0061$), whereas the executive summary and main ablation table reported Micro Recall@20 ($+0.0019$).

---

## 2. Bootstrap Methodology & P-Value Clarification

### 2.1 Audit of the Computed Quantity

In the evaluation script `execute_m2_recovery_full.py`, the quantity reported in the "p-value" column was calculated as:
```python
p_val_mrr = np.mean(np.array(delta_mrrs) <= 0)
p_val_rec20 = np.mean(np.array(delta_rec20s) <= 0)
```
Mathematically, this evaluates the empirical tail area of the bootstrap replicates that are non-positive:
$$\hat{P}^*(\Delta^* \le 0 \mid \mathbf{X}) = \frac{1}{B} \sum_{b=1}^B \mathbb{I}(\Delta^{*(b)} \le 0)$$
where $\Delta^{*(b)} = \hat{\theta}_T^{*(b)} - \hat{\theta}_C^{*(b)}$ represents the paired difference in the $b$-th cluster-resampled bootstrap draw ($B = 1,000$).

### 2.2 Critical Distinction of Statistical Quantities

1. **Empirical Bootstrap Non-Positive Proportion ($\hat{P}^*(\Delta^* \le 0)$)**:
   - This records the **empirical bootstrap proportion of resampled treatment-effect estimates that are non-positive** across the $B = 1,000$ cluster-bootstrap replications:
     $$\hat{P}^*(\Delta^* \le 0 \mid \mathbf{X}) = \frac{1}{B} \sum_{b=1}^B \mathbb{I}(\Delta^{*(b)} \le 0)$$
   - It is calculated directly from the unconstrained bootstrap distribution, which is centered at the **observed sample estimate** $\hat{\Delta}$, not at zero.
2. **Clarification on Frequentist P-Values and Bayesian Posteriors**:
   - **Not a Conventional Frequentist P-Value**: A conventional frequentist $p$-value for testing $H_0: \Delta \le 0$ requires evaluating test statistics strictly under the null hypothesis (e.g. via cluster-permutation tests or recentered bootstrap distributions under $H_0$). The reported proportion was evaluated on unshifted draws centered at $\hat{\Delta}$. A conventional frequentist null-hypothesis $p$-value was **not calculated**.
   - **No Bayesian Posterior Calculated**: A Bayesian posterior distribution was **not calculated**. The quantity $\hat{P}^*(\Delta^* \le 0)$ is strictly an empirical frequency of unshifted bootstrap draws.
3. **Formal Uncertainty Framework: Percentile Confidence Intervals**:
   - The reported uncertainty intervals are the **preregistered 95% bootstrap percentile confidence intervals** ($\text{CI}_{95\%} = [q^*_{0.025}, \, q^*_{0.975}]$).
   - **Treatment F is not statistically established as an improvement** over the frozen M1 baseline because its 95% bootstrap confidence intervals for both MRR ($[-0.00114, +0.00975]$) and Recall@20 ($[-0.00130, +0.01600]$ for Macro, $[-0.00195, +0.00778]$ for Micro) strictly include zero ($0 \in \text{CI}_{95\%}$).

### 2.3 Hypothesis Testing via Preregistered Percentile Confidence Intervals

Under the preregistered non-parametric bootstrap methodology, statistical significance at level $\alpha = 0.05$ is determined by whether zero is excluded from the equal-tailed 95% percentile confidence interval:
$$\text{CI}_{95\%} = \left[ q^*_{0.025}, \, q^*_{0.975} \right]$$

Evaluating Treatment F against Treatment A under the original registered bootstrap method (1,000 resamples, cluster unit = repository, seed = 42):

| Metric | Sample Delta | Mean Bootstrap Delta | 95% Bootstrap Percentile CI | Zero Included in 95% CI? | Statistically Significant at $\alpha = 0.05$? |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **MRR** | `+0.00205` | `+0.00240` | **`[-0.00114, +0.00975]`** | **YES** (Spans 0) | **NO ($p > 0.05$)** |
| **Macro Recall@20** | `+0.00628` | `+0.00611` | **`[-0.00130, +0.01600]`** | **YES** (Spans 0) | **NO ($p > 0.05$)** |
| **Micro Recall@20** | `+0.00195` | `+0.00214` | **`[-0.00195, +0.00778]`** | **YES** (Spans 0) | **NO ($p > 0.05$)** |
| **Complete Cov@20** | `+0.00580` | `+0.00558` | **`[+0.00000, +0.01438]`** | **YES** (Touches 0) | **NO ($p > 0.05$)** |

**Conclusion**: Because zero is strictly contained within the 95% bootstrap confidence intervals for both MRR and Recall@20, Treatment F **fails** to demonstrate a statistically significant retrieval improvement over the frozen M1 baseline.

---

## 3. Repository Cluster Reconciliation

### 3.1 Explanation of the "21 Clusters" Discrepancy

In earlier reports (such as `M2_DECISION_REPORT.md` and `RANKING_ABLATION_RESULTS.md`), the text stated:
> *"1,000 resamples clustered at repository boundary (21 clusters)."*

**Root Cause**:
This was a **documentation copy-paste artifact** inherited from earlier project phases (Stage 3.7 / 3.8 and ContextBench prototypes), which operated on an older 21-repository evaluation scope. When the ARB v2 benchmark was expanded to 345 queries across 25 repositories, the python evaluation scripts dynamically grouped clusters via:
```python
clusters: Dict[str, List[int]] = defaultdict(list)
for idx, r in enumerate(baseline_records):
  clusters[r["repo"]].append(idx)
cluster_keys = list(clusters.keys())
k = len(cluster_keys)
```
In execution, `k` dynamically evaluated to **25**. However, the markdown reporting template contained the hardcoded literal string `"(21 clusters)"` instead of `f"({k} clusters)"`.

### 3.2 Complete Inventory of All 25 Repositories in ARB v2

Independent audit confirms that **all 25 repositories** present in the benchmark were included as resampling units. **Zero repositories were excluded.**

| # | Repository Name (`repo` key) | Query Count | Gold Target Count | Primary Language | In Resampling Pool? |
| :---: | :--- | :---: | :---: | :--- | :---: |
| 1 | `gin-gonic/gin` | 88 | 104 | Go | **YES** |
| 2 | `etcd-io/etcd` | 41 | 63 | Go | **YES** |
| 3 | `tokio-rs/tokio` | 38 | 62 | Rust | **YES** |
| 4 | `huggingface/transformers` | 36 | 63 | Python | **YES** |
| 5 | `pallets/click` | 26 | 38 | Python | **YES** |
| 6 | `vitejs/vite` | 25 | 40 | TypeScript | **YES** |
| 7 | `huggingface/diffusers` | 16 | 28 | Python | **YES** |
| 8 | `caddyserver/caddy` | 13 | 19 | Go | **YES** |
| 9 | `clap-rs/clap` | 10 | 18 | Rust | **YES** |
| 10 | `spring-projects/spring-boot` | 8 | 13 | Java | **YES** |
| 11 | `pytest-dev/pytest` | 7 | 12 | Python | **YES** |
| 12 | `vuejs/core` | 6 | 9 | TypeScript | **YES** |
| 13 | `astral-sh/ruff` | 6 | 8 | Rust | **YES** |
| 14 | `pypa/pip` | 5 | 9 | Python | **YES** |
| 15 | `microsoft/playwright` | 4 | 7 | TypeScript | **YES** |
| 16 | `fastapi/fastapi` | 3 | 5 | Python | **YES** |
| 17 | `scrapy/scrapy` | 3 | 4 | Python | **YES** |
| 18 | `ipython/ipython` | 2 | 3 | Python | **YES** |
| 19 | `tox-dev/tox` | 2 | 3 | Python | **YES** |
| 20 | `mockito/mockito` | 1 | 1 | Java | **YES** |
| 21 | `HypothesisWorks/hypothesis` | 1 | 1 | Python | **YES** |
| 22 | `eslint/eslint` | 1 | 1 | JavaScript | **YES** |
| 23 | `numpy/numpy` | 1 | 1 | Python | **YES** |
| 24 | `pydantic/pydantic` | 1 | 1 | Python | **YES** |
| 25 | `python/mypy` | 1 | 1 | Python | **YES** |
| **Total** | **25 Repositories** | **345** | **514** | **Polyglot** | **100% Included** |

### 3.3 Cluster Resampling Integrity Verification
- **Resampling Unit**: The sampling unit was strictly the repository key `r["repo"]`. In each of the 1,000 bootstrap iterations, 25 repository keys were sampled with replacement.
- **Partition Disjointness**: Each of the 345 queries has a unique string identifier and belongs to exactly one repository. No query was partitioned across multiple clusters.
- **Cluster Size Distribution**: The cluster sizes are highly skewed (min: 1 query, median: 6 queries, max: 88 queries). Clustered bootstrap correctly accounts for this intra-repository correlation.

---

## 4. Structural Evidence Denominator & Terminology Audit

### 4.1 Resolution of the 340 / 345 Proportion Calculation

Earlier working drafts reported a "98.6% structural false-positive rate" based on the ratio $340 / 345 = 98.55\%$. An independent audit was conducted to resolve the exact counting units of both the numerator and the denominator:

1. **Exact Counting Unit: Expansion Edges (Not Queries or Unique Seeds)**:
   - In `frozen_m1_candidates.jsonl`, a total of **7,149 candidate evidence edges** were generated across all 345 queries.
   - Among these 7,149 edges, exactly **345 expansion edges originated from an annotated gold target seed**. (Note: The count of 345 edges is coincidentally equal to the 345 queries in the benchmark, but its counting unit is strictly **expansion edges**).
   - Among these 345 edges originating from gold seeds:
     - **5 edges** connected to a target file that was also an annotated gold target for that query (`both_are_gold = 5`).
     - **340 edges** connected to a target file that was not in the annotated gold target set for that query (`edges_seed_gold_target_not = 340`).
   - Therefore, the exact edge-level definition is:
     $$\text{Non-Gold Expansion Edge Proportion} = \frac{\text{Non-Gold Expansion Edges from Gold Seeds}}{\text{All Expansion Edges from Gold Seeds}} = \frac{340}{345} = \mathbf{98.5507\%} \quad (\approx 98.55\%)$$
     $$\text{Gold-Coupled Expansion Edge Proportion} = \frac{\text{Gold-Coupled Expansion Edges from Gold Seeds}}{\text{All Expansion Edges from Gold Seeds}} = \frac{5}{345} = \mathbf{1.4493\%} \quad (\approx 1.45\%)$$

2. **Seed-Level Accounting (Unique Gold Query-Seed Instances)**:
   - Across the 345 benchmark queries, exactly **142 unique gold query-seed instances** triggered candidate expansion.
   - Out of these 142 gold seeds:
     - **138 gold seeds** produced at least one candidate expansion edge pointing to a non-gold target.
     - **5 gold seeds** produced at least one candidate expansion edge pointing to an annotated gold target.
   - Therefore, the exact seed-level definition is:
     $$\text{Proportion of Gold Seeds Producing } \ge 1 \text{ Non-Gold Expansion} = \frac{138}{142} = \mathbf{97.18\%}$$
     $$\text{Proportion of Gold Seeds Producing } \ge 1 \text{ Gold Expansion} = \frac{5}{142} = \mathbf{3.52\%}$$

3. **Methodological Context: Diagnostic Oracle-Seeded Expansion vs Production Inference**:
   - The analysis above is a **diagnostic oracle-seeded expansion audit** originating from known ground-truth targets. In production retrieval, gold targets are unknown.
   - A structural edge linking a gold implementation file to an imported utility or test fixture represents a valid AST/dependency coupling in the repository. It is not an erroneous static edge; rather, it connects to a **task-irrelevant file** outside the query's ground-truth resolution edit set.
   - Denominators must never be conflated: 345 is the count of **expansion edges from gold seeds**, 142 is the count of **unique gold seeds with expansions**, and 345 is the count of **benchmark queries** (of which 298 contain candidates with structural evidence).

---

## 5. Final M2 Disposition

In accordance with Section 5 of the charter and the empirical statistical reconciliation:

1. **All Failed Structural Treatments Remain Rejected**:
   - Treatment `m2_full_auto`, `m2a` (test linkage), `m2d` (composite), and `m2e` (RRF) caused catastrophic precision collapses (MRR falling from 0.2675 to 0.166–0.196) and are permanently rejected.
2. **Hub Normalization Is Formally Rejected**:
   - Treatment B (`m1_hub_norm`) improved Recall@20 (+0.0117), but caused a **statistically significant MRR regression** ($\Delta \text{MRR} = -0.0063$, 95% CI: $[-0.0113, -0.0003]$, $p = 0.9850$, 51 query losses).
   - In accordance with the release policy ("A treatment must not be promoted just because Recall@20 increases while MRR deteriorates"), hub normalization is **REJECTED** and will not be applied as a prior or filter.
3. **Evidence-Gated Combined Reranking (Treatment F) Is Formally Rejected**:
   - Treatment F maintained safety ($\Delta \text{MRR} = +0.00205$, $\Delta \text{Micro Recall@20} = +0.00195$), but its 95% bootstrap confidence intervals strictly contain zero. It cannot be certified as statistically superior to M1.
4. **Retain M1 as Authoritative Frozen Baseline**:
   - The M1 multi-channel candidate retrieval engine is the **sole authoritative production baseline**.
   - Preserved locked figures:
     - **Micro Candidate Recall**: `1.0000` (514/514)
     - **Macro Candidate Recall**: `1.0000` (345/345)
     - **Complete-Gold Coverage**: `1.0000` (345/345)
     - **MRR**: `0.2675`
     - **Hit@1**: `0.0899` (31/345)
     - **Micro Recall@20**: `0.5953` (306/514)
     - **Complete Coverage@20**: `0.5507` (190/345)
     - **Micro Recall@50**: `0.7646` (393/514)
     - **Complete Coverage@50**: `0.7130` (246/345)
5. **Milestone Disposition**:
   - Milestone 2 is formally **CLOSED**.
   - Milestone 3 is **NOT** started.
   - All experimental data, raw rankings, and audit files are preserved immutably.

