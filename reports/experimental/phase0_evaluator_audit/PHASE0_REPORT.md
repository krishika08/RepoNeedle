# Phase 0 — ARB v2 Evaluator Forensic Audit

**Status**: EXPERIMENTAL DIAGNOSTIC (2026-11-09). Development-branch engine (identical to released 1.1.0). Not an official benchmark result; the official harnesses (`benchmarks/run_complete_arb_evaluation.py`, `benchmarks/run_arb_current_engine.py`) and ARB metric definitions are unchanged.
**Tool**: `benchmarks/run_arb_evaluator_audit.py`. **Data**: ARB v2 positive split, N=345 (80 `comment2context`).
**Fidelity**: the audit's recomputed official sequence reproduces the official current-engine run on **345 / 345** queries (MRR, Recall@5/10/20). Its BM25 reproduces the historical official BM25 per-query metrics and BCY@8k on **345 / 345**.

---

## 1. Evaluator execution flow

| Step | What happens | Code |
| :--- | :--- | :--- |
| Documents | One document per path, built from the **single longest ARB chunk** for that path, truncated to 25,000 chars | `run_complete_arb_evaluation.py` / `run_arb_current_engine.py` |
| Ranking | `engine.retrieve(task_type=<benchmark label>, budget=8000)` fuses lexical + semantic (+ workflow boost) scores over **all** files | `reponeedle/engine.py` |
| Packing | CUD-Pack receives the complete ranking, scans the top 85 in rank order, skips files no tier fits, then backfills outlines | `reponeedle/core/packer.py` |
| Evaluator input | `selected_files` (packed order), then **every other file in corpus (chunk-file) order** | harness |
| Metrics | ARB `sample_metrics` → `unique_ranked_paths` → file-level `reciprocal_rank`, `recall_at(k)`; BCY via `pack_files(top-20)` | `agent_retrieval_bench.baseline`, `.bcy_curve` |
| BM25 baseline | **All chunks** ranked by BM25 score (ties by path), collapsed to files | `rank_chunks_bm25_with_scores` |

The benchmark passes the task label explicitly, so automatic intent classification is **not** exercised by the official numbers.

## 2. Ranking vs packing (overall, N=345)

| View | MRR | Recall@5 | Recall@10 | Recall@20 |
| :--- | :---: | :---: | :---: | :---: |
| Official sequence (packed + corpus order) | 0.2153 | 0.3032 | 0.3677 | 0.3842 |
| **View A: RepoNeedle full ranking** | **0.2379** | **0.3061** | **0.4407** | **0.5803** |
| View A: BM25 full ranking (official baseline) | 0.1520 | 0.1899 | 0.3034 | 0.4452 |

- Full ranking minus official: MRR +0.0226 (repo-clustered 95% CI [+0.0169, +0.0284]); Recall@20 +0.1961 (CI [+0.1188, +0.2521]).
- **96** gold files ranked in RepoNeedle's top 20 are pushed out of the official top 20 by corpus ordering; corpus order "gains" **1**.
- CUD-Pack delivers 8.9 files on average (99.6% budget utilisation). Gold coverage of the packed context is 38.3%; 45.8% of queries get at least one gold file packed.
- ARB's own `pack_files` applied to RepoNeedle's full ranking gives BCY@8k 0.3501 vs 0.3443 for the official sequence. **Packing is not the bottleneck**; ranking is.

## 3. BM25 vs RepoNeedle under all three views

| Task (N) | Official MRR / R@20 | **Full-ranking MRR / R@20** | BM25 MRR / R@20 | Packed gold coverage / success | BCY@8k RN-full / BM25 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| code2test (106) | 0.2546 / 0.5176 | **0.2736 / 0.6434** | 0.1057 / 0.3066 | 51.8% / 58.5% | 0.4909 / 0.1541 |
| comment2context (80) | 0.1658 / 0.1938 | **0.1857 / 0.3146** | 0.1974 / 0.5292 | 19.4% / 32.5% | 0.1896 / 0.2604 |
| trace2code (101) | 0.2262 / 0.3548 | **0.2577 / 0.6782** | 0.1638 / 0.4934 | 35.5% / 37.6% | 0.2954 / 0.1931 |
| edit2ripple (58) | 0.1929 / 0.4540 | **0.2104 / 0.6609** | 0.1536 / 0.4986 | 44.5% / 55.2% | 0.4095 / 0.2428 |

Paired, repository-clustered 95% CIs (full ranking minus BM25):

