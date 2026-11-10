# Milestone 2B: Documentation-Filter Validation on Held-Out Repositories

> [!IMPORTANT]
> **EXPERIMENTAL. Not an official ARB score, and not a default change.** This evaluates the **existing**, opt-in documentation filter (`AblationConfig.enable_doc_filter`, `doc_filter_penalty`) with a pre-registered, repository-level development/test design. The filter stays **disabled by default**. Official ARB v2 results, the Phase 0 audit and the Phase 1 evaluation are unchanged.

**Experiment script**: `benchmarks/run_doc_filter_validation.py` · **Framework**: Phase 1 product-aligned evaluation (file unit, whole-file input, full ranking; packed context reported separately) · **Engine**: development branch (ranking identical to released 1.1.0) · **Production code changed**: none

---

## 1. The filter under test (established from the code before any experiment)

| Question | Answer |
| :--- | :--- |
| What counts as documentation? | Path only (case-insensitive): contains `/doc/`, `/docs/`, `doc/`, `docs/`, `documentation/`, `guide/`, `tutorial/` or `.github/`, or ends in `.md`, `.rst`, `.txt`, `.adoc`, `.html`. No content or repository metadata is used. |
| Removal or penalty? | **Multiplicative penalty**: the fused score of each documentation file is multiplied by `doc_filter_penalty` (default 0.5). Files are never removed. |
| Stage | After score fusion (and optional graph diffusion), before sorting. It changes the **full ranking** and therefore the input to CUD-Pack. It does not affect candidate generation. |
| Scope | The default `legacy` ranker, identically for every task type. (`arm101` and `cascade` have separate, independent penalties not exercised here.) |
| Can documentation still be returned? | Yes. It stays in the ranking and can still be packed. |
| Can gold documentation be harmed? | Yes, by demotion (never removal). Measured in §6. |
| Configurable? | Yes: `doc_filter_penalty` float. No range validation exists; values in [0, 1] are meaningful (1 = no-op, 0 = documentation scored 0). |
| Known limitation | The predicate is broader than documentation: it also matches e.g. `requirements.txt`, `CMakeLists.txt`, `.github/` workflow files and any path containing `doc/` (e.g. `pydoc/`). Evaluated as-is, without modification. |

Treatment arms pass `AblationConfig(enable_doc_filter=True, doc_filter_penalty=p)` and the control passes `AblationConfig()` per call to `retrieve()`, so the two arms share the same engine instance, input, candidate universe and code path. Packing mode is identical in both (`complete` at 8,000 tokens). Fidelity: the control arm reproduces the Phase 1 whole-file results exactly (full-ranking metrics and packed coverage, 166 / 166 development queries).

## 2. Pre-registration (frozen before any filter result was computed)

| Artifact | Value |
| :--- | :--- |
| `protocol.json` | Primary metric, guardrails, correction, grid, selection rule and decision rule (see below) |
| `split.json` | Repository → dev/test assignment, derived from repository ids and task coverage only |
| Split SHA-256 | `6b8b0322ef70d5ffbd072c8a10d7b0154bc166dc3650df85c1cb30a154ba5bb4` (canonical JSON) |
| Split seed / algorithm | `reponeedle-2B-split-v1`; shuffle with `random.Random(f"{seed}:{attempt}")`, test = first 10 of 25, accept the first attempt where every task's test repository count is within ±1 of round(0.4 n) and both splits cover every task. Accepted at attempt 0. |
| `selected_filter_config.json` SHA-256 | `30343e918194787a100251a3407d4d6d2dd69f51c4cbe9d7be7b8d987e9fa814` (frozen after dev, before test) |

**Primary success criterion**: comment2context Recall@20, filter ON − OFF on the **test** repositories; the paired, repository-clustered 95% percentile CI must lie entirely above zero.

