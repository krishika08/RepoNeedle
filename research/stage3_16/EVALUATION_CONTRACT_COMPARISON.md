# RepoNeedle Stage 3.10.1: Evaluation Contract Comparison Matrix

## 1. Systematic Comparison Across Research Stages

This document provides a side-by-side audit of the evaluation contract, code hashes, candidate universes, metric denominators, and operational parameters across Stage 3.5, Stage 3.9.1, and Stage 3.10.

| Dimension | Stage 3.5 Protocol (Report A) | Stage 3.9.1 Canonical Protocol | Stage 3.10 Protocol (Report B) | Audited Reconciliation Status |
| :--- | :--- | :--- | :--- | :--- |
| **Git Commit Reference** | `4f78cc3658df` (Stage 3.5 Anchor) | `b7cf35bc6ebf` (Stage 3.9.1) | `21d2586b71e0` (Stage 3.10 HEAD) | Verified continuous linear lineage |
| **Evaluator Script** | `research/stage3_5/evaluate_graph_retrieval.py` | `research/stage3_9/evaluate_cascade_ablation.py` | `research/stage3_10/evaluate_stage3_10.py` | Scripts archived and preserved |
| **Benchmark Denominator** | Purported 345 positive ARB v2 queries | Exactly 345 positive ARB v2 queries | Exactly 345 positive ARB v2 queries | Identical 345 queries verified |
| **Corpus Snapshots** | 218 snapshots (`corpus_manifest.jsonl`) | 218 snapshots (`corpus_manifest.jsonl`) | 218 snapshots (`corpus_manifest.jsonl`) | Identical 218 snapshots verified |
| **Candidate Universe** | **RESTRICTED**: `code2test` restricted to `tests_only` | **UNCONSTRAINED**: Full repository candidates | **UNCONSTRAINED**: Full repository candidates | Root cause of Candidate C & F inflation |
| **Diagnostic Mode** | String bypasses active in diagnostic paths | Zero diagnostic shortcuts | Zero diagnostic shortcuts | Shortcuts removed in canonical runs |
| **BM25 Length Norm** | **Coupled**: AST symbols included in length | **Decoupled**: Only body & path tokens count | **Decoupled**: Only body & path tokens count | Explains BM25 0.1705 vs 0.1752 |
| **Top-Rank Protection** | None (equal unweighted score fusion) | Ranks 1–3 BM25 lock | Ranks 1–3 BM25 lock | Prevents early-rank graph regressions |
| **Graph Edge Weighting** | Unnormalized bidirectional diffusion | Degree-normalized ($\frac{1}{\sqrt{d_{\text{out}} \cdot d_{\text{in}}}}$) | Degree-normalized ($\frac{1}{\sqrt{d_{\text{out}} \cdot d_{\text{in}}}}$) | Prevents high-degree hub explosion |
| **Package Fencing** | None (cross-module diffusion allowed) | Enabled (confines diffusion to package) | Enabled (confines diffusion to package) | Prevents cross-crate contamination |
| **Test Discovery** | None | Stem-matching (`test_<stem>.py`) | Stem-matching + Class-to-Test Invocations | Stage 3.10 innovation (+0.0015 MRR) |
| **RepoMap Evaluation** | **Hardcoded Constant** (`0.2140 MRR`) | **Live Execution** (commit `9e4d689`) | **Live Execution** (commit `9e4d689`) | Live RepoMap achieves 0.2293 MRR |
| **BCY@8k Definition** | **Token Budget** (`pack_files` via tokenizer) | **Character Greedy-Stop** (`len(text) <= 8000`) | **Character Greedy-Stop** (`len(text) <= 8000`) | Explains 0.3184 vs 0.0488 divergence |
| **Latency Metric** | Mean query latency ($11.60\text{ ms}$) | Median ($8.12\text{ ms}$) & Mean ($34.12\text{ ms}$) | Median ($8.30\text{ ms}$) & Mean ($26.72\text{ ms}$) | Kept strictly distinct |
| **Memory Metric** | Claimed universal sub-100 MB | Process RSS (~930 MB for full suite) | Process RSS ($937.9\text{ MB}$, peak $3,962.7\text{ MB}$) | Click is ~104 MB, Caddy is ~160 MB |

---

## 2. Query Denominators and Missing Query Verification

Every single one of the 345 benchmark queries was matched across:
- `research/stage3_10/PER_QUERY_RESULTS.csv`
- `research/stage3_9_1/INDEPENDENT_RECOMPUTATION.csv`
- `research/stage3_9_2/PER_QUERY_CROSS_STAGE_COMPARISON.csv`
- `research/stage3_10_1/CANONICAL_PER_QUERY_RESULTS.csv`

### Breakdown by Task
1. `v2_code2test`: 106 queries
2. `v2_comment2context`: 80 queries
3. `v2_trace2code`: 101 queries
4. `v2_edit2ripple`: 58 queries
**Total Queries**: Exactly 345 positive samples. Zero missing queries, zero filtered queries, zero synthetic rows.
