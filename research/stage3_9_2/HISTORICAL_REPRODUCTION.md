# RepoNeedle Stage 3.9.2: Historical Reproduction & Protocol Isolation Audit

**Document ID**: `STAGE3.9.2-REPRO-001`  
**Date**: October 2026  
**Auditor**: Independent Reproducibility & Benchmark Integrity Auditor  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Target Revisions**:
- Historical Revision: `4f78cc3658dfb5e338a5458579d38d5d7ef416e8` (Stage 3.5 Anchor)
- Forensic Audit Revision: `cbe6c49` (Stage 3.6 Diagnostic Baseline)
- Canonical Audited Revision: `b7cf35bc6ebfebc7e6c6cc5df122118bdb1c3bbc` (Current HEAD)

---

## 1. Executive Summary

This deliverable provides the forensic execution audit reproducing the Stage 3.5 evaluation workflows and isolating each implementation difference against the Stage 3.9.1 canonical pipeline.

All evaluations were executed using identical query inputs ($N = 345$ positive queries across 25 repositories, 218 snapshots) and matched corpus manifests from `external/agent-retrieval-bench`.

---

## 2. Historical Reproduction Ledger by System

The reproduction table compares the recorded Stage 3.5 values, the re-executed historical procedure, and the canonical Stage 3.9.1 results:

| System ID | Historical Stage 3.5 Value | Reproduced Stage 3.5 Workflow | Stage 3.9.1 Canonical Value | Reproduction Delta | Root Cause & Reproduction Finding | Status |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **`BASE-BM25`** | 0.1705 | 0.1705 | **0.1768** | +0.0063 | **Exact match on historical procedure**: Reading `research/stage2_results/PER_SAMPLE_ABLATIONS.jsonl` under `EXP-016` yields exactly `0.1705`. Live execution of decoupled BM25 yields `0.1768`. | **REPRODUCED** |
| **`BASE-REPOMAP`** | 0.2140 | 0.2140 | **0.2293** | +0.0153 | **Exact match on historical artifact**: Inspecting `research/stage3_5/evaluate_graph_retrieval.py:278` confirms that `0.2140` was hardcoded as a static string dictionary. Live execution of `9e4d689` yields `0.2293`. | **REPRODUCED (STATIC)** |
| **`CAND-C`** | 0.2040 | 0.2040 | **0.1401** | -0.0639 | **Exact match on filtered pool**: On `v2_selective_mixed` chunk pools with candidate restrictions, CAND-C yields `0.2040`. On unconstrained full repository universe, it collapses to `0.1401`. | **REPRODUCED** |
| **`CAND-F`** | 0.2078 (0.2152) | 0.2078 (0.2152) | **0.1338** | -0.0740 | **Exact match on shortcut-enabled workflow**: With ripgrep string matching bypass and filtered pools, CAND-F produces `0.2078` (table) / `0.2152` (report). Live unconstrained execution without bypass collapses to `0.1338`. | **REPRODUCED (INVALIDATED)** |
| **`CAND-CASCADE`** | N/A | N/A | **0.1905** | +0.0137 vs BM25 | **Independently recomputed**: Full live execution on all 345 queries reproduces `0.1905 MRR`, `0.5503 Recall@20`, and `0.0493 BCY@8k`. | **CANONICAL WINNER** |

---

## 3. Matched Common Harness Isolation Experiments

To isolate implementation variables, four controlled experiments were conducted using matched query sets and common evaluation harnesses:

### Experiment 1: BM25 Symbol Decoupling Isolation
- **Common Inputs**: 345 positive ARB v2 queries across 218 snapshots.
- **Variable**: Document length normalization formula in `reponeedle/core/lexical.py`.
- **Harness**: `agent_retrieval_bench.baseline.sample_metrics`.
- **Results**:
  - `decouple_symbols = False` (Stage 3.6 Coupled):
    $$\text{MRR} = 0.1735, \quad \text{Recall@20} = 0.4549, \quad \text{Hit@20} = 0.5362$$
  - `decouple_symbols = True` (Stage 3.9.1 Decoupled):
    $$\text{MRR} = 0.1768, \quad \text{Recall@20} = 0.4622, \quad \text{Hit@20} = 0.5391$$
- **Finding**: Decoupling AST symbols from the document length denominator improves MRR by $+0.0033$ on full repositories because it prevents rich code files declaring numerous symbols from being penalized by the BM25Okapi length ratio $|d|/\text{avgdl}$.

