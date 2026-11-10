# Supplemental Product-Aligned Evaluation (ARB v2 positives)

> [!IMPORTANT]
> **This is a supplemental, product-aligned evaluation. It is NOT an official ARB v2 score and does not replace one.** The official ARB v2 results (README Part A, measured on 2026-10-28 with the engine at commit `8e00425`), the official current-engine re-measurement (`reports/arb_v2_current_engine/`), the official harnesses, and the ARB metric definitions are all unchanged.

**Date**: 2026-11-09 · **Engine**: development branch (identical to released 1.1.0 for ranking) · **Evaluator**: `benchmarks/run_arb_product_aligned_eval.py` · **Configuration**: `config.json` (fixed before any result was computed) · **Run metadata**: `run_metadata.json`

---

## 1. Why this evaluation exists

The Phase 0 audit (`../phase0_evaluator_audit/PHASE0_REPORT.md`) found two properties of the official harness that make it measure something other than RepoNeedle's real retrieval behaviour:
1. **Input representation**: RepoNeedle receives one fragment per file (the single longest ARB chunk), while the official BM25 baseline ranks every chunk of every file. In real use, RepoNeedle reads whole files.
2. **Ranking measurement**: files RepoNeedle does not pack into the 8,000-token context are appended in corpus order and scored as if ranked.

This evaluation measures RepoNeedle's **full ranking** on **both** representations and compares it with BM25 given the **same** representation.

## 2. Evaluation architecture and protocol

