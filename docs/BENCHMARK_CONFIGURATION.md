# Benchmark Configuration & Reproducibility

This document records **how each benchmark and research script configures RepoNeedle**, which historical results were measured under which defaults, and known reproducibility gaps. It exists because 1.2.0 (upcoming; PyPI publication pending) changed a default that some evaluations depend on.

*Last audited: 2026-11-09. Machine-checked by `tests/test_documentation_consistency.py`.*

---

## 1. The Default That Changed

| Version | Selective abstention heuristic |
| :--- | :--- |
| ≤ 1.1.0 (released) | **Always on.** Every `retrieve()` call could abstain (return no files) on heuristic grounds. |
| 1.2.0 | **Off by default.** Enabled only via `BudgetConfig(enable_experimental_abstention=True)`, `retrieve(..., enable_experimental_abstention=True)`, the CLI flag `--enable-experimental-abstention`, or the MCP argument of the same name. |

The heuristic itself (formula, threshold semantics, default threshold `0.12`) is unchanged. Empty repositories always return `abstained=True` regardless of the flag, because there are no candidates.

**To reproduce 1.1.0 behaviour exactly** in any script, construct the engine with `budget_config=BudgetConfig(enable_experimental_abstention=True)`.

## 2. Policy

1. **Scripts that measure the heuristic** (selective/no-gold accuracy, false abstentions on positive queries, or abstainer ablations) **enable it explicitly**, with the original threshold, data and methodology.
2. **Scripts that measure ordinary retrieval** (ranking quality, packing, latency, memory) **use the new default** (disabled), unless they also record per-query abstention decisions.
3. Historical result files are **never regenerated or edited** to match new code. Gaps are documented in Section 6.

## 3. Scripts That Enable the Experimental Heuristic

<!-- abstention-opt-in-scripts:start -->
| Script | What it measures | How abstention is enabled |
| :--- | :--- | :--- |
| `benchmarks/runner.py` | Synthetic RepoNeedle-Bench, including `SelectiveAccuracy` on 3 no-gold samples | Per call, **selective samples only** (`enable_experimental_abstention=is_selective`) |
| `benchmarks/run_ablations.py` | Synthetic ablation study, including the "No Abstainer" factor | Engine-wide (`BudgetConfig`), all samples |
| `benchmarks/run_arb_comprehensive_validation.py` | ARB v0.1 validation; records `abstained`/`confidence` per positive sample plus the N=82 selective pilot | Engine-wide (`BudgetConfig`), all samples |
| `benchmarks/run_complete_arb_evaluation.py` | Headline ARB v2 evaluation (README Parts A–B) | **Phase 2 (selective, N=82) only**; Phase 1 (positive, N=345) uses the default |
| `research/stage3_6/scripts/evaluate_abstention.py` | Stage 3.6 abstention diagnostic (Candidate F configuration) | Engine-wide (`BudgetConfig`) |
| `research/stage3_6/scripts/test_abstention.py` | Abstention decisions on positive and no-gold ARB samples | Engine-wide (`BudgetConfig`) |
| `scripts/verify_abstention_reproducibility.py` | Read-only check that historical ARB v2 abstention and positive results still reproduce | Per call; runs each query **both** with and without the opt-in and compares |
<!-- abstention-opt-in-scripts:end -->

## 4. Scripts That Read Abstention Results but Intentionally Use the Default

<!-- abstention-default-exempt:start -->
| Script | Reason |
| :--- | :--- |
| `research/stage3_20/run_parity_tests.py` | Only checks the structural empty-repository result (`abstained=True` with zero files), which is independent of the flag |
| `benchmarks/run_arb_current_engine.py` | Ordinary positive-retrieval measurement of the current engine; records `abstained` only to confirm it stays `False` under the default |
<!-- abstention-default-exempt:end -->

## 5. Other Scripts (Ordinary Retrieval, Latency, Memory)

These call `RepoNeedleEngine.retrieve()` / `query()` for ranking, packing or timing and **use the default** (disabled):

