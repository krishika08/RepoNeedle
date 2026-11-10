# KNOWN LIMITATIONS AND ARCHITECTURAL BOUNDARIES: REPONEEDLE

**Applies to**: Released 1.1.0 (PyPI) and the current development branch (planned for 1.2.0, unreleased). Differences between the two are called out explicitly.  
**Originally written for**: 0.1.0 Research Preview (October 2026); last reconciled with the source code on 2026-11-09.  
**Primary Benchmark**: Agent Retrieval Bench v2 ($N=427$ samples, 25 repositories, 271 unique snapshots)

---

## 1. Executive Summary of Limitations

While RepoNeedle demonstrates substantial, statistically significant improvements over classical BM25 and Lexical search on large-scale repository retrieval (+50.5% MRR, $p < 0.001$), it exhibits concrete failure modes and architectural boundaries that preclude an unqualified general-purpose release.

This document provides transparent, unhedged documentation of every known limitation, failure mode, and architectural trade-off.

---

## 2. Failure of Heuristic Selective Abstention in Production

### The Observed Defect
On the official Agent Retrieval Bench Selective Retrieval split ($N=82$ total abstention queries across 71 frozen repository snapshots), RepoNeedle achieved **0.0% abstention accuracy (0 / 82)**:
- Natural No-Gold GitHub Issues ($N=50$): **0 / 50 correctly abstained (100% false return rate)**
- Counterfactual Wrong-Repo Tasks ($N=32$): **0 / 32 correctly abstained (100% false return rate)**

### Root Cause Analysis
The `SelectiveAbstainer` heuristic (`reponeedle/core/abstention.py`) computes a composite score over the engine's **fused ranking scores**:

$$\text{confidence} = 0.30 \cdot \min(1, Z/3) + 0.45 \cdot \text{overlap} + 0.25 \cdot \text{margin}$$

1. **Repository Vocabulary Overlap**: fraction of query tokens (length > 2) found in the repository vocabulary (paths, symbols, and identifiers from the first 3,000 characters of each file).
2. **Z-Score Peakiness**: $(s_{\max} - \mu) / \sigma$ of the fused scores.
3. **Score Margin**: top fused score minus the median fused score.

It abstains if overlap ≤ 0.10, or if confidence falls below the threshold. The engine's default threshold is **$\tau = 0.12$** (`BudgetConfig.abstention_threshold`, unchanged since the first release). The value 0.38 is only the standalone `SelectiveAbstainer` class default and is not used by the engine.

Measured on the 82 ARB v2 no-gold queries (source: `reports/full_arb_validation/checkpoint_selective.jsonl`):
1. **Natural Issues Contain Repository Vocabulary**: Issue descriptions filed against a project naturally use that project's identifiers. Overlap had a median of 0.84 (range 0.39–0.92) on natural no-gold issues; 43 of 50 exceeded 0.70.
2. **Counterfactual Queries Share Ubiquitous Software Terms**: Queries from other repositories still use universal terms (`client`, `parse`, `config`, `handler`, `error`), which match many files in a large repository. Overlap had a median of 0.81 (range 0.61–0.92); the $Z$-score had a median of 4.32 (range 1.77–7.50).
3. **Threshold Far Below Observed Scores**: Confidence on all 82 no-gold queries ranged from **0.532 to 0.891** (5th–95th percentile 0.635–0.851), so no query came near $\tau = 0.12$. Raising the threshold would not fix this without also rejecting in-scope queries, because the heuristic does not separate the two populations; it would need to be evaluated against the false-abstention rate on positive queries.

### Required Resolution
Heuristic confidence scoring based on surface lexical overlap is scientifically inadequate for repository abstention. Future versions will require a dedicated, fine-tuned cross-encoder or neural classifier trained specifically to discriminate internal bugs from out-of-scope issues. Until then, RepoNeedle's selective abstention feature must be treated as purely experimental.

### Mitigation on the Development Branch (planned 1.2.0): Disabled by Default (Behavior Change)
In released 1.1.0 the heuristic runs on every query. On the development branch it is no longer applied unless explicitly requested. The algorithm, confidence formula and threshold semantics are unchanged; only the default changed.

