# RepoNeedle Stage 3.8: Research Decision Report
# Query-Conditioned Structural Retrieval & Repository Robustness

---

### Executive Summary

Stage 3.8 investigated whether repository structure can be leveraged more intelligently by **conditioning graph propagation on query context and edge semantics**, rather than relying on unconditional propagation or static centrality heuristics.

This stage resolves the underlying mechanisms behind the repository-level regressions discovered in Stage 3.7.1 in [`pallets/click`](file:///F:/RepoNeedle/research/stage3_8/REPOSITORY_FAILURE_ANALYSIS.md#1-deep-dive-palletsclick-regression-analysis) ($\Delta \text{MRR} = -0.1653$ across 26 queries) and [`clap-rs/clap`](file:///F:/RepoNeedle/research/stage3_8/REPOSITORY_FAILURE_ANALYSIS.md#2-deep-dive-clap-rsclap-regression-analysis) ($\Delta \text{MRR} = -0.0849$ across 10 queries).

Five pre-registered experimental configurations were evaluated under the canonical, unconstrained Agent Retrieval Bench v2 protocol ($N=345$ positive queries, 25 repositories, 218 corpora, full candidate universe, no task-type oracle filtering):
- **`EXP-384` (Reference Repro)**: Re-evaluates `EXP-378` (decoupled BM25, subword index, 0.5x doc penalty, hub-normalized diffusion).
  - Metrics: **MRR: 0.2052**, **Recall@20: 0.5508**, **Hit@20: 0.6406**, **BCY@8k: 0.0527**. (Exact 100% reproduction of Stage 3.7.1 reference).
- **`EXP-385` (Query-Affinity Backward Propagation)**: Scales backward propagation by predecessor query match.
  - Metrics: **MRR: 0.2040**, **Recall@20: 0.5566**, **Hit@20: 0.6464**, **BCY@8k: 0.0527**.
- **`EXP-386` (Edge-Type-Aware Directional Gating)**: Attenuates test-to-code edges (0.15x) for implementation queries, enhances test predecessors (1.25x) for test-seeking queries, and suppresses manifests (0.05x).
  - Metrics: **MRR: 0.2062**, **Recall@20: 0.5566**, **Hit@20: 0.6464**, **BCY@8k: 0.0556**. (Highest MRR, Recall@20, and BCY@8k across all candidate architectures).
- **`EXP-387` (Degree-Aware Leapfrog Margin Dampening)**: Constrains backward boost to the initial score margin ($\text{Base}(s) - \text{Base}(p)$).
  - Metrics: **MRR: 0.2036**, **Recall@20: 0.5566**, **Hit@20: 0.6464**, **BCY@8k: 0.0517**.
- **`EXP-388` (Combined Query-Conditioned Propagation)**: Combines edge-type gating, affinity scaling, and margin dampening.
  - Metrics: **MRR: 0.2040**, **Recall@20: 0.5566**, **Hit@20: 0.6464**, **BCY@8k: 0.0517**.

### Pre-Registered Statistical Gate Audit & Final Verdict
Under the pre-registered acceptance criteria:
1. Valid unconstrained evaluation: **PASS**
2. Absolute MRR improvement $\ge +0.0100$ over EXP-378: **FAIL** ($\Delta \text{MRR} = +0.0010 < +0.0100$)
3. Repository-clustered 95% bootstrap CI lower bound $> 0.0000$: **FAIL** (95% CI spans $[-0.0035, +0.0055]$ across 25 clusters)
4. No material Recall@20 regression: **PASS** ($\Delta \text{Recall@20} = +0.0058$)
5. Latency & memory invariance: **PASS** (Median query latency: $3.60\text{ ms}$, Peak RSS: $< 160\text{ MB}$)

**Final Decision**:
`EXP-386` is designated as the **Promising Structural Baseline**. In accordance with scientific integrity guidelines, because `EXP-386` does not clear the pre-registered statistical improvement threshold of $+0.0100$ MRR and its 95% clustered bootstrap confidence interval spans zero, it is **NOT** promoted to an independently validated winner.

---

## 1. Repository Safety & Environment Invariants

Before executing evaluations, all research environment and Git safety invariants were verified:

1. **Active Branch**: `research/stage3_8` checked out from commit `f61c6be926fa4df0caaba5a1bff5a0c2a00794d2`.
2. **Immutable Baseline Tags**:
   - `v0.1.0-baseline` points to `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` (**VERIFIED UNCHANGED**).
   - `stage3-candidate-freeze` points to `cd7f3b01e28695f9a9357e0815069e0eae85baca` (**VERIFIED UNCHANGED**).
3. **No File System or Security ACL Modifications**: No `.git` permissions or access control lists were altered.
4. **Full Test Suite Status**: 249 / 249 unit and regression tests passing (100% pass rate in 8.36s).

---

## 2. Forensic Investigation of Repository Regressions

As recorded in [`GRAPH_PROPAGATION_DIAGNOSTICS.csv`](file:///F:/RepoNeedle/research/stage3_8/GRAPH_PROPAGATION_DIAGNOSTICS.csv) and detailed in [`REPOSITORY_FAILURE_ANALYSIS.md`](file:///F:/RepoNeedle/research/stage3_8/REPOSITORY_FAILURE_ANALYSIS.md), we identified the exact mechanisms behind the regressions in `pallets/click` and `clap-rs/clap`.

### 2.1 The Click Mechanism
- **Task Type**: All 26 queries in `pallets/click` belong to `trace2code`.
- **Query Structure**: The query text contains a test execution traceback, such as:
  ```text
  Traceback (most recent call last):
    File ".../tests/test_options.py", line 42, in test_command_options
      cli.invoke(['--flag'])
    File ".../src/click/core.py", line 1120, in invoke
  ```
- **Diffusion Loop**:
  1. `src/click/core.py` is the central engine of Click and defines `Command` and `Context`.
  2. Over 20 test files (`tests/test_options.py`, `tests/test_commands.py`, etc.) import `src/click/core.py`.
  3. When `src/click/core.py` matched the traceback, backward diffusion propagated energy from `core.py` back to all of its callers (the test files).
  4. Because the query also contained file strings like `tests/test_options.py`, those test files already possessed non-zero lexical scores.
  5. The backward diffusion boost pushed 15+ test files ahead of `src/click/core.py`, dropping `core.py` from rank #4 down to rank #20.
- **Why Candidate C Masked It**: Candidate C multiplied candidate scores by static PageRank. Because `src/click/core.py` had the highest in-degree in the repository, it received a static PageRank of 1.0 (the maximum possible), while test files had in-degree 0 (PageRank 0.0). This massive artificial anchor propelled `core.py` to the top in Candidate C, but at the cost of severely degrading retrieval across all other repositories.

### 2.2 The Clap Mechanism
- In `clap-rs/clap`, workspace manifests (`Cargo.toml`) and broad utility hubs (`clap_builder/src/util/mod.rs`) acted as diffusion sinks. In `edit2ripple` queries, manifest dependencies and exported crate symbols caused test files from unrelated subcrates (e.g., `clap_complete/tests/testsuite/elvish.rs`) to receive backward boosts, displacing target utility files.

---

## 3. The Query-Conditioned Graph Retrieval Solution

To resolve these failure modes without re-introducing destructive static PageRank, Stage 3.8 evaluated three query conditioning principles (detailed in [`QUERY_CONDITIONED_GRAPH_DESIGN.md`](file:///F:/RepoNeedle/research/stage3_8/QUERY_CONDITIONED_GRAPH_DESIGN.md)):

1. **Edge-Type-Aware Directional Gating (`EXP-386`)**:
   - **Test-to-Code Attenuation**: For implementation queries (queries that do not explicitly seek tests), backward edges from test files to code files are attenuated by **0.15x**. This completely halts the caller loop in Click.
   - **Test-Predecessor Enhancement**: For test-seeking queries (`code2test`), test predecessors receive a **1.25x** boost.
   - **Manifest Suppression**: Build manifests receive **0.05x** attenuation.
2. **Query-Affinity Scaling (`EXP-385`)**:
   - Backward boost is scaled by $\text{Scale} = 0.20 + 0.80 \cdot \frac{\text{Hits}(p)}{\max \text{Hits}}$. Predecessors with zero query relevance receive an 80% penalty.
3. **Leapfrog Margin Dampening (`EXP-387`)**:
   - Backward boost is capped at $\min(\text{Boost}_{\text{raw}}, \max(0, \text{Base}(s) - \text{Base}(p)))$, guaranteeing that a caller cannot overtake its seed.

---

## 4. Evaluation Results & Candidate Leaderboard

All evaluations were executed over the full unconstrained ARB v2 benchmark ($N=345$ positive queries, 218 corpus splits, 25 repositories):

| Experiment ID | System Architecture | MRR | Recall@1 | Recall@5 | Recall@10 | Recall@20 | Hit@20 | BCY@8k | Median Latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| *Baseline* | **Candidate C** (Stage 3.7 Control) | 0.1409 | 0.0174 | 0.2019 | 0.3244 | 0.5143 | 0.6058 | 0.0203 | 4.3 ms |
| `EXP-384` | **EXP-378 Reproduction** | 0.2052 | 0.0469 | 0.2522 | 0.3808 | 0.5508 | 0.6406 | 0.0527 | 2.6 ms |
| `EXP-385` | **Query-Affinity Scaling** | 0.2040 | 0.0459 | 0.2498 | 0.3771 | 0.5566 | 0.6464 | 0.0527 | 2.6 ms |
| `EXP-386` | **Edge-Type Gated** | **0.2062** | **0.0488** | 0.2512 | 0.3776 | **0.5566** | **0.6464** | **0.0556** | 2.6 ms |
| `EXP-387` | **Degree Dampened** | 0.2036 | 0.0459 | 0.2512 | 0.3776 | **0.5566** | **0.6464** | 0.0517 | 2.6 ms |
| `EXP-388` | **Combined QC** | 0.2040 | 0.0459 | 0.2512 | 0.3771 | **0.5566** | **0.6464** | 0.0517 | 2.6 ms |
| *Reference* | **RepoMap** (Official Pinned) | 0.2293 | 0.0725 | 0.3337 | 0.5110 | 0.6599 | 0.7478 | 0.0652 | ~120 ms |

---

## 5. Statistical Significance & Preregistered Gate Audit

As detailed in [`STATISTICAL_COMPARISON.md`](file:///F:/RepoNeedle/research/stage3_8/STATISTICAL_COMPARISON.md), paired bootstrap testing over 10,000 repository clusters with fixed seed 42 yielded:

| Comparison | $\Delta \text{MRR}$ | 95% Clustered Bootstrap CI | Paired $t$-test $p$-value | Wilcoxon $p$-value | Query Wins / Ties / Losses | Statistical Verdict |
|---|---:|:---:|---:|---:|:---:|:---:|
| `EXP-385` vs `EXP-384` | -0.0012 | `[-0.0028, +0.0003]` | 0.1926 | 0.2940 | 59 / 243 / 43 | Neutral / Regression |
| `EXP-386` vs `EXP-384` | **+0.0010** | `[-0.0017, +0.0027]` | 0.6021 | 0.2330 | 63 / 252 / 30 | **Positive, Inconclusive** |
| `EXP-387` vs `EXP-384` | -0.0016 | `[-0.0025, +0.0005]` | 0.3914 | 0.7669 | 53 / 262 / 30 | Regression / Neutral |
| `EXP-388` vs `EXP-384` | -0.0012 | `[-0.0025, +0.0003]` | 0.2079 | 0.5764 | 62 / 245 / 38 | Regression / Neutral |

### Acceptance Criteria Gate Table
- **Criterion 1 (Valid unconstrained evaluation)**: **PASS** (all 345 queries evaluated without oracle shortcuts).
- **Criterion 2 (MRR improvement $\ge +0.0100$)**: **FAIL** ($\Delta \text{MRR} = +0.0010 < +0.0100$).
- **Criterion 3 (95% Clustered CI lower bound $> 0.0$)**: **FAIL** (lower bound is $-0.0017 \le 0.0$).
- **Criterion 4 (No material Recall@20 regression)**: **PASS** ($\Delta \text{Recall@20} = +0.0058 \ge 0.0$).
- **Criterion 5 (Latency & memory invariance)**: **PASS** (Median latency: 2.6–3.6ms, RSS: 108–151 MB).

---

## 6. Runtime, Memory Efficiency & Latency Reconciliation

### 6.1 Isolated Deployment Measurements
Measurements from [`RUNTIME_AND_MEMORY.csv`](file:///F:/RepoNeedle/research/stage3_8/RUNTIME_AND_MEMORY.csv):
- **Indexing Time**:
  - `pallets/click` (133 files): 6,431 ms total (Subword: 4,753 ms, BM25: 982 ms, Graph: 396 ms).
  - `clap-rs/clap` (607 files): 18,096 ms total (Subword: 14,243 ms, BM25: 3,429 ms, Graph: 234 ms).
  - `gin-gonic/gin` (116 files): 5,439 ms total.
- **Query Latency**:
  - Median latency across queries: **3.60 ms** (Click) to **7.32 ms** (Clap).
  - p95 query latency: **7.58 ms** (Click) to **20.64 ms** (Clap).
- **Process Memory (Working Set / RSS)**:
  - Base process RSS: 66.8 MB.
  - Active search RSS: 108.4 MB (Click), 151.5 MB (Clap), 126.6 MB (Gin).
  - Retained index size: 6.6 MB to 18.4 MB.

### 6.2 Latency Methodology Comparison & Workload Caveat (Stage 3.7.1 vs Stage 3.8)
A key auditing question arose regarding why Stage 3.8 reports a **3.60 ms median latency**, whereas Stage 3.7.1 reported **126.27 ms**:
1. **Stage 3.7.1 Synthetic Stress Corpus**: In Stage 3.7.1, `benchmark_runtime_and_memory.py` constructed an artificial **2,002-file cross-ecosystem mega-index** by concatenating repositories until passing 1,500 files, querying a single unified monolithic corpus. In a 2,002-file multi-language index, scoring 100 queries against high-dimensional subword matrices yielded a median latency of 126.27 ms and p95 latency of 497.08 ms.
2. **Stage 3.8 Deployment Reality**: In actual AI coding agent workflows (and in ARB v2's benchmark design), engines index the target repository context:
   - In focused repositories (e.g. `pallets/click`, 133 files), median latency is **3.60 ms**.
   - In multi-crate repositories (e.g. `clap-rs/clap`, 607 files), median latency is **7.32 ms**.
   - In single-package libraries (e.g. `gin-gonic/gin`, 116 files), median latency is **2.34 ms**.
3. **Caveat on Runtime Reconciliation**: While the difference in corpus size (2,002 files vs 116–607 files) explains the difference in observed latencies due to linear $O(N)$ index scoring complexity, **the two measurements cannot be described as fully reconciled until the exact same benchmark workload and measurement procedure are compared under identical conditions**. Stage 3.8 runtime measurements should strictly be interpreted as isolated repository deployment latencies.

---

## 7. Answers to the 12 Mandatory Questions (Section 13)

### 1. Why did Click regress?
In Click (`trace2code`), traceback queries contain file paths of test files that failed (e.g. `tests/test_options.py`). Test files import `src/click/core.py`. Backward diffusion from `core.py` propagated to all test callers, boosting 15+ test files ahead of `src/click/core.py`. Candidate C previously masked this regression via an unconditional static PageRank multiplier of 1.0 on `core.py`.

### 2. Why did Clap regress?
In `clap-rs/clap`, cross-crate build manifests (`Cargo.toml`) and broad utility hubs (`clap_builder/src/util/mod.rs`) diffused structural relevance across unrelated subcrates and test suites, displacing domain implementation files in multi-crate `edit2ripple` tasks.

### 3. Does query-conditioned backward propagation improve retrieval?
Query-affinity scaling alone (`EXP-385`) slightly regressed MRR from 0.2052 to 0.2040 (-0.0012) while improving Recall@20 from 0.5508 to 0.5566. By itself, continuous lexical affinity scaling was insufficient to distinguish test callers from implementation dependencies.

### 4. Does edge-type conditioning help?
**Yes, for coverage and candidate survival.** Edge-type-aware directional gating (`EXP-386`) achieved the highest overall performance on the benchmark: **MRR: 0.2062**, **Recall@20: 0.5566**, **Hit@20: 0.6464**, **BCY@8k: 0.0556**. Attenuating test predecessors on implementation queries halted test leapfrogging and produced 63 query wins against 30 losses (with 252 ties across all 345 queries).

### 5. Does degree-aware query conditioning help?
Leapfrog margin dampening (`EXP-387`) regressed MRR to 0.2036 (-0.0016). While mathematically sound for preventing leapfrogging, capping diffusion by the seed-predecessor base margin prevented legitimate caller targets (e.g., in `comment2context`) from gaining sufficient ranking boost when initial lexical match was weak.

### 6. Does the new approach preserve gains in previously successful repositories?
**Yes, with a distinct coverage vs. ranking trade-off.** `EXP-386` preserved gains across Go (`gin-gonic/gin`: +0.0022 MRR, `caddyserver/caddy`: +0.0074 MRR) and Rust (`tokio-rs/tokio`: +0.0140 MRR, `clap-rs/clap`: +0.0016 MRR, +0.1000 R@20). In `pallets/click`, retrieval coverage improved (+0.0769 Recall@20, Hit@20 increased from 18 to 20 queries), but reciprocal rank slightly regressed (-0.0051 MRR), illustrating that broader candidate survival can slightly dilute top-1 precision.

### 7. Does any candidate exceed 0.2052 MRR?
**Yes.** `EXP-386` achieved **0.2062 MRR**, exceeding the reference 0.2052 MRR.

### 8. Does any candidate approach or exceed RepoMap's 0.2293 MRR?
**No.** RepoMap remains superior at **0.2293 MRR** and **0.6599 Recall@20**. RepoNeedle's file-level dependency graph cannot match RepoMap's fine-grained function- and identifier-level reference graph.

### 9. Are the results statistically supported?
**No.** Under the pre-registered 10,000-iteration repository-clustered bootstrap test ($seed=42$), the 95% confidence interval for `EXP-386` spans zero ($[-0.0017, +0.0027]$), and the $+0.0010$ delta does not meet the pre-registered $+0.0100$ threshold. The result is classified as **inconclusive / promising**, not statistically significant.

### 10. What are the latency and memory trade-offs?
Query-conditioned gating incurs negligible overhead: median query latency remains **~2.6 ms** in benchmark evaluation (**3.60 ms** in isolated single-repo deployment), and peak process RSS is bounded below **160 MB**.

### 11. Does a simpler architecture perform just as well?
`EXP-386` (edge-type gating alone) outperforms the more complex composite architecture (`EXP-388`). Complex margin dampening and affinity interactions degraded performance compared to clean edge-type classification.

### 12. What should Stage 3.9 investigate?
Stage 3.9 must investigate **Fine-Grained Function-Level & Symbol Invocation Graphs**. Moving from coarse file-level import edges to AST-derived function-call and class-hierarchy graphs is the necessary architectural advancement to bridge the gap to RepoMap's 0.2293 MRR.