| Category | Scripts |
| :--- | :--- |
| Supplemental diagnostics (experimental, not official) | `benchmarks/run_arb_evaluator_audit.py` (Phase 0 forensic audit), `benchmarks/run_arb_product_aligned_eval.py` (Phase 1 product-aligned evaluation; see Section 9), `benchmarks/run_doc_filter_validation.py` (Phase 2 documentation-filter held-out validation), `benchmarks/run_lexical_forensics.py` (Phase 3 lexical forensics, development data only) |
| Ranking / packing quality | `benchmarks/run_arb_official_eval.py`, `research/contextbench_evaluation/adapter.py`, `research/run_stage2_failure_diagnostics.py`, `research/stage3/benchmark_neural_track.py`, `research/stage3/evaluate_architectural_tradeoffs.py`, `research/stage3/run_contextbench_evaluation.py`, `research/stage3/run_swe_bench_evaluation.py`, `research/stage3_2/evaluate_candidates.py`, `research/stage3_3/run_stage3_3_eval.py`, `research/stage3_5/evaluate_graph_retrieval.py`, `research/stage3_20/run_production_arb_reproduction.py` |
| Latency / memory | `research/measure_runtime_costs.py`, `research/stage3/audit_runtime_and_memory.py`, `research/stage3_5/audit_memory_reduction.py`, `research/stage3_6/audit_runtime_and_memory.py` (and its identical copy under `scripts/`), `research/stage3_9/audit_runtime_and_memory.py`, `research/stage3_12/run_stage3_12_benchmarks.py`, `research/stage3_13/run_stage3_13_audit.py`, `research/stage3_20/benchmark_resources.py`, `research/stage3_21/benchmark_isolated_memory.py`, `scripts/verify_multi_scale_token_and_latency.py`, `scripts/verify_token_savings_and_latency.py` |

Notes:
- Scripts that read only `ranked_files` (e.g. `run_production_arb_reproduction.py`) are unaffected by abstention in every version: `ranked_files` was populated even when the heuristic abstained.
- In ≤ 1.1.0, an abstained query skipped context packing, so it returned slightly faster. Latency scripts may therefore measure marginally higher times under the new default *if* the heuristic used to fire on their queries. On the ARB v2 positive split it fired on **0 of 345** queries (Section 7.1).
- Scripts that evaluate abstention policies **without** the engine's opt-in path, by computing their own features or thresholds from the engine's indices, are unaffected: `research/run_stage2_abstention_evaluation.py` and `research/stage3_11/run_stage3_11_evaluation.py` (which applies its own `top_score < 3.0` rule).
- All remaining scripts that construct a `RepoNeedleEngine` use its indices or rankers directly and never call `retrieve()`, so the default does not affect them.

## 6. Historical Results and the Defaults They Were Measured Under

| Result | Producer | Measured with abstention | Reproducible on the development branch? |
| :--- | :--- | :--- | :--- |
| README Part A (ARB v2 positive, N=345) | `benchmarks/run_complete_arb_evaluation.py` → `reports/full_arb_validation/`, run on 2026-10-28 with the engine at commit `8e00425` (tag `v0.1.0-baseline`) | Always on | **Only with that engine** (verified exactly). Engine changes before the 1.1.0 release changed the rankings, so these numbers do **not** describe 1.1.0 or later. The current engine is re-measured in `reports/arb_v2_current_engine/` (Section 7.3). |
| README Part B (ARB v2 selective, 0/82) | same, Phase 2 | Always on | **Yes**: 0/82 abstained with explicit opt-in on 1.1.0 and on the development branch (confidence values differ slightly from the 2026-10-28 engine, max 0.031, but no decision changes). |
| `benchmarks/results/benchmark_results.json` (synthetic, v0.1.0) | `scripts/run_benchmarks.py` → `benchmarks/runner.py` | Always on | **No.** Stale since v0.1.0: neither 1.1.0 nor the development branch reproduces it (MRR 0.917 stored vs 0.861 re-run; selective 3/3 stored vs 2/3 re-run). 1.1.0 and the development branch produce *identical* values to each other. |
| `benchmarks/results/ablation_study_results.json`, `arb_comprehensive_validation.json` | `run_ablations.py`, `run_arb_comprehensive_validation.py` | Always on | Harnesses opt in explicitly, so the abstention condition is preserved; not re-run in this audit. |
| Stage 3.x research results (`research/stage3_*`) | scripts listed in Section 5 | Always on | Ordinary-retrieval results are unaffected wherever the heuristic did not fire; not individually re-run in this audit. |

