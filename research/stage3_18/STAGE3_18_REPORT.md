# RepoNeedle Stage 3.18 — Candidate Provenance, Benchmark Reconciliation & Research Integrity Audit Report

**Document ID**: `STAGE3-18-REPORT-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `461f690d5b4bd3c21776eaaf94f038250ee9d6a0`  
**Production Code Reference**: `12142e8` (`reponeedle/` **100% untouched**)  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`) — **VERIFIED UNCHANGED**  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`) — **VERIFIED UNCHANGED**  
**Candidate Leaderboard Verdict**: **`RECONCILED — REPRODUCIBLE CANDIDATE LEADERBOARD`**  
**ContextBench External Gate Verdict**: **`BLOCKED — OFFICIAL DATA ACQUISITION`**  

---

## 1. Executive Summary & Mission Charter

Stage 3.18 conducts a comprehensive forensic reconciliation of RepoNeedle's historical evaluation results on the Agent Retrieval Benchmark (ARB v2, 345 positive queries across 25 repositories), establishing one trustworthy, reproducible candidate leaderboard before any further retrieval optimization or external performance claims.

In strict adherence to the Stage 3.18 research charter:
1. **Zero Production Code Modifications**: Production retrieval code under `reponeedle/` was held completely frozen. Zero ranking weights, graph parameters, scoring formulas, thresholds, or retrieval algorithms were modified.
2. **Individual Candidate Provenance**: Audited exact commits, source implementations, graph diffusion parameters, lexical scoring formulas, and candidate generation constraints for `CAND-C`, `CAND-F`, `ARM-101-BASE`, `BASE-BM25`, and `BASE-REPOMAP`.
3. **Soft Lexical Damping & Verified Edges Verified**: Confirmed in source code that `ARM-101-BASE` implements soft lexical damping ($\tau = 0.25$) and Level 1 verified function call edges without hub attenuation.
4. **Historical Metric Discrepancies Reconciled**: Investigated and explained all numerical differences between earlier reports (Stage 3.5) and Stage 3.17 across BM25 MRR ($0.1705 \to 0.1752$), RepoMap MRR ($0.2140 \to 0.2293$), RepoMap Recall@20 ($0.5681 \to 0.6599$), Candidate C MRR ($0.2040 \to 0.1399$), and Candidate F MRR ($0.2152 \to 0.1351$). Exactly zero discrepancies remain unresolved.
5. **Candidate F Invalidation Verified**: Confirmed that Candidate F's Stage 3.5 score depended on artificial test-only candidate filtering, diagnostic shortcuts, and synthetic lookups. Traced the provenance of the reported $p = 0.0122$ citation (the upper bound of a Stage 3.10/3.11 clustered bootstrap confidence interval), and recomputed the exact live Wilcoxon test ($p = 0.008541$), proving Candidate F is statistically significantly worse than BM25 on the unconstrained corpus.
6. **Unified Leaderboard Reproduced**: Produced a fair, single-standard comparison of all 5 systems across all 345 positive queries, reporting MRR, Recall@5/10/20, Precision@20, Token BCY@4k/8k, Latency P50/P95, index build time, and process RSS.
7. **Cluster-Aware Statistical Analysis**: Performed 10,000-replicate repository-cluster-aware bootstrap resampling across all 25 repositories. Proved that `ARM-101-BASE` statistically significantly outperforms BM25 on both MRR ($+18.62\%$, $p < 10^{-30}$, 95% Clustered CI $[+0.0237, +0.0442]$) and Recall@20 ($+24.54\%$, $p < 10^{-13}$, 95% Clustered CI $[+0.0734, +0.1692]$), while remaining competitive with RepoMap ($p = 0.0559$, CI $[-0.0732, +0.0177]$) with a $>13.9\times$ CPU latency advantage.
8. **ContextBench External Gate Preserved**: Preserved the status `BLOCKED — OFFICIAL DATA ACQUISITION` without retrying blocked downloads or using unofficial mirrors.

---

## 2. Research Safeguards & Tag Immutability

Prior to conducting any analysis, Git state, commits, and tags were dereferenced and verified:

```
Branch: research-program
Starting HEAD SHA: 461f690d5b4bd3c21776eaaf94f038250ee9d6a0
Tag v0.1.0-baseline: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9 (MATCH)
Tag stage3-candidate-freeze: cd7f3b01e28695f9a9357e0815069e0eae85baca (MATCH)
Working Tree: Clean
Production Code reponeedle/: Untouched (0 diffs)
```

No git tags were moved, retagged, or deleted. All prior reports under `research/` were preserved.

---

## 3. Audited Candidate Identities & Provenance

Complete architectural specifications and evaluation details are documented in [`research/stage3_18/CANDIDATE_PROVENANCE.md`](file:///F:/RepoNeedle/research/stage3_18/CANDIDATE_PROVENANCE.md).

### Summary Table of Audited Candidates:

| Candidate ID | Exact Source Commit | Architecture Specification | Lexical Scorer | Graph Structure & Diffusion | Candidate Pool Policy | Canonical MRR | Status |
|---|---|---|---|---|---|---|---|
| **`BASE-BM25`** | `12142e8` | Decoupled Okapi BM25 | Okapi $k_1=1.5, b=0.75$, decoupled paths | None ($W_{\text{graph}}=0.0$) | Full unconstrained repository | **0.1752** | **Preregistered Lexical Baseline** |
| **`BASE-REPOMAP`** | Pinned `9e4d689` | Aider AST Tag Reference Graph | Tree-sitter identifier frequency | Personalized PageRank ($\alpha=0.85$) on AST definitions/references | Full unconstrained repository | **0.2293** | **Preregistered External Leader** |
| **`CAND-C`** | `cd7f3b0` | Equal Weight Hybrid (BM25 + Semantic + PageRank) | Coupled token/path BM25 | Python AST import graph; PageRank diffusion | Restricted in Stage 3.5; Unconstrained in Stage 3.8 | **0.1399** | **Superseded Frozen Candidate** |
| **`CAND-F`** | `4f78cc3` | Manifest-Aware Polyglot Graph + PageRank | Coupled BM25 with appended regex symbols | Cargo/Go/npm manifest parsing; bidirectional PageRank | Restricted in Stage 3.5; Unconstrained in Stage 3.6 | **0.1351** | **Formally Invalidated Prototype** |
| **`ARM-101-BASE`** | `12142e8` | Cascaded Ranker with Soft Lexical Damping | Decoupled Okapi BM25 | Level 1 verified function call edges; $\tau=0.25$ soft damping; unattenuated hubs | Full unconstrained repository | **0.2078** | **Preregistered Candidate Champion** |

### Soft Lexical Damping & Verified Edges Implementation Check:
- Verified in [`research/stage3_14/pilot_attenuation.py`](file:///F:/RepoNeedle/research/stage3_14/pilot_attenuation.py#L143-L151):
  $$\text{threshold} = \tau \times \max(0, \text{BM25}_{s1} - \text{BM25}_{s2})$$
  Candidate 1 is protected from displacement by graph neighbors unless the fused graph score exceeds it by at least $\tau \times \text{margin}$ ($\tau = 0.25$).
- Verified in [`research/stage3_11/function_graph_engine.py`](file:///F:/RepoNeedle/research/stage3_11/function_graph_engine.py): Call edges are strictly restricted to `{"verified_call", "unique_global_call", "intra_file_call"}` at depth 1.

---

## 4. Reconciled Historical Metric Discrepancies

Detailed analysis is documented in [`research/stage3_18/METRIC_RECONCILIATION.md`](file:///F:/RepoNeedle/research/stage3_18/METRIC_RECONCILIATION.md) and [`research/stage3_18/METRIC_RECONCILIATION.csv`](file:///F:/RepoNeedle/research/stage3_18/METRIC_RECONCILIATION.csv).

| Metric Discrepancy | Earlier Reported | Canonical Reproduced | Delta | Root Cause Category | Detailed Forensic Mechanism |
|---|---|---|---|---|---|
| **BM25 MRR** | 0.1705 | **0.1752** | $+0.0047$ | Scorer Refactoring | Stage 3.5 used coupled token/path BM25; Stage 3.9/3.14 decoupled path scoring with standard Okapi BM25 ($k_1=1.5, b=0.75$). |
| **RepoMap MRR** | 0.2140 | **0.2293** | $+0.0153$ | Superseded Static Constant | Stage 3.5 line 278 hardcoded 0.2140 from a draft paper table; live execution of pinned RepoMap (`9e4d689`) yields 0.2293. |
| **RepoMap Recall@20** | 0.5681 | **0.6599** | $+0.0918$ | Metric Definition Shift | Stage 3.5 reported binary Hit@20 ($196/345 = 0.5681$) mislabeled as Recall@20; canonical evaluation uses multi-target fractional Recall@20 ($0.6599$). |
| **Candidate F MRR** | 0.2152 | **0.1351** | $-0.0801$ | Candidate Filtering & Bypasses | Stage 3.5 used test-only candidate filtering in `code2test`, synthetic lookups, and Ripgrep bypasses; collapses to 0.1351 under full corpus retrieval. |
| **Candidate C MRR** | 0.2040 | **0.1399** | $-0.0641$ | Candidate Pool Restriction | Stage 3.5 clamped candidate pools to 20 files per task; collapses to 0.1399 under unconstrained 25-repository candidate pools. |
| **Caddy Process RSS** | 103.1 MB | **198.0 MB** | $+94.9\text{ MB}$ | Artificial File Clamping | Stage 3.5 clamped discovery to 250 files via `max_files=250` and truncated to 25k chars; true 605-file Caddy requires 198 MB RSS. |

**Verdict**: Exactly zero discrepancies remain unresolved.

---

## 5. Candidate F Invalidation Verification

Detailed forensics are recorded in [`research/stage3_18/CANDIDATE_F_INVALIDATION_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_18/CANDIDATE_F_INVALIDATION_AUDIT.md):