| Task | Δ MRR [CI] | Δ Recall@20 [CI] |
| :--- | :---: | :---: |
| Overall | +0.0859 [+0.0372, +0.1186] | +0.1351 [+0.0178, +0.2185] |
| code2test | +0.1679 [+0.1070, +0.2240] | +0.3368 [+0.1987, +0.4642] |
| **comment2context** | **−0.0117 [−0.0991, +0.0635]** (not significant) | **−0.2146 [−0.3720, −0.1011]** (significant) |
| trace2code | +0.0939 [−0.0333, +0.1569] | +0.1848 [−0.0296, +0.2958] |
| edit2ripple | +0.0567 [+0.0179, +0.1194] | +0.1624 [+0.0351, +0.3268] |

View C (remainder): no gold file has a zero fused or zero BM25 score; every remainder position in the official sequence is a corpus-order position, not a retrieval rank.

## 4. Representative comment2context traces

Full traces (top-25 with fused / lexical / semantic / structural scores, packed files with tiers, official top-25 with source, BM25 top-25): `traces.jsonl`.

| Query | Gold rank: official / full / BM25 | What the trace shows |
| :--- | :---: | :--- |
| `a467dd60…` ipython | 336 / **14** / 60 | Official sequence loses a top-20 hit: after 9 packed files, ranks 10+ are `.editorconfig`, `.flake8`, … in corpus order. Top-2 RepoNeedle results are `CONTRIBUTING.md` and `version6.rst`. |
| `bf473089…` hypothesis | 116 / 335 / **3** | Genuine RepoNeedle ranking failure: tests and `.rst`/`.md` docs fill the top; `core.py` (BM25 rank 3) is at full rank 335. |
| `7d661ed7…` diffusers | **2** / **2** / 150 | RepoNeedle wins clearly; gold packed at position 2. |
| `3e3c5349…` tox | 161 / 108 / 76 | Both fail; RepoNeedle's top 10 are almost all `docs/*.rst`. |

In every trace the structural (graph) score is 0.000 for every file.

## 5. Root-cause assessment (comment2context)

| Candidate cause | Verdict | Evidence |
| :--- | :--- | :--- |
| Evaluator ordering / metric construction | **Major contributor (inflates the deficit)** | Recall@20 0.1938 official → 0.3146 full ranking; 17 lost top-20 hits; MRR deficit vs BM25 not significant on the full ranking |
| CUD-Pack selection | Not a cause | ARB packing of the same ranking gives identical BCY@8k (0.1896) |
| Graph signal dilution | Not a cause | Structural score is 0 for all files (PageRank fusion is off by default); the 0.20 structural weight only rescales scores |
| Incorrect task routing | Not a cause **in the benchmark** (label is passed explicitly). Relevant for real AUTO use: AUTO would route only 55/80 comment2context and **125/345 overall (36%)** to the labelled task |
| Semantic noise | **Not supported** | Semantic-only Recall@20 0.3896 / MRR 0.1942 is *better* than lexical-only (0.2875 / 0.1587) and than the fusion (0.3146 / 0.1857) |
| Lexical signal quality | **Main ranking weakness** | RepoNeedle's own BM25 index scores far below ARB's chunk-level BM25 (Recall@20 0.2875 vs 0.5292) |
| Documentation distractors | **Contributor** | 23% of RepoNeedle's comment2context top-8 are docs vs 7% for BM25; 0% of gold files are docs. `enable_doc_filter` exists but is off by default |
| Query form | **Premise mismatch** | All 345 ARB queries (all tasks) are structured JSON (PR review context, PR descriptions, CI failure excerpts, diffs), none conversational |

## 5a. Document representation (comment2context, N=80, all queries accounted for)