## 7. Verification Performed (2026-11-09)

All runs used the local ARB v2 checkout (`external/agent-retrieval-bench`), the same data and document construction as `run_complete_arb_evaluation.py`, and were read-only with respect to `reports/full_arb_validation/`.

### 7.1 The abstention default change does not alter any ARB v2 result

`python scripts/verify_abstention_reproducibility.py --positives` on the development branch (elapsed 4,299 s):

| Check | Result |
| :--- | :--- |
| Selective (N=82): abstain decision with explicit opt-in equals the historical decision | **82 / 82** (0/82 abstained, as published) |
| Selective (N=82): abstentions under the new default | **0 / 82** |
| Positive (N=345): heuristic would abstain when opted in | **0 / 345** |
| Positive (N=345): selected files identical with and without opt-in | **345 / 345** |

Conclusion: making the heuristic opt-in changes no positive-query result and no selective decision on ARB v2.

### 7.2 Historical results describe the 2026-10-28 engine, not 1.1.0

The same script reported that current confidence values (2/82) and top-20 lists (5/345) mostly do **not** equal the historical records. To attribute this, the same inputs were run against three code versions (all 82 selective queries plus the 53 positive queries of the first 25 snapshots):

| Engine | Selective confidence equal to history | Positive top-20 equal to history |
| :--- | :---: | :---: |
| Commit `8e00425` (tag `v0.1.0-baseline`, 2026-10-28; produced the historical reports) | **82 / 82** (bit-identical) | **53 / 53** |
| Released 1.1.0 (`HEAD` of `main`) | 2 / 82 (max diff 0.031) | 1 / 53 |
| Pre-release 1.2.0 development branch (2026-11-09) | identical to 1.1.0 (max diff 0.0) | identical to 1.1.0 (53 / 53) |

Conclusions:
- The evaluation pipeline and data are sound: the producing engine reproduces the published records exactly on every query checked.
- Engine changes made between 2026-10-28 and the 1.1.0 release changed RepoNeedle's rankings. **README Part A and the ARB-derived claims in `CLAIMS_AND_EVIDENCE.md` describe the 2026-10-28 engine.**
- Milestones 1A–1C (CLI JSON, anchors, MCP, abstention opt-in, indexing diagnostics) changed no ranking result: the development branch is bit-identical to 1.1.0 on every query compared.
- Changes merged into 1.2.0 after these measurements were not re-measured. They do not touch the ranking path used here: all benchmark scripts build the engine with `from_documents`, while the outside-repository link check applies only to `from_directory`; the CLI anchor path handling is CLI-only; and the `change_impact` change affects the reported task label only (ranking equality is covered by `tests/test_release_compat.py`).

### 7.3 Current-engine re-measurement (ARB v2 positive, N=345)

`benchmarks/run_arb_current_engine.py` re-measures RepoNeedle only, replicating the harness's RepoNeedle path. It was validated by running it against the `v0.1.0-baseline` engine on the first 12 snapshots: all 8 metrics and the top-20 list reproduced exactly for 20 / 20 samples. Official BM25 / Lexical / RepoMap baselines do not depend on RepoNeedle code, so their historical per-sample values are used for comparison. Results: `reports/arb_v2_current_engine/SUMMARY.json`.

Run on 2026-11-09 in 3 parallel shards (engine version 1.1.0 = development branch; 345 / 345 samples; 0 abstentions).

| System (N=345) | MRR | Recall@5 | Recall@10 | Recall@20 | BCY@4k | BCY@8k | BCY@16k | BCY@32k |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoNeedle, current engine (1.1.0 / dev branch)** | **0.2153** | **0.3032** | **0.3677** | **0.3842** | **0.2400** | **0.3443** | **0.3813** | **0.3842** |
| RepoNeedle, 2026-10-28 engine (README Part A) | 0.2287 | 0.3011 | 0.4110 | 0.4279 | 0.2436 | 0.3450 | 0.4192 | 0.4279 |
| Official BM25 | 0.1520 | 0.1899 | 0.3034 | 0.4452 | 0.1220 | 0.2051 | 0.3184 | 0.4365 |
| Official Lexical | 0.1574 | 0.2292 | 0.3548 | 0.4940 | 0.1488 | 0.2650 | 0.3886 | 0.4882 |
| Official RepoMap | 0.2140 | 0.3185 | 0.4786 | 0.6306 | 0.2024 | 0.3788 | 0.5235 | 0.6166 |