### Experiment 2: Candidate Universe Isolation (Filtered vs. Unconstrained)
- **Common Inputs**: 64 `v2_code2test` queries.
- **Variable**: Candidate universe passed to ranker.
  - Option A: Filtered candidate pool (`tests_only` filter, ~50 test files per repo).
  - Option B: Full unconstrained repository universe (~1,000 to 5,000 files per repo).
- **Results**:
  - Option A (Filtered): Candidate C achieved $\text{MRR} = 0.2241$.
  - Option B (Unconstrained): Candidate C achieved $\text{MRR} = 0.0969$.
- **Finding**: Task-specific candidate pre-filtering artfully sheltered Candidate C from thousands of repository distractors. On realistic unconstrained repositories, dense semantic vectors and static PageRank hub nodes introduce severe false-positive matches.

### Experiment 3: Ripgrep Target Diagnostic Shortcut Excision
- **Common Inputs**: Single `BurntSushi/ripgrep` failure fixture (`crates/printer/src/standard.rs` $\to$ `crates/core/search.rs`).
- **Variable**: Presence of hardcoded string matching in `reponeedle/core/graph.py`.
- **Results**:
  - With Stage 3.5 hardcoded string bypass: CAND-F MRR $= 1.0000$.
  - Without hardcoded bypass (Stage 3.6 fail-closed test): CAND-F MRR $= 0.0000$.
- **Finding**: The Stage 3.5 ripgrep win was an artifact of targeted diagnostic code. Removing the bypass exposed that cross-crate diffusion without true AST linkage does not discover the target.

### Experiment 4: Diffusion Hub Dilution vs. Degree Normalization
- **Common Inputs**: 345 positive ARB v2 queries.
- **Variable**: Diffusion formulation in `reponeedle/core/cascade.py`.
  - Option A: Unnormalized diffusion (Stage 3.5 CAND-F formulation).
  - Option B: Degree-normalized diffusion with top-3 rank fencing (CAND-CASCADE formulation).
- **Results**:
  - Option A (Unnormalized): 70 queries suffered early-rank demotions (`cand_f_early_demotion_flag = 1`), reducing MRR to $0.1338$.
  - Option B (Degree-Normalized + Fenced): 0 early-rank demotions, raising MRR to $0.1905$.
- **Finding**: Locking the top-3 ranks to BM25 and normalizing diffusion weights by node out-degree completely eliminates supernode dilution.

---

## 4. Query-Level Rank Difference Ledger

The file [`PER_QUERY_CROSS_STAGE_COMPARISON.csv`](file:///F:/RepoNeedle/research/stage3_9_2/PER_QUERY_CROSS_STAGE_COMPARISON.csv) records per-query reciprocal rank and recall across all stages. A representative sample demonstrating these mechanisms:

| Query ID | Repository | Task Track | Stage 2 BM25 MRR | Stage 3.6 Coupled BM25 MRR | Stage 3.9.1 Decoupled BM25 MRR | Stage 3.9.1 CAND-F MRR | Stage 3.9.1 CAND-CASCADE MRR | Forensic Mechanism |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `597f32e9b482...` | `clap-rs/clap` | `code2test` | 0.0092 | 0.0104 | 0.0105 | 0.0096 | 0.0105 | Decoupled BM25 promotes gold target by 1 rank (rank 96 $\to$ 95). |
| `01323034afde...` | `astral-sh/ruff` | `comment2context` | 0.1250 | 0.1667 | 0.1667 | 0.0833 | 0.1667 | CAND-F demotes gold target from rank 6 to 12; CASCADE restores to rank 6. |
| `4b7e8841a31c...` | `tokio-rs/tokio` | `trace2code` | 0.2000 | 0.2000 | 0.2500 | 0.1000 | 0.2500 | Supernode dilution demotes gold target in CAND-F; CASCADE protects top ranks. |
| `a8f9024c0891...` | `etcd-io/etcd` | `edit2ripple` | 0.3333 | 0.3333 | 0.3333 | 0.1111 | 0.5000 | CASCADE graph expansion at rank 4+ promotes ripple dependency to rank 2. |

---

## 5. Summary of Reproduction Status

All historical Stage 3.5 and Stage 3.6 results are **100% accounted for and reproducible from retained artifacts**.
The historical discrepancies are not unexplained anomalies; they are the mathematical consequence of moving from synthetic/filtered environments to an unconstrained, fail-closed canonical evaluation protocol.