1. **Full-Corpus Evaluation Confirmed**: Re-evaluation included all 345 positive ARB v2 queries across all 25 repositories without candidate pool restrictions or test-only shortcuts.
2. **Statistical Significance Verified**:
   - Query-level paired Wilcoxon signed-rank test vs decoupled BM25 ($MRR = 0.1752$): **$p = 0.008541$** (two-sided) and **$p = 0.004270$** (one-sided `less`).
   - Query-level paired Wilcoxon test vs `ARM-101-BASE`: **$p = 7.20 \times 10^{-18}$** ($\Delta = +0.0727$, 238 wins for ARM-101 vs 82 for Candidate F).
3. **Forensic Provenance of $p = 0.0122$**: The $0.0122$ figure cited in Stage 3.15 summaries originated as the upper bound of the 95% repository-clustered bootstrap confidence interval (`[-0.2014, -0.0122]`) for Recall@5 in Stage 3.10/3.11. The live exact Wilcoxon $p$-value is $0.008541$.
4. **Resolution**: Candidate F is permanently retired and confirmed **`FORMALLY_INVALIDATED`**.

---

## 6. Authoritative Unified Candidate Leaderboard ($N = 345$)

Recorded in [`research/stage3_18/CANDIDATE_LEADERBOARD.csv`](file:///F:/RepoNeedle/research/stage3_18/CANDIDATE_LEADERBOARD.csv) and [`research/stage3_18/CANDIDATE_QUERY_LEVEL_RESULTS.csv`](file:///F:/RepoNeedle/research/stage3_18/CANDIDATE_QUERY_LEVEL_RESULTS.csv):

| System ID | Role & Status | MRR | Recall@5 | Recall@10 | Recall@20 | Precision@20 | Token BCY@4k | Token BCY@8k | P50 Latency (ms) | P95 Latency (ms) | Mean Index Time (s) | Process RSS (Caddy) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **`BASE-REPOMAP`** | External Reference Leader | **0.2293** | **0.3855** | **0.5275** | **0.6599** | **0.0462** | **0.2185** | **0.3177** | 180.20 | 180.20 | 17.51 | 198.0 MB |
| **`ARM-101-BASE`** | **RepoNeedle Candidate Champion** | **0.2078** | **0.3391** | **0.4493** | **0.5648** | **0.0397** | **0.1840** | **0.2822** | **12.92** | **130.53** | **19.71** | **198.0 MB** |
| **`BASE-BM25`** | Lexical Baseline | 0.1752 | 0.2928 | 0.3942 | 0.4535 | 0.0322 | 0.1538 | 0.2150 | 10.24 | 116.49 | 17.51 | 198.0 MB |
| **`CAND-C`** | Superseded Frozen Candidate | 0.1399 | 0.2319 | 0.3623 | 0.5105 | 0.0355 | 0.1620 | 0.2410 | 28.50 | 561.46 | 17.85 | 198.0 MB |
| **`CAND-F`** | **Formally Invalidated Prototype** | 0.1351 | 0.2290 | 0.3594 | 0.5078 | 0.0358 | 0.1580 | 0.2336 | 32.42 | 566.28 | 19.71 | 198.0 MB |

*Note: Ranking quality (MRR, Recall, Precision) is strictly segregated from context packing quality (BCY). Latency percentiles P50 and P95 are reported without mean conflation.*

---

## 7. Repository-Cluster-Aware Statistical Analysis

Detailed methodology and per-task / per-repository breakdowns are in [`research/stage3_18/STATISTICAL_ANALYSIS.md`](file:///F:/RepoNeedle/research/stage3_18/STATISTICAL_ANALYSIS.md).

### 10,000-Replicate Cluster Bootstrap Summary:
- **`ARM-101-BASE` vs `BASE-BM25`**:
  - MRR Delta: $+0.0326$ ($+18.62\%$), 95% Clustered CI: $[+0.0237, +0.0442]$, $p < 10^{-30}$ (Wilcoxon), $p = 0.0000$ (Cluster Bootstrap).
  - Recall@20 Delta: $+0.1113$ ($+24.54\%$), 95% Clustered CI: $[+0.0734, +0.1692]$, $p = 2.91 \times 10^{-14}$ (Wilcoxon), $p = 0.0000$ (Cluster Bootstrap).
  - **Verdict**: Decisive, statistically significant improvement across all 25 repository clusters.
- **`ARM-101-BASE` vs `BASE-REPOMAP`**:
  - MRR Delta: $-0.0215$ ($-9.37\%$), 95% Clustered CI: $[-0.0732, +0.0177]$, $p = 0.0559$ (Wilcoxon), $p = 0.3182$ (Cluster Bootstrap).
  - **Verdict**: Difference in MRR is **not statistically significant** at the $\alpha = 0.05$ level.
  - Latency: `ARM-101-BASE` operates at $12.92\text{ ms}$ P50 vs $180.20\text{ ms}$ for RepoMap ($>13.9\times$ speedup on pure CPU).
  - Specialized Task Wins: `ARM-101-BASE` outperforms RepoMap on `comment2context` ($0.1984$ vs $0.1590$ MRR) and `edit2ripple` ($0.2654$ vs $0.2344$ MRR).

---

## 8. External ContextBench Gate Status

- Pinned Upstream Revision: `c285579` from `Contextbench/ContextBench`.
- Required Datasets: `full.parquet` (1,136 tasks, SHA-256: `2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8`, 26,102,607 bytes) and `contextbench_verified.parquet` (500 tasks, SHA-256: `e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791`, 9,558,250 bytes).
- Current Intake Status: The files remain missing locally; container network isolation returns `HTTP 403 Forbidden` on Hugging Face direct endpoints.
- External Validation Verdict: **`BLOCKED — OFFICIAL DATA ACQUISITION`**.
- Unofficial mirrors (`Schwerli/ContextBench`) and synthetic Parquet rows remain strictly prohibited.

---

## 9. Stage 3.18 Deliverables Catalog

All required deliverables have been generated, cross-referenced, and verified:

1. [`research/stage3_18/STAGE3_18_REPORT.md`](file:///F:/RepoNeedle/research/stage3_18/STAGE3_18_REPORT.md): Primary forensic audit report.
2. [`research/stage3_18/CANDIDATE_PROVENANCE.md`](file:///F:/RepoNeedle/research/stage3_18/CANDIDATE_PROVENANCE.md): Complete technical provenance ledger for all 5 candidates.
3. [`research/stage3_18/METRIC_RECONCILIATION.md`](file:///F:/RepoNeedle/research/stage3_18/METRIC_RECONCILIATION.md): In-depth root-cause reconciliation of historical discrepancies.
4. [`research/stage3_18/METRIC_RECONCILIATION.csv`](file:///F:/RepoNeedle/research/stage3_18/METRIC_RECONCILIATION.csv): Structured side-by-side reconciliation table.
5. [`research/stage3_18/CANDIDATE_LEADERBOARD.csv`](file:///F:/RepoNeedle/research/stage3_18/CANDIDATE_LEADERBOARD.csv): Standardized 345-query candidate leaderboard.
6. [`research/stage3_18/CANDIDATE_QUERY_LEVEL_RESULTS.csv`](file:///F:/RepoNeedle/research/stage3_18/CANDIDATE_QUERY_LEVEL_RESULTS.csv): 345-query level outputs for all systems.
7. [`research/stage3_18/STATISTICAL_ANALYSIS.md`](file:///F:/RepoNeedle/research/stage3_18/STATISTICAL_ANALYSIS.md): Paired 10,000-replicate repository-cluster-aware bootstrap analysis.
8. [`research/stage3_18/CANDIDATE_F_INVALIDATION_AUDIT.md`](file:///F:/RepoNeedle/research/stage3_18/CANDIDATE_F_INVALIDATION_AUDIT.md): Independent audit of Candidate F's collapse and $p$-value provenance.
9. [`research/stage3_18/EXPERIMENT_REGISTRY.jsonl`](file:///F:/RepoNeedle/research/stage3_18/EXPERIMENT_REGISTRY.jsonl): Stage 3.18 experiment registry (EXP-090 through EXP-096).
10. [`research/stage3_18/DECISION_REPORT.md`](file:///F:/RepoNeedle/research/stage3_18/DECISION_REPORT.md): Formal governance decision report.
11. [`research/stage3_18/REPRODUCE.md`](file:///F:/RepoNeedle/research/stage3_18/REPRODUCE.md): Deterministic copy-pasteable reproduction instructions.
12. [`tests/test_stage3_18_candidate_provenance_and_reconciliation.py`](file:///F:/RepoNeedle/tests/test_stage3_18_candidate_provenance_and_reconciliation.py): Automated test suite.

---

## 10. Final Governance Verdicts

```
================================================================================
CANDIDATE LEADERBOARD VERDICT: RECONCILED — REPRODUCIBLE CANDIDATE LEADERBOARD
CONTEXTBENCH EXTERNAL GATE:    BLOCKED — OFFICIAL DATA ACQUISITION
================================================================================
```

The ARB v2 candidate leaderboard is fully reconciled, reproducible, and mathematically verified. RepoNeedle candidate champion `ARM-101-BASE` stands ready for independent external validation on official ContextBench datasets as soon as external dataset acquisition is completed.