Paired MRR differences (current engine minus comparator; 5,000 bootstrap resamples; repository-clustered across 25 repositories):

| Comparison | Mean Δ MRR | Wins / Ties / Losses | Sample 95% CI | Repo-clustered 95% CI |
| :--- | :---: | :---: | :---: | :---: |
| vs BM25 | +0.0633 (+41.6%) | 132 / 17 / 196 | [+0.0312, +0.0948] | [+0.0111, +0.0980] |
| vs Lexical | +0.0579 (+36.8%) | 118 / 24 / 203 | [+0.0278, +0.0888] | [+0.0180, +0.0933] |
| vs RepoMap | +0.0013 (+0.6%) | 106 / 27 / 212 | [−0.0330, +0.0359] | [−0.0597, +0.0517] |
| vs 2026-10-28 RepoNeedle engine | −0.0134 | 85 / 175 / 85 | [−0.0205, −0.0065] | [−0.0204, −0.0061] |

MRR by task (current engine vs official baselines):

| Task | N | Current RepoNeedle | 2026-10-28 RepoNeedle | BM25 | Lexical | RepoMap |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `code2test` | 106 | 0.2546 | 0.2660 | 0.1057 | 0.0663 | 0.1942 |
| `comment2context` | 80 | 0.1658 | 0.1708 | 0.1974 | 0.1530 | 0.1532 |
| `trace2code` | 101 | 0.2262 | 0.2337 | 0.1638 | 0.2075 | 0.2723 |
| `edit2ripple` | 58 | 0.1929 | 0.2320 | 0.1536 | 0.2428 | 0.2323 |

Findings:
- The qualitative conclusions published in README Part A still hold for the current engine: significantly better MRR than BM25 and Lexical (repository-clustered CIs exclude zero), statistical parity with RepoMap on MRR, a large RepoMap advantage in deep recall (Recall@20: 0.6306 vs 0.3842), the strongest `code2test` MRR (+140.8% vs BM25, +31.0% vs RepoMap), and a `comment2context` deficit against BM25 (−16.0%, previously −13.5%). The BCY@4k advantage over RepoMap is +18.5% (previously +20.4%); no confidence interval was computed for BCY.
- The current engine is measurably weaker than the 2026-10-28 engine on MRR (−0.0134, CI excludes zero), mainly through lower Recall@10 / @20. Note that the harness ranks every file RepoNeedle did not pack in corpus order (it uses `selected_files`, not `ranked_files`), so deep-rank metrics also depend on how many files the packer selects at an 8,000-token budget. This is a hypothesis for follow-up, not a verified cause.
- Latency (mean 269.8 ms, p50 188.3 ms, p95 775.5 ms) was measured with three shards running concurrently and is **not comparable** to the single-process latency figures in README Part D.

## 8. Research Integrity Notes

Issues found during the audit. The affected files are **left unchanged** for the record; errata were added where the results are reported.