| Surface | How to opt in |
| :--- | :--- |
| Python API (engine-wide) | `BudgetConfig(enable_experimental_abstention=True)` |
| Python API (per call) | `engine.retrieve(..., enable_experimental_abstention=True)` (also accepts `False` to override an engine-wide opt-in) |
| CLI | `--enable-experimental-abstention` |
| MCP | `reponeedle_retrieve` argument `enable_experimental_abstention: true` |

Consequences users must understand:
- **Out-of-scope queries are not detected by default.** Retrieval returns the best-ranked files even when the repository does not contain the answer. Treat results as candidates, not as evidence that the answer exists in the repository.
- **`task_type="selective"` does not enable abstention.** It only selects routing weights. This prevents the opt-in requirement from being bypassed by a task label.
- **`confidence_score` is uncalibrated.** It is still computed on every query for schema compatibility, but it is not a probability and should not be used as an in-scope / out-of-scope classifier.
- **Empty repositories still abstain** (`abstention.status == "empty_repository"`) because there are no candidates; this is structural, not heuristic.
- Every `RetrievalResult` carries an `abstention` diagnostic object with `experimental: true` and `calibrated: false`, so downstream consumers cannot mistake the heuristic for a calibrated signal.
- Every benchmark or research script that measures the heuristic opts in explicitly, so historical abstention results remain reproducible; ordinary retrieval benchmarks use the new default. The per-script policy, and which historical results were measured under the old always-on default, are documented in [docs/BENCHMARK_CONFIGURATION.md](docs/BENCHMARK_CONFIGURATION.md) and enforced by `tests/test_documentation_consistency.py`.

---

## 3. Deep Recall Deficit Compared to RepoMap