**Finding.** The benchmark harness builds each RepoNeedle document from the **single longest ARB chunk** for a path. ARB stores one `file` chunk per path (the file's opening text, truncated; about 2,000 characters in this corpus) plus one chunk per symbol covering the rest of the file. RepoNeedle therefore ranks files from **fragments**, while the official BM25 baseline ranks **every chunk of every file**. Real RepoNeedle use (`from_directory`) reads whole files up to 500 KB, so the official numbers measure a handicapped input condition, not the product.

**Diagnostic.** `--doc-mode reconstructed` rebuilds each file from its ARB chunks (header lines of the `file` chunk before the first symbol, then all symbol chunks in line order) and re-ranks with the **unchanged** engine. ARB's own BM25 was also run on whole-file documents of both representations, to separate granularity (chunks vs files) from text coverage.

| comment2context (N=80) | MRR | Recall@5 | Recall@10 | Recall@20 |
| :--- | :---: | :---: | :---: | :---: |
| RepoNeedle full ranking, official documents (longest chunk) | 0.1857 | 0.1646 | 0.2250 | 0.3146 |
| **RepoNeedle full ranking, reconstructed documents** | **0.2037** | **0.2458** | **0.3521** | **0.4896** |
| RepoNeedle official sequence, reconstructed documents | 0.1869 | 0.2458 | 0.3271 | 0.3583 |
| RepoNeedle lexical-only: official → reconstructed | 0.1587 → 0.2071 | 0.1479 → 0.2583 | 0.2375 → 0.3646 | 0.2875 → 0.4646 |
| RepoNeedle semantic-only: official → reconstructed | 0.1942 → 0.1917 | 0.1646 → 0.1833 | 0.2437 → 0.3042 | 0.3896 → 0.4417 |
| ARB BM25 on chunks (official baseline) | 0.1974 | 0.2146 | 0.4042 | 0.5292 |
| ARB BM25 on whole files, longest chunk only | 0.1875 | 0.1875 | 0.2542 | 0.3563 |
| ARB BM25 on whole files, reconstructed | 0.2063 | 0.2812 | 0.4333 | 0.5792 |

Repository-clustered 95% CIs:

| Comparison | Δ MRR | Δ Recall@20 |
| :--- | :---: | :---: |
| RepoNeedle reconstructed − RepoNeedle official documents | +0.0180 [−0.0340, +0.0781] | **+0.1750 [+0.0928, +0.2929]** |
| RepoNeedle lexical reconstructed − lexical official | +0.0484 [−0.0119, +0.1188] | **+0.1771 [+0.0968, +0.2981]** |
| **RepoNeedle reconstructed − BM25 (official baseline)** | **+0.0063 [−0.0485, +0.0571]** | **−0.0396 [−0.1945, +0.1099]** |

Packed context (CUD-Pack, unchanged): gold coverage 19.4% → 35.8%; queries with at least one gold file packed 32.5% → 51.2%.

Conclusions:
- Text coverage, not ranking logic, is the largest driver. BM25 degrades the same way (Recall@20 0.5792 → 0.3563) when restricted to the fragment RepoNeedle receives.
- With whole-file input, the comment2context difference between RepoNeedle and BM25 is **not statistically significant** on MRR or Recall@20.
- Granularity is not BM25's advantage: whole-file BM25 (0.5792) is at least as good as chunk-level BM25 (0.5292).
- A **residual lexical gap** remains on equal input: RepoNeedle lexical-only Recall@20 0.4646 vs ARB whole-file BM25 0.5792.
- The evaluator gap persists with whole files (official sequence Recall@20 0.3583 vs full ranking 0.4896).

Reconstructed-document traces (`reconstructed_docs/traces.jsonl`):

| Query | Gold full rank: fragments → whole files | Note |
| :--- | :---: | :--- |
| `bf473089…` hypothesis | **335 → 2** (and 513 → 28) | Fixed by representation; gold now packed |
| `3e3c5349…` tox | 108 → 36 | Improves, but the top 5 are all `docs/*.rst` |
| `a467dd60…` ipython | 14 → 12 | `CONTRIBUTING.md`, `version6.rst` still in top 5 |
| `7d661ed7…` diffusers | 2 → **9** | Worse: two `contribution.md` files enter the top 5; documentation gains text too |

## 5b. Documentation distractors (comment2context, N=80, official documents)

Diagnostic: the same full rankings with documentation files (`.md`, `.rst`, `.txt`, `.adoc`, `.html`, or under `docs/`/`doc/`) removed, applied identically to RepoNeedle and BM25. No comment2context gold file is documentation, so removal cannot drop gold files; this is an **oracle-style upper bound**, not a deployable filter. Fidelity: metrics with documentation included equal the audit's full-ranking metrics on 80 / 80 queries. Results: `doc_distractor/`.

| comment2context (N=80) | MRR | Recall@5 | Recall@10 | Recall@20 | Docs in top 10 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| RepoNeedle | 0.1857 | 0.1646 | 0.2250 | 0.3146 | 2.24 |
| RepoNeedle, documentation removed | 0.2033 | 0.2021 | 0.2729 | 0.3604 | — |
| BM25 | 0.1974 | 0.2146 | 0.4042 | 0.5292 | 0.71 |
| BM25, documentation removed | 0.2138 | 0.2521 | 0.4208 | 0.5458 | — |

| Comparison (repo-clustered 95% CI) | Δ MRR | Δ Recall@20 |
| :--- | :---: | :---: |
| RepoNeedle without docs − with docs | **+0.0176 [+0.0105, +0.0232]** (53 wins / 0 losses) | **+0.0458 [+0.0098, +0.0905]** |
| BM25 without docs − with docs | +0.0164 [+0.0019, +0.0482] | +0.0167 [+0.0000, +0.0485] |
| RepoNeedle without docs − BM25 without docs | −0.0105 [−0.1018, +0.0656] | −0.1854 [−0.3556, −0.0578] |

RepoNeedle ranks a median of 4 (mean 49.8) documentation files above its best-ranked gold file. Documentation distractors are a real, significant contributor for RepoNeedle, but they explain roughly a fifth of the Recall@20 gap; document representation explains most of it.

## 6. Problem classification

| Problem class | Present? | Size of effect (comment2context unless noted) | Evidence |
| :--- | :--- | :--- | :--- |
| **Evaluator methodology** (unpacked files ranked in corpus order) | **Yes, all tasks** | Recall@20 under-measured by +0.196 overall, +0.121 comment2context; MRR by +0.023 overall | §2–§3; 96 lost top-20 hits overall |
| **Document representation** (harness feeds one fragment per file) | **Yes, largest** | Recall@20 +0.175 for RepoNeedle; BM25 degrades identically when given the same fragments | §5a |
| **Documentation distractors** | **Yes, secondary** | MRR +0.018, Recall@20 +0.046 (oracle upper bound) | §5b |
| **Retrieval ranking** (residual) | **Yes, smaller** | RepoNeedle lexical-only vs ARB whole-file BM25 on equal input: Recall@20 0.4646 vs 0.5792. Fused vs BM25 on whole files: not significant | §5a |
| **Context packing** (CUD-Pack) | **No** | Packing the same ranking with ARB's packer gives identical BCY@8k; packed coverage rises with better input | §2, §5a |
| Graph dilution | No | Structural score is 0 for every file | §4 |
| Semantic noise | Not supported | Semantic-only outperforms lexical-only on official documents | §5 |
| Task routing | Not in the benchmark (labels are explicit); **yes for AUTO users** | AUTO would assign the labelled task to only 125 / 345 queries (36%) | §5 |
| Conversational query handling | **Not testable on ARB v2** | 0 of 345 queries are conversational; all are structured JSON | §5 |

## 7. Decision

Gate outcome against the Phase 0 criteria:
- **The evaluator assigns misleading ranks to unselected files: confirmed.** The corrected diagnostic evaluator is provided as `benchmarks/run_arb_evaluator_audit.py` (experimental, separate output directory). The official harness and published metric definitions are unchanged.
- **Full-ranking deficit for comment2context: not confirmed under realistic input.** It is significant only when RepoNeedle receives file fragments; with whole files it is not significant (MRR +0.006, Recall@20 −0.040, CIs span zero).
- **Packed-context coverage is limited by the ranking and its inputs, not by CUD-Pack.**

Therefore Adaptive Query Routing 2.0's **conversational fusion re-weighting is not supported by the evidence** and should not be implemented now.

## 8. Engineering recommendation

**Address first: benchmark input fidelity and full-ranking evaluation** (measurement, no product change). Promote the diagnostic into a clearly labelled "corrected" evaluation that (1) gives RepoNeedle whole-file documents reconstructed from ARB chunks, the same text BM25 ranks, and (2) reports full-ranking MRR/Recall@K alongside packed-context coverage, next to the unchanged official numbers. *Evidence*: this is the single largest effect (+0.175 Recall@20) and it changes the sign of the comment2context conclusion. Any ranking change tuned on the current harness would optimise a fragment artifact.

**Then, the product fix with the best evidence: documentation-distractor handling.** RepoNeedle already has an `enable_doc_filter` penalty, off by default. The oracle bound is +0.018 MRR on comment2context (CI excludes zero, 0 losses). It must be validated on repository-held-out splits under the corrected evaluator across **all four tasks** (1% of edit2ripple gold files are documentation) and against documentation-seeking queries before any default change.

**Then: the residual lexical gap** (RepoNeedle field-weighted BM25 vs ARB BM25 on identical whole-file input: Recall@20 0.4646 vs 0.5792). Likely candidates to investigate: length normalisation, field weights, and JSON key tokens in structured queries.

**Separately: AUTO intent classification** (36% agreement with ARB task labels). It does not affect the published task-conditioned numbers, but it does affect real users. ARB's task labels allow a classifier accuracy evaluation with repository-level splits.

**Postpone:**
- Conversational fusion weights (lexical 0.80 / semantic 0.15 / structural 0.05). Lexical-only underperforms the current fusion on both document representations, and ARB v2 has no conversational queries to validate against.
- Semantic noise filtering (not supported by the signal analysis).
- Graph / PageRank changes (zero structural contribution in these configurations).
- CUD-Pack changes (not a bottleneck).
- README or headline claim updates (diagnostic results only; not official benchmark results).

**Expectation-setting**: the evaluator and representation corrections change how much of RepoNeedle's ranking quality is *measured*; they do not change the product. Product-level MRR gains should be claimed only from validated ranking changes, measured under the corrected evaluator on held-out repositories.

<!-- full-reconstructed-results -->
