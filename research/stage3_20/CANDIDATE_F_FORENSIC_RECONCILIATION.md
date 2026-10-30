# RepoNeedle Stage 3.20 — Forensic Reconciliation of Candidate F

**Workspace:** `F:\RepoNeedle`  
**Date:** 2026-10-30  
**Historical Claim:** Candidate F achieved **0.2152 MRR** (Stage 3.5, commit `4f78cc3`).  
**Audited Reality:** Candidate F achieves **0.1351 MRR** on the canonical unconstrained ARB v2 benchmark.  
**Authoritative Verdict:** **`FORMALLY_INVALIDATED`**

---

## 1. Executive Summary & The Discrepancy

In Stage 3.5, Candidate F was reported as achieving an MRR of **0.2152** and Recall@20 of **0.5652** across the 345 positive ARB v2 queries, claiming parity with RepoMap (reported as 0.2140).

Subsequent canonical audits (Stages 3.6 through 3.19) revealed that under authentic, unconstrained evaluation conditions, Candidate F collapses to **`0.1351 MRR`**, lagging pure decoupled Okapi BM25 (**`0.1752 MRR`**) by **-0.0401 MRR (-22.89%)** and lagging ARM-101 (**`0.2078 MRR`**) by **-0.0727 MRR (-34.99%)**.

This forensic document details the exact technical reasons why Candidate F produced 0.2152 in Stage 3.5 and why it collapsed to 0.1351 under canonical reproduction.

---

## 2. Reconstructed Comparison: Stage 3.5 Procedure vs. Canonical Stage 3.20 Procedure

| Evaluation Dimension | Stage 3.5 Historical Procedure | Canonical Stage 3.20 Procedure | Impact on Candidate F |
| :--- | :--- | :--- | :--- |
| **`code2test` Candidate Pool** | **`tests_only` Filter:** Filtered candidate search space to test files only | **100% Unconstrained:** All repository source files and tests eligible | Artificially removed hundreds of code distractors; MRR collapsed from ~0.25+ to **0.0601** |
| **Corpus Snapshot Boundary** | **Artificially Capped:** Caddy capped at 250 files; content clamped to 25k chars | **Full Corpus:** All 605 files in Caddy loaded without truncation | Kept PageRank graph small; full corpus created thousands of noisy cross-crate edges |
| **Ripgrep Micro-Fixture** | **Hardcoded String Bypass:** Handled search.rs/standard.rs with string matching | **Pure Algorithmic Routing:** Standard regex / AST call resolution | Artificially awarded rank 1 (MRR 1.0) on held-out diagnostic failure |
| **Symbol Indexing** | Extracted symbols appended directly into file content string buffer | Polyglot symbols stored in structured metadata, indexed separately | Appending text inflated file length 2x-5x, severely penalizing BM25 Okapi length norm |
| **Graph Edge Weighting** | Unnormalized bidirectional diffusion across all parsed manifest dependencies | Verified function-call edges with degree normalization and soft damping | Unnormalized diffusion turned crate root files (e.g. `lib.rs`) into attractor supernodes |
| **RepoMap Comparison** | Hardcoded static paper reference constant (**0.2140**) | Pinned upstream reference execution (**0.2293**) | Created illusory claim that Candidate F beat RepoMap |

---

## 3. Task-Level Breakdown of the Collapse

Recomputed from [research/stage3_20/CANDIDATE_F_METRIC_RECOMPUTATION.csv](file:///F:/RepoNeedle/research/stage3_20/CANDIDATE_F_METRIC_RECOMPUTATION.csv):

| Task Type | Queries | Stage 3.5 Reported MRR | Canonical CAND-F MRR | Baseline BM25 MRR | Champion ARM-101 MRR | CAND-F Deficit vs BM25 | CAND-F Deficit vs ARM-101 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `code2test` | 106 | ~0.2500* | **0.0601** | 0.0784 | 0.1257 | -0.0183 | -0.0656 |
| `comment2context` | 80 | ~0.2000 | **0.1239** | 0.1550 | 0.1984 | -0.0311 | -0.0745 |
| `edit2ripple` | 58 | ~0.1900 | **0.1284** | 0.2424 | 0.2654 | **-0.1139** | **-0.1370** |
| `trace2code` | 101 | ~0.2300 | **0.2265** | 0.2542 | 0.2683 | -0.0276 | -0.0418 |
| **OVERALL** | **345** | **0.2152** | **0.1351** | **0.1752** | **0.2078** | **-0.0401** | **-0.0727** |

*Note on `edit2ripple`:* The catastrophic collapse in `edit2ripple` (-0.1139 vs BM25) confirms that Candidate F's bidirectional graph diffusion aggressively promoted crate entry points (`main.rs`, `lib.rs`, `init.py`) over the true downstream edit ripple targets.

---

## 4. Query-Level Win/Tie/Loss Statistics

Across all 345 queries (detailed in [research/stage3_20/CANDIDATE_F_QUERY_DIFF.csv](file:///F:/RepoNeedle/research/stage3_20/CANDIDATE_F_QUERY_DIFF.csv)):
- **Candidate F vs. BASE-BM25:**
  - Candidate F Wins: 161 queries
  - BASE-BM25 Wins: 159 queries
  - Ties: 25 queries
  - While win counts are comparable, Candidate F's losses were catastrophic drops from rank 1 to ranks 15-50+, pulling down overall MRR.
  - Paired Wilcoxon Signed-Rank Test: **`p = 0.0085`** (Statistically significantly inferior to BM25 at $p < 0.01$).
- **Candidate F vs. ARM-101-BASE:**
  - ARM-101 Wins: 238 queries
  - Candidate F Wins: 82 queries
  - Ties: 25 queries
  - Paired Wilcoxon Signed-Rank Test: **`p = 7.20 x 10^-18`** (Decisively and overwhelmingly inferior to ARM-101).

---

## 5. Definitive Conclusion on Candidate F

Candidate F's reported $0.2152$ MRR in Stage 3.5 was a statistical artifact of candidate pre-filtering, artificial repository clamping, and hardcoded diagnostic strings. Under authentic benchmark rules, it is an inferior algorithm that damages lexical ranking quality. Its status remains **`FORMALLY_INVALIDATED`**.