> [!NOTE]
> Figures in this section come from the 2026-10-28 engine (README Part A). On the current engine (1.1.0 / development branch, re-measured 2026-11-09) the gap is larger: Recall@20 is 0.3842 vs RepoMap 0.6306 (RepoMap +64.2%), and BCY@8k is 0.3443 vs 0.3788 (RepoMap +10.0%). MRR remains at parity (+0.0013, repository-clustered CI [−0.0597, +0.0517]). See [docs/BENCHMARK_CONFIGURATION.md §7.3](docs/BENCHMARK_CONFIGURATION.md#73-current-engine-re-measurement-arb-v2-positive-n345).

### The Observed Defect
While RepoNeedle matches or slightly exceeds RepoMap on top-rank precision (MRR: `0.2287` vs `0.2140`, a non-significant +6.9% difference, $p=0.4089$), **RepoMap substantially outperforms RepoNeedle at high recall depth**:
- **Recall@20**: RepoMap `0.6306` vs RepoNeedle `0.4279` (**+47.4% relative advantage for RepoMap**)
- **BCY@8k**: RepoMap `0.3788` vs RepoNeedle `0.3450` (**+9.8% relative advantage for RepoMap**)
- **BCY@16k**: RepoMap `0.5235` vs RepoNeedle `0.4192` (**+24.9% relative advantage for RepoMap**)
- **BCY@32k**: RepoMap `0.6166` vs RepoNeedle `0.4279` (**+44.1% relative advantage for RepoMap**)

### Architectural Mechanism
1. **PageRank Component Connectivity**: RepoMap computes PageRank over the full identifier reference graph. When a query references a high-centrality hub, PageRank probability naturally diffuses across the entire connected subgraph, successfully capturing secondary and tertiary relevant files in positions 10 through 20.
2. **RepoNeedle Precision Focus**: RepoNeedle's multi-signal scoring and knapsack density optimization aggressively prioritize top-rank relevance density ($U_i / C_i^\gamma$). Files outside the immediate lexical or direct AST neighborhood receive low scores, causing tail recall to plateau around 0.43.
3. **Recommendation**: For applications requiring broad recall across entire sub-systems (e.g. large architectural refactorings), standalone RepoMap or hybridizing RepoNeedle with deeper graph diffusion walks is recommended.

---

## 4. Performance Deficit on High-Level Issue Comments (`comment2context`)

> [!NOTE]
> Figures in this section come from the 2026-10-28 engine. On the current engine (re-measured 2026-11-09) the deficit is slightly larger: `comment2context` MRR 0.1658 vs BM25 0.1974 (**−16.0%**), Recall@20 0.1938 vs 0.5292.
>
> A supplemental product-aligned evaluation (whole-file input for both systems, file-level full ranking; not an official ARB score) shows that much of this official-harness gap is a measurement artifact. On matched whole-file input, RepoNeedle is level with BM25 on `comment2context` MRR (−0.0026, CI includes zero). A **genuine deep-recall deficit remains**, however: Recall@20 0.4896 vs 0.5792 (−0.0896, repository-clustered 95% CI [−0.1779, −0.0056]). See `reports/experimental/phase1_product_aligned_evaluation/REPORT.md`.
>
> The existing opt-in documentation filter (`enable_doc_filter`) was tested as a mitigation in a pre-registered held-out experiment and was **not validated**: it left comment2context Recall@20 unchanged on held-out repositories (Δ 0.000), though it removed documentation from top ranks and showed no regressions. It also demoted 1 of 4 gold documentation files in development data. It remains off by default. See `reports/experimental/phase2_documentation_filter/REPORT.md`.
>
> Lexical forensics (development data only) attribute most of RepoNeedle's comment2context lexical gap to its BM25 index **ignoring query term frequency**, plus duplicate token counting. Accounting for query term frequency also harms trace2code on development data, so no change has been made. See `reports/experimental/phase3_lexical_retrieval/REPORT.md`.

### The Observed Defect
On the `comment2context` task track ($N=80$ samples), classical BM25 outperforms RepoNeedle:
- **MRR**: Official BM25 `0.1974` vs RepoNeedle `0.1708` (**-13.5% deficit for RepoNeedle**)
- **Recall@5**: Official BM25 `0.2146` vs RepoNeedle `0.1646` (**-23.3% deficit**)
- **Recall@20**: Official BM25 `0.5292` vs RepoNeedle `0.2083` (**-60.6% deficit**)
- **BCY@8k**: Official BM25 `0.2604` vs RepoNeedle `0.1896` (**-27.2% deficit**)

### Root Cause
*(Corrected 2026-11-10. Earlier text described these queries as conversational prose, quoted fusion weights the code does not use, and recommended a BM25 weight of at least 0.85; none of that matched the code or the evidence.)*

1. **Query form**: ARB v2 `comment2context` queries are **structured JSON PR-review contexts** (`review_comment`, `diff_hunk_context`, `path`, `given_file`, `pr_title`, `line`), not conversational natural-language questions. ARB v2 has no conversational query track, so conversational retrieval is not measured by these results.
2. **Fusion weights (verified in `reponeedle/core/router.py`)**: for `comment2context` the router uses lexical 0.40, semantic 0.40, structural 0.20, workflow boost 0.0. The structural term multiplies a PageRank score that is all zeros unless `enable_pagerank_fusion=True` (default `False`), so in the default configuration and in the audited benchmarks the graph contributes nothing.
3. **Measurement effects**: much of the official-harness gap is an artifact of how the harness feeds RepoNeedle file fragments and scores unpacked files in corpus order (Phase 0 / Phase 1 reports). On matched whole-file input, `comment2context` MRR is level with BM25, but a real deep-recall deficit remains (Recall@20 −0.0896, repository-clustered 95% CI [−0.1779, −0.0056]).
4. **Lexical findings (research, not a production fix)**: development-only forensics (Phase 3) identified **query-term-frequency handling** as the strongest candidate cause of the lexical gap: RepoNeedle's BM25 index counts query terms but does not use the counts. Accounting for raw query term frequency improved `comment2context` lexical Recall@20 on development data but caused a `trace2code` regression. The best combination of the remaining candidate changes did not meet the pre-registered development criterion. **No lexical optimisation was validated, and production lexical behaviour is unchanged.**
5. **No supported mitigation yet**: raising the BM25 weight is **not** recommended. Lexical-only ranking performed worse than the current fusion on both fragment and whole-file input (Phase 0, Phase 3). The opt-in documentation filter was also not validated (Phase 2).

---

## 5. Monolithic File Saturation and Context Truncation

### The Observed Defect
In repositories containing large monolithic source files (>2,000 lines of code, e.g. `etcdserver/server.go` or `models/modeling_bert.py`):
1. **Budget Exhaustion**: If a monolithic file is packed in full (`Tier: FULL`), it can consume 3,000 to 6,000 tokens, exhausting an entire 4k or 8k budget on a single file and crowding out supporting secondary files.
2. **Skeleton Truncation Risk**: In `Tier: SKELETON` mode, RepoNeedle preserves class and function signatures while eliding implementation bodies. While this preserves architectural context, if the task requires fine-grained reasoning about an inner private helper or nested closure, the relevant code logic is omitted.
3. **Absence of Span Slicing**: RepoNeedle currently operates at the file and structural skeleton level. It does not perform fine-grained AST block slicing (e.g. extracting only lines 450–520 of a 3,000-line file).

---

## 5a. Indexing Exclusions: File-Size Limit, Unreadable Files and `max_files`

### Behavior
`RepoNeedleEngine.from_directory` does not index every file in a repository:
1. **File-size limit**: files **strictly larger** than `max_file_size_bytes` (default `500_000` bytes) are excluded. A file exactly at the limit is indexed. The limit is configurable (`from_directory(..., max_file_size_bytes=...)`, CLI/MCP `--max-file-size-bytes`) and must be a positive integer. It is never raised automatically.
2. **Unreadable files**: files whose size or contents cannot be read are excluded (including broken links and link loops).
2b. **Links resolving outside the repository** (development branch): files whose canonical location (following symlinks, and junctions on Windows) is outside the repository root are excluded without reading the target and recorded by link path (`symlink_outside_repository_paths`). In released 1.1.0 such files were read and indexed.
3. **`max_files` cap**: indexing stops after `max_files` (default `3000`) files.
4. **Ignore rules and extensions**: `.gitignore` entries, built-in ignore patterns (`node_modules`, `dist`, `build`, …) and unsupported extensions are excluded by design and are **not** reported as skipped.

### Visibility (development branch, planned 1.2.0)
Exclusions in categories 1–3 are recorded in `engine.indexing_diagnostics` (`skipped_paths`, `unreadable_paths`, `max_files_reached`, plus counts), exposed in CLI `--json` output under `indexing`, and returned by the MCP `reponeedle_inspect` tool. A summary `WARNING` is emitted on the `reponeedle.engine` logger (stderr by default; never on JSON stdout). Diagnostics and log records contain repository-relative paths and counts only, never file contents.

### Remaining Limitations
- Excluded files are invisible to retrieval: a relevant symbol defined only in an oversized generated or vendored file cannot be found.
- `skipped_paths` is unbounded. A repository with thousands of oversized supported-extension files (e.g. large JSON fixtures) produces a correspondingly long list in JSON/MCP output.
- Which files are dropped by the `max_files` cap depends on filesystem walk order, which is not guaranteed to be stable across platforms.
- The MCP server indexes once at startup; diagnostics reflect that snapshot until the server is restarted.

---

## 6. Local Compute Boundaries & Neural Baseline Scope

### Execution Boundaries
1. **CPU Native Execution**: The evaluation and benchmarks were executed strictly in a standard CPU environment (Python 3.12 AMD64 on Windows 11).
2. **Lack of Local GPU Neural Inference**: Heavy neural embedding models (such as `Qwen/Qwen3-Embedding-4B` and `8B`, `pplx-embed-v1-4b`) were evaluated by reference to official published ARB literature. They were not executed locally due to the absence of CUDA hardware and deep learning frameworks (`torch`, `transformers`) in the sandboxed execution environment.
3. **Scope Bounding**: RepoNeedle is designed as an ultra-fast, zero-dependency CPU retrieval system. It should not be mischaracterized as a competitor to fine-tuned 8-billion-parameter dense neural models running on H100 clusters.

---

## 7. Benchmark Repository Concentration

### Distribution Imbalance
While the evaluation spans 25 open-source repositories, query distribution in ARB v2 is naturally clustered:
- `gin-gonic/gin`: 88 queries (25.5% of positive samples)
- `tokio-rs/tokio`: 42 queries (12.2% of positive samples)
- `etcd-io/etcd`: 36 queries (10.4% of positive samples)

### Validation Safeguard
To ensure that headline gains over BM25 (+50.5%) were not simply driven by large gains on Gin, **repository-clustered bootstrap resampling** was conducted across all 25 repositories (10,000 resamples). The repository-clustered 95% Confidence Interval for $\Delta_{\text{MRR}}$ remained strictly positive (`[+0.0202, +0.1129]`), confirming statistical significance across clusters. However, broader evaluation across diverse languages (e.g. Java, C++, Ruby, PHP) remains an open objective.

---

## 8. Summary Table of Architectural Limitations

| Limitation | Impact | Severity | Planned Mitigation |
| :--- | :--- | :---: | :--- |
| **Heuristic Abstention Failure** | 0.0% accuracy on no-gold tasks; always on in 1.1.0, disabled by default on the development branch (planned 1.2.0), where out-of-scope queries are therefore not detected | **HIGH** | Fine-tuned neural cross-encoder discriminator |
| **Indexing Exclusions** | Files > 500 KB (configurable via `max_file_size_bytes` on the development branch), unreadable files, or beyond `max_files` are not searchable. Silent in 1.1.0; reported in diagnostics on the development branch | **MEDIUM** | Configurable limit; future span-level indexing of large files |
| **Deep Tail Recall Deficit** | Recall@20 lags RepoMap by -32.1% | **MEDIUM** | Multi-hop graph diffusion for tail ranks |
| **`comment2context` Deficit** | MRR lags pure BM25 by -13.5% | **MEDIUM** | Dynamic BM25 up-weighting on colloquial inputs |
| **Monolithic File Saturation** | 2k+ line files crowd budget | **MEDIUM** | AST block/span-level context slicing |
| **CPU Only / No Neural Weights** | Cannot perform deep semantic reasoning | **LOW (Design Choice)** | Optional pluggable neural embedding backend |
| **Benchmark Cluster Imbalance** | Top 3 repos represent 48% of queries | **LOW** | Expanded evaluation on Multi-Repo Benchmarks |

---

## 9. Capabilities Not Implemented

These are frequently assumed but are **not** part of RepoNeedle (neither 1.1.0 nor the current development branch):

| Capability | Status |
| :--- | :--- |
| Persistent / on-disk index cache | Not implemented; the index is rebuilt in memory on every process start. |
| Automatic live filesystem updates | Not implemented; restart the CLI process or MCP server to pick up changes. |
| HTTP / SSE MCP transport | Not implemented; the MCP server supports STDIO only. |
| AST block slicing of large files | Not implemented (see Section 5). |
| Calibrated confidence / reliable abstention | Not implemented; `confidence_score` is an uncalibrated diagnostic heuristic (see Section 2). |
| Live validation in Claude Code / Cursor | Not performed; MCP is verified with the MCP Python SDK and a JSON-RPC STDIO handshake only. |

## 10. Benchmark Reproducibility & Research Integrity Notes

Several historical artifacts cannot be reproduced exactly or contain non-measured values. They are documented, not silently corrected, in [docs/BENCHMARK_CONFIGURATION.md](docs/BENCHMARK_CONFIGURATION.md#research-integrity-notes). In summary:
- `benchmarks/results/benchmark_results.json` (synthetic, v0.1.0) is not reproduced by 1.1.0 or later code.
- Stage 3.6 per-query RepoMap BCY@4k/BCY@16k values and latencies were derived or hard-coded, not measured. This does **not** affect the headline ARB v2 results in the README, which use the official `pack_files` measurement for every system.
- The Stage 3.6 abstention evaluation simulated positive-query confidence scores instead of measuring them.