1. **Stage 3.6 synthesized RepoMap values.** `research/stage3_6/scripts/evaluate_systems.py` (and its identical copy one directory up) writes `PER_QUERY_RESULTS.csv`, in which `BASE-REPOMAP` `bcy_at_4k` = 0.5 × `bcy_at_8k` and `bcy_at_16k` = min(1, 1.5 × `bcy_at_8k`) (all 29 rows with non-zero BCY@8k) and `latency_ms` is the constant 180.20 (all 345 rows). The `abstained` column is hard-coded `False` for every system. A fallback branch would also fill missing RepoMap records with published aggregate values (it was not triggered: 0 rows match). RepoMap MRR/Recall come from official ARB records. **The README's headline numbers are not affected**: they come from `run_complete_arb_evaluation.py`, which measures BCY for every system with the official `pack_files`.
2. **Stage 3.6 simulated positive confidences.** `research/stage3_6/scripts/evaluate_abstention.py` does not run the 345 positive queries. It hard-codes `abstained = 0` and draws confidence values from a normal distribution fitted to ~35 sampled queries. The positive-row values in `ABSTENTION_RESULTS.csv` (mean confidence, Brier score) and the overall Brier/ECE are therefore simulated. The 82 no-gold rows were measured. An erratum was added to `research/stage3_6/REPRODUCIBILITY_REPORT.md`.
3. **Synthetic "100% selective abstention" claim.** The v0.1.0 announcement's 100% figure came from 3 synthetic samples in the stale `benchmark_results.json`. It has been corrected in `docs/ANNOUNCEMENT.md` and recorded as retracted claim C11 in `CLAIMS_AND_EVIDENCE.md`.
4. **Documented threshold and score ranges.** Earlier docs stated a default threshold of 0.38 and a confidence range of [0.64, 0.86]. The engine default has always been 0.12 (0.38 is the unused class default), and the measured range on the 82 no-gold queries is [0.532, 0.891]. Corrected in README, KNOWN_LIMITATIONS and CLAIMS_AND_EVIDENCE.
5. **Hard-coded absolute paths.** Six research scripts still hard-code `F:\RepoNeedle` and will not run unchanged on another machine: `research/stage3_6/scripts/generate_graph_csv.py`, `research/stage3_10/generate_canonical_results.py`, `research/stage3_11/run_stage3_11_audit.py`, `research/stage3_12/run_stage3_12_benchmarks.py`, `research/stage3_19/run_clean_reproduction.py`, `research/stage3_20/run_candidate_f_forensics.py`. The two abstention scripts edited in this audit now resolve the repository root relative to their own location.

## 9. Kinds of ARB v2 Results (Do Not Mix Them)

| Kind | What it is | Engine | Where | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Official ARB v2 result (historical, published)** | Official harness: RepoNeedle gets one fragment per file; packed files then corpus order are scored | Commit `8e00425` (tag `v0.1.0-baseline`, 2026-10-28) | README Part A; `reports/full_arb_validation/` | Official. Reproducible with that engine. Does not describe 1.1.0 |
| **Official harness, current engine** | The same harness and metric definitions, re-run | 1.1.0 = development branch | `reports/arb_v2_current_engine/`; this file §7.3 | Official-harness measurement of today's engine |
| **Phase 0 forensic audit** | Diagnostic decomposition (full ranking vs packing, document representation, documentation distractors) | 1.1.0 = development branch | `reports/experimental/phase0_evaluator_audit/` | Experimental diagnostic |
| **Phase 2 documentation-filter validation** | Pre-registered repository-level dev/test experiment on the existing opt-in `enable_doc_filter` (penalty 0.5) using the supplemental framework | 1.1.0 = development branch | `reports/experimental/phase2_documentation_filter/` | Experimental. Result: **NOT VALIDATED** on its primary endpoint (comment2context Recall@20 Δ = 0.000); no guardrail regression; filter remains off by default |
| **Phase 3 lexical retrieval forensics** | Pre-registered development-only ablations of RepoNeedle's lexical index (query term frequency, duplicate tokens, JSON keys, length normalisation, field weights) | 1.1.0 = development branch | `reports/experimental/phase3_lexical_retrieval/` | Experimental, development evidence only. Root cause identified (query term frequency ignored); no change met the dev-support criterion; **NOT VALIDATED**; no fresh confirmatory data available |
| **Supplemental product-aligned evaluation** | File-unit full-ranking metrics on fragment **and** whole-file input for RepoNeedle and BM25, matched comparisons, packed-context coverage reported separately, no remainder positions | 1.1.0 = development branch | `reports/experimental/phase1_product_aligned_evaluation/` (`benchmarks/run_arb_product_aligned_eval.py`) | **Supplemental. Not an official ARB score** |

Supplemental headline (345 queries, 25 repositories; paired, repository-clustered 95% CIs). On matched whole-file input, RepoNeedle's full ranking exceeds BM25 overall: MRR 0.2789 vs 0.1717 (+0.1073 [+0.0647, +0.1596]); Recall@20 0.7042 vs 0.5138 (+0.1904 [+0.1114, +0.2715]). By task, code2test is significantly better on every metric; edit2ripple is significantly better on Recall@10/20; trace2code is inconclusive (7 repositories); **comment2context is level on MRR but significantly worse on Recall@20 (−0.0896 [−0.1779, −0.0056])**. Full details, fidelity checks and limitations are in that directory's `REPORT.md`.