**Guardrails** (7 hypotheses, one-sided regression tests, bootstrap p = (1 + #{resampled mean ≥ 0}) / (B + 1), Holm-Bonferroni at family-wise α = 0.05): comment2context MRR; MRR and Recall@20 for code2test, trace2code and edit2ripple. Recall@5 and Recall@10 are reported for every task with uncorrected CIs (descriptive).

**Decision rule**: VALIDATED = primary CI lower bound > 0 and no Holm-supported regression. NOT VALIDATED = any Holm-supported regression, or primary point estimate ≤ 0. INCONCLUSIVE = no supported regression and positive primary point estimate, but primary CI includes 0 (or fewer than 5 test repositories with comment2context queries).

**Bootstrap**: resample repositories with replacement, 10,000 resamples, seed 20261109.

### 2.1 Split

| Task | Repositories dev / test | Queries dev / test |
| :--- | :---: | :---: |
| comment2context (primary) | 11 / 7 | 46 / 34 |
| code2test | 8 / 4 | 72 / 34 |
| trace2code | 3 / 4 | 14 / 87 |
| edit2ripple | 7 / 3 | 34 / 24 |
| **Total** | **15 / 10** | **166 / 179** |

Test repositories: `astral-sh/ruff`, `etcd-io/etcd`, `gin-gonic/gin`, `microsoft/playwright`, `mockito/mockito`, `numpy/numpy`, `pallets/click`, `pytest-dev/pytest`, `scrapy/scrapy`, `tox-dev/tox`.

As pre-registered, stratification balanced **repository** coverage per task, not query counts. One consequence: only 14 trace2code queries (3 repositories) are in development, so the development trace2code signal is weak. The split was not changed after it was generated.

## 3. Development results (exploratory; used only to select the penalty)

Grid {0.5, 0.25, 0.0}, all on development repositories only (166 queries, 15 repositories). Differences are filter ON − OFF.

| Task (queries / repos) | MRR Δ (p = 0.5) | Recall@20 Δ (p = 0.5) | Docs in top 10, OFF → ON |
| :--- | :---: | :---: | :---: |
| comment2context (46 / 11) | +0.0094 | +0.0580 | 1.85 → 0.00 |
| code2test (72 / 8) | +0.0364 | +0.0000 | 0.94 → 0.06 |
| trace2code (14 / 3) | +0.0141 | +0.0357 | 1.71 → 0.00 |
| edit2ripple (34 / 7) | +0.0026 | +0.0294 | 0.47 → 0.00 |
| Overall (166 / 15) | +0.0201 | +0.0251 | 1.16 → 0.02 |

Penalties 0.25 and 0.0 produced the same comment2context Recall@20 gain (+0.0580) and near-identical results otherwise: at 0.5, documentation already leaves the top 10. All three met the development guardrail (no mean loss beyond −0.02). By the pre-registered tie rule (larger, milder penalty), **0.5 was selected and frozen**. This equals the existing default value of `doc_filter_penalty`, so no parameter was tuned away from its default. Full development contrasts with CIs: `dev_results.json`.

## 4. Held-out confirmatory test (run once, frozen penalty 0.5)

Before running, the script verified the split hash and the frozen configuration hash. 179 / 179 test queries (10 repositories), 0 duplicates, every row from a test repository. The control arm reproduces Phase 1 whole-file results exactly (179 / 179).

### 4.1 Primary criterion

| comment2context Recall@20 (34 queries, 7 repositories) | OFF | ON | Δ | W / T / L | 95% CI |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Test | 0.6373 | 0.6373 | **0.0000** | 0 / 34 / 0 | [0.0000, 0.0000] |

**The primary criterion is not met.** The filter did not change whether any comment2context gold file appears in the top 20 of any held-out query.

### 4.2 Guardrails (Holm-adjusted, one-sided regression tests)

| Hypothesis | Δ (ON − OFF) | 95% CI | p (one-sided) | p (Holm) | Regression supported |
| :--- | :---: | :---: | :---: | :---: | :---: |
| comment2context MRR | +0.0299 | [+0.0068, +0.0765] | 1.000 | 1.000 | no |
| code2test MRR | +0.0004 | [+0.0000, +0.0009] | 1.000 | 1.000 | no |
| code2test Recall@20 | 0.0000 | [0.0000, 0.0000] | 1.000 | 1.000 | no |
| trace2code MRR | +0.0778 | [+0.0099, +0.0875] | 1.000 | 1.000 | no |
| trace2code Recall@20 | +0.0211 | [0.0000, +0.0322] | 1.000 | 1.000 | no |
| edit2ripple MRR | +0.0008 | [0.0000, +0.0033] | 1.000 | 1.000 | no |
| edit2ripple Recall@20 | 0.0000 | [0.0000, 0.0000] | 1.000 | 1.000 | no |

No guardrail shows a regression; no test query got worse on any full-ranking metric.

### 4.3 All tasks and metrics (test; uncorrected 95% CIs, descriptive except where stated above)

| Task (queries / repos) | MRR Δ | Recall@5 Δ | Recall@10 Δ | Recall@20 Δ |
| :--- | :---: | :---: | :---: | :---: |
| comment2context (34 / 7) | +0.0299 [+0.0068, +0.0765] | +0.0147 [0.0000, +0.0682] | +0.0539 [+0.0090, +0.1842] | 0.0000 [0.0000, 0.0000] |
| code2test (34 / 4) | +0.0004 [0.0000, +0.0009] | 0.0000 | +0.0147 [0.0000, +0.1250] | 0.0000 |
| trace2code (87 / 4) | +0.0778 [+0.0099, +0.0875] | +0.0843 [0.0000, +0.1023] | +0.0594 [+0.0111, +0.2000] | +0.0211 [0.0000, +0.0322] |
| edit2ripple (24 / 3) | +0.0008 [0.0000, +0.0033] | 0.0000 | 0.0000 | 0.0000 |
| **Overall (179 / 10)** | **+0.0437 [+0.0098, +0.0623]** | +0.0438 [0.0000, +0.0640] | +0.0419 [+0.0167, +0.1026] | +0.0102 [0.0000, +0.0182] |

Absolute test values (OFF → ON): comment2context MRR 0.2465 → 0.2764; trace2code MRR 0.2873 → 0.3651; overall MRR 0.2832 → 0.3269. Per-query reciprocal ranks and gold positions: `test/` shard files.

### 4.4 Documentation in rankings, packed context, latency (test)

| Task | Docs in top 5 / 10 / 20, OFF → ON | Packed gold coverage, OFF → ON | Queries with ≥1 gold packed, OFF → ON | Utilisation |
| :--- | :---: | :---: | :---: | :---: |
| comment2context | 0.74 / 1.74 / 3.56 → 0.03 / 0.03 / 0.18 | 45.6% → 51.0% | 67.6% → 76.5% | 99.3% |
| code2test | 0.12 / 0.18 / 0.38 → 0 / 0 / 0 | 62.9% → 62.9% | 67.6% → 67.6% | 99.4% |
| trace2code | 1.34 / 2.30 / 3.92 → 0.01 / 0.21 / 0.54 | 73.6% → 81.4% | 77.0% → 83.9% | 99.7% |
| edit2ripple | 0.12 / 0.33 / 0.83 → 0 / 0 / 0 | 79.5% → 79.5% | 91.7% → 91.7% | 99.6% |
| Overall | 0.83 / 1.53 / 2.77 → 0.01 / 0.11 / 0.30 | 67.0% → 71.9% | 75.4% → 80.4% | 99.5% |

**Latency is not a valid comparison in this design.** Both arms run on the same engine instance in a fixed order (OFF first), so the ON arm benefits from caches warmed by the OFF call (mean 546 ms vs 93 ms). The arms were not counterbalanced. The filter itself is a single pass over file paths and should be negligible, but that was not measured here.

## 5. Decision

### **B. NOT VALIDATED**

The pre-registered primary criterion (a supported positive change in comment2context Recall@20 on held-out repositories) failed: the observed change was exactly zero. No guardrail regression was found.

Secondary observations, **not** usable as validation because they were not the pre-registered primary endpoint (exploratory for future work):
- The filter improved comment2context MRR (+0.030, CI excludes zero) and overall MRR (+0.044, CI excludes zero) on held-out repositories, with **zero** per-query losses on any full-ranking metric across 179 queries.
- The effect is a reordering **within** the top ranks: documentation leaves the top 10 (1.53 → 0.11 per query), lifting gold files that were already near the top, without moving gold files across the rank-20 boundary.

## 6. Gold documentation and false negatives

| Split | Gold files | Gold documentation files | Gold docs pushed out of top 20 | Gold docs dropped from packed context | Non-doc gold dropped from packed context | Non-doc gold entering top 20 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Development (p = 0.5) | 252 | **4** | **1** | **1** | 0 | 7 |
| Test (p = 0.5) | 262 | **0** | 0 | 0 | **1** | 3 |

- **The filter does harm relevant documentation.** One of the 4 development gold documentation files left both the top 20 and the packed context. The test split contained no gold documentation, so the held-out test **cannot** measure this risk. The "no comment2context gold is documentation" observation from Phase 0 does not generalise to all tasks.
- **Test false negative** (`false_negative_examples.json`): trace2code, `gin-gonic/gin`, gold `context.go` moved from rank 11 to rank 10 under the filter but was no longer packed. Promoting other non-documentation files changed CUD-Pack's representation choices. This is a packing interaction, not a ranking loss.

## 7. Limitations

- **Small held-out sample**: 7 comment2context repositories (34 queries) and 3–4 repositories for the other tasks. Clustered percentile CIs with this few clusters are approximate, and degenerate to [0, 0] when every query ties.
- **Query imbalance from repository-level stratification**: trace2code has 14 development vs 87 test queries.
- **The test split contains no gold documentation**, so harm to relevant documentation is measured only on development data (4 files).
- **The documentation predicate is broader than documentation** (`.txt`, `.github/`, any path containing `doc/`).
- **Latency** is confounded by arm order (§4.4).
- A single benchmark (ARB v2) of structured, non-conversational queries; task labels passed explicitly.
- The held-out set has now been used once. Any follow-up confirmatory study (for example with MRR as a pre-registered primary endpoint) needs **new** held-out data, not these repositories.

## 8. Production changes

None. No file under `reponeedle/` was modified (verified by SHA-256 against the pre-milestone fingerprint). The filter remains opt-in and disabled by default.

## 9. Artifacts

`protocol.json` (+ `.sha256`), `split.json` (+ `split.sha256`), `selected_filter_config.json` (+ `.sha256`), `dev/` and `test/` per-query results (metrics, reciprocal ranks, gold positions, top-20 rankings, packed stats, latencies), `dev_results.json`, `test_results.json` (contrasts, CIs, Holm results, decision), `false_negative_examples.json`, `run_metadata.json`.