| Item | Decision |
| :--- | :--- |
| Queries / gold | All 345 ARB v2 positive queries (`code2test` 106, `comment2context` 80, `trace2code` 101, `edit2ripple` 58); gold = ARB `target_gold_files` |
| Retrieval unit | **File**, for every system |
| Candidate universe | Every path with at least one chunk in the snapshot's ARB chunk file (same universe for all systems) |
| Fragment representation | Longest ARB chunk per path (what the official harness gives RepoNeedle) |
| Whole-file representation | The `file` chunk's header lines before the first symbol, then every `symbol` chunk in line order |
| RepoNeedle ranking | The complete ranking the engine hands to CUD-Pack (fused score, all files); task label passed as in the official harness |
| BM25 | ARB's own BM25 (k1 = 1.5, b = 0.75, ARB tokenizer). File-unit variants index one document per file. The chunk variant (the official baseline) maps chunk scores to files by **max**, which is ARB's own `unique_ranked_paths` rule |
| Ties | Score descending, then path ascending (asserted against both engines' native order) |
| Full-ranking metrics | MRR, Recall@5/10/20, per-query reciprocal rank, gold positions (ARB `reciprocal_rank` / `recall_at`, cross-checked by an independent implementation) |
| Packed context | CUD-Pack output at 8,000 tokens: gold coverage, queries with at least one gold file packed, utilisation, files packed |
| Remainder | Count of unselected files only. **No positions are assigned**; remainder order never enters a full-ranking metric |
| Official sequence | Packed files then corpus order, recorded **only** to check fidelity against the official current-engine run |
| Statistics | Paired per-query differences; repository-clustered percentile bootstrap (resample repositories with replacement), 10,000 resamples, seed 20261109, 95% CI. "Supported" means the CI excludes zero |

**Valid comparisons.** "RepoNeedle vs BM25" is like-for-like only within a representation (fragment vs fragment, whole file vs whole file). The comparison with the official chunk-level BM25 is reported for continuity, but its BM25 uses a different retrieval unit (chunks aggregated by max) and different input text, so it is **not** a matched comparison.

## 3. Fidelity and reproducibility

| Check | Result |
| :--- | :--- |
| Queries present / expected | **345 / 345**; 0 missing, 0 unexpected, 0 duplicate rows |
| Missing gold labels | 0 |
| Task and repository of every query match the dataset | 345 / 345 |
| Every ranked file belongs to the query's snapshot; no duplicate files in any ranking | asserted for every ranking of every query |
| Independent metric implementation agrees with ARB helpers | 345 / 345 |
| Hoisted BM25 equals ARB `rank_chunks_bm25_with_scores` | asserted on the first query of every snapshot, for all three BM25 variants |
| Official sequence equals the official current-engine run (`reports/arb_v2_current_engine/`) | **345 / 345** |
| BM25 (chunks) equals the historical official BM25 (`reports/full_arb_validation/`) | **345 / 345** |
| Independent reproduction of the Phase 0 audit | RepoNeedle fragment 345 / 345; RepoNeedle whole file, BM25 whole file and BM25 fragment 238 / 238 (every query Phase 0 completed) |
| Determinism (fresh re-run of the first 6 snapshots: ranking hashes of all 5 systems + all metrics) | **8 / 8 queries identical** (`determinism_check.json`) |
| Historical result files unchanged | verified by SHA-256 before and after (see §8) |

## 4. Results

Complete tables, including every comparison, metric and task: `TABLES.md` (generated from `aggregate.json` and `confidence_intervals.json`). Per-query metrics, reciprocal ranks and gold positions: `per_query/`. Top-100 rankings: `rankings/`.

### 4.1 Full-ranking metrics

| Group (queries / repositories) | RN fragment MRR / R@20 | **RN whole-file MRR / R@20** | BM25 fragment MRR / R@20 | **BM25 whole-file MRR / R@20** | BM25 chunks (official) MRR / R@20 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Overall** (345 / 25) | 0.2379 / 0.5803 | **0.2789 / 0.7042** | 0.1439 / 0.3604 | **0.1717 / 0.5138** | 0.1520 / 0.4452 |
| comment2context (80 / 18) | 0.1857 / 0.3146 | 0.2037 / 0.4896 | 0.1875 / 0.3563 | 0.2063 / 0.5792 | 0.1974 / 0.5292 |
| code2test (106 / 12) | 0.2736 / 0.6434 | 0.3556 / 0.7698 | 0.0656 / 0.2594 | 0.1160 / 0.3381 | 0.1057 / 0.3066 |
| trace2code (101 / 7) | 0.2577 / 0.6782 | 0.2885 / 0.8300 | 0.1432 / 0.3927 | 0.1476 / 0.6089 | 0.1638 / 0.4934 |
| edit2ripple (58 / 10) | 0.2104 / 0.6609 | 0.2259 / 0.6609 | 0.2283 / 0.4943 | 0.2676 / 0.5790 | 0.1536 / 0.4986 |

### 4.2 Matched comparisons (paired, repository-clustered 95% CI)

| Group | RN − BM25, **whole file**: Δ MRR | Δ Recall@20 | RN − BM25, fragment: Δ MRR | Δ Recall@20 | RN whole file − RN fragment: Δ MRR | Δ Recall@20 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Overall** | **+0.1073 [+0.0647, +0.1596]** | **+0.1904 [+0.1114, +0.2715]** | **+0.0940 [+0.0570, +0.1201]** | **+0.2199 [+0.1278, +0.2938]** | **+0.0410 [+0.0007, +0.1042]** | **+0.1239 [+0.0572, +0.2430]** |
| comment2context | −0.0026 [−0.0297, +0.0337] | **−0.0896 [−0.1779, −0.0056]** | −0.0018 [−0.0329, +0.0399] | −0.0417 [−0.1240, +0.0515] | +0.0180 [−0.0362, +0.0772] | **+0.1750 [+0.0915, +0.2909]** |
| code2test | **+0.2397 [+0.1783, +0.2994]** | **+0.4318 [+0.3207, +0.5229]** | **+0.2080 [+0.1672, +0.2511]** | **+0.3840 [+0.2544, +0.4880]** | **+0.0821 [+0.0098, +0.1417]** | **+0.1264 [+0.0790, +0.1785]** |
| trace2code | +0.1409 [−0.0344, +0.2275] | +0.2211 [−0.0358, +0.4056] | +0.1145 [−0.0396, +0.1619] | **+0.2855 [+0.1000, +0.3373]** | +0.0307 [−0.0658, +0.2125] | +0.1518 [−0.0097, +0.4725] |
| edit2ripple | −0.0417 [−0.1095, +0.0466] | **+0.0819 [+0.0145, +0.1771]** | −0.0179 [−0.0472, +0.0245] | **+0.1667 [+0.0861, +0.2519]** | **+0.0155 [+0.0010, +0.0294]** | +0.0000 [−0.0660, +0.0510] |

Bold = statistically supported (CI excludes zero). Unbolded differences are descriptive only.

### 4.3 Packed context (CUD-Pack, 8,000 tokens)

| Group | Gold coverage: fragment → whole file | Queries with ≥1 gold packed: fragment → whole file | Files packed (whole file) | Utilisation |
| :--- | :---: | :---: | :---: | :---: |
| **Overall** | 38.3% → **59.8%** | 45.8% → **68.4%** | 11.7 | 99.5% |
| comment2context | 19.4% → 35.8% | 32.5% → 51.2% | 11.0 | 99.3% |
| code2test | 51.8% → 68.3% | 58.5% → 74.5% | 12.3 | 99.4% |
| trace2code | 35.5% → 70.8% | 37.6% → 75.2% | 12.1 | 99.6% |
| edit2ripple | 44.5% → 58.3% | 55.2% → 69.0% | 10.7 | 99.5% |

### 4.4 Latency (descriptive only)

Per-query query-time latency, measured with 4 shards running concurrently (overall means: RepoNeedle `retrieve()` 549 ms on fragments vs 1,368 ms on whole files; p50 222 ms vs 499 ms). BM25 timings use the hoisted tokenisation described above and exclude it, so **RepoNeedle and BM25 latencies are not comparable** with each other or with README Part D. Whole-file documents make RepoNeedle's per-query work (including packing larger files) about 2–2.5× slower than on fragments.

## 5. Findings

1. **On matched input, RepoNeedle's full ranking is significantly better than BM25 overall**, on both representations (whole file: MRR +0.107, Recall@20 +0.190).
2. **Input representation matters for both systems.** Whole files improve RepoNeedle (Recall@20 +0.124 overall) and BM25 (+0.153) alike. The official harness therefore under-states both, but especially RepoNeedle's packed context (gold coverage 38% → 60%).
3. **comment2context remains a genuine weakness on deep recall.** Against BM25 given the same whole files, RepoNeedle is level on MRR but significantly worse on Recall@20 (−0.090). This refines Phase 0, whose "not significant" result compared against the chunk-level official BM25. It is consistent with Phase 0's residual lexical gap and documentation-distractor findings.
4. **code2test is RepoNeedle's clearest strength**, significant on every metric and representation.
5. **trace2code results are inconclusive at the cluster level.** Point estimates favour RepoNeedle, but the 101 queries come from only 7 repositories, and most matched CIs include zero.
6. **edit2ripple**: RepoNeedle is significantly better on Recall@10/20 with whole files. MRR differences are not significant.

## 6. Limitations

- **Small numbers of repository clusters**: 25 overall; 18, 12, 7 and 10 per task. Percentile bootstraps with few clusters (especially trace2code's 7) can under-cover, so treat per-task intervals as approximate.
- **Reconstructed whole files are approximations.** Symbol chunks are themselves capped at 8,000 characters, and header text beyond the `file` chunk's preview is lost. Reconstruction is close to, but not exactly, the source file.
- **Benchmark queries are structured JSON** (PR review context, PR descriptions, CI failures, diffs). Results do not speak to conversational natural-language queries.
- **Task labels are passed explicitly**, as in the official harness. AUTO intent classification is not evaluated here (Phase 0: 36% agreement with labels).
- **Single benchmark.** ARB v2 positives only; no held-out benchmark was used, and no parameter was tuned in this evaluation.
- Latency is descriptive only (§4.4).

## 7. Recommendation

The methodology is now reliable enough to proceed with **documentation-filter validation**, under these conditions:
- Use this evaluator's **whole-file full-ranking** view as the primary metric, alongside packed coverage, and keep the official harness numbers reported unchanged.
- Fix a **repository-level dev/test split before** looking at filter results (for example, by stratifying the 25 repositories across tasks). Choose the penalty on dev only, and report test once.
- Evaluate all four tasks, since a filter that helps comment2context could hurt tasks where documentation is occasionally gold (1% of edit2ripple gold).
- Pre-register the success criterion: a supported improvement on comment2context Recall@20 or MRR, and no supported regression on any other task.

## 8. Reproduction

See `REPRODUCE.md`.
