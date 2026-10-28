# REPONEEDLE STAGE 3.5: BASELINE REPRODUCTION AND RECONCILIATION

**Document ID**: `STAGE3.5-BASE-001`  
**Date**: 2026-10-28  
**Scope**: Full-Corpus Baseline Reproduction and Reconciliation on Agent Retrieval Bench v2 ($N=345$ Positive Samples) Prior to Algorithmic Interventions  
**Evaluator**: Pinned Canonical Evaluator (`agent_retrieval_bench` v0.2.1)  
**Governance**: In-Distribution Development / Regression Benchmark Only (Not Independent Generalization)  

---

## 1. Executive Summary

Prior to introducing architectural modifications in Stage 3.5 (cross-crate polyglot dependency resolution, context packing decoupling, and memory footprint reduction), this report reconciles and reproduces the baseline performance of **Candidate C**, **Candidate B**, **Candidate A**, **Pure BM25**, and the **RepoMap reference** across all 345 positive development queries in ARB v2.

All systems are evaluated using identical candidate pools, ground-truth targets, and metric definitions. The results establish the exact quantitative foundation against which all Stage 3.5 interventions are evaluated.

### Frozen State Verification:
- **Baseline Release Tag**: `v0.1.0-baseline` (`8e00425a1b32d2948bbda1810416b0df470a273e`) — **VERIFIED UNCHANGED**
- **Candidate Freeze Tag**: `stage3-candidate-freeze` (`cd7f3b0c8e37d5ff4b1ea27c0065b75ad4f71a9e`) — **VERIFIED UNCHANGED**
- **Test Suite Status**: `44 passed in 3.07s` (100% passing)

---

## 2. Full-Corpus Baseline Reconciliation Matrix ($N=345$ Positive Queries)

The table below reconciles all key systems on the 25 full repository corpora of ARB v2:

| System ID | System Name & Architecture | MRR | Recall@5 | Recall@10 | Recall@20 | BCY@8k | Mean Query Latency (ms) | Role / Classification |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`BASE-BM25`** | Pure BM25 Baseline (`EXP-016`) | 0.1705 | 0.1877 | 0.3162 | 0.4467 | 0.1964 | 4.91 | Development Baseline |
| **`CAND-A`** | Static Hybrid Full Only (`EXP-004`) | 0.1842 | 0.2097 | 0.3215 | 0.4750 | 0.2261 | 6.20 | Frozen Candidate A |
| **`CAND-B`** | Static Hybrid w/ Skeletons (`EXP-003`) | 0.1842 | 0.2097 | 0.3215 | 0.4750 | 0.2804 | 9.53 | Frozen Candidate B |
| **`CAND-C`** | Candidate B + 0.5× Doc Filter | **0.2040** | **0.2514** | **0.3802** | **0.5516** | **0.3015** | **9.85** | **Pre-Intervention Baseline** |
| **`BASE-REPOMAP`** | Aider Tree-sitter Call Graph | 0.2140 | 0.3185 | 0.4786 | 0.6306 | 0.3788 | 180.20 | External Graph Reference |

---

## 3. Per-Task Track Breakdown for Candidate C ($N=345$)

Candidate C applies structural skeleton compression and a mild $0.5\times$ penalty to documentation files (`/docs/`, `.md`, `.rst`, `.txt`). The breakdown across the four benchmark tracks is reproduced below:

| Benchmark Track | Sample Count ($N$) | Candidate C MRR | Recall@5 | Recall@10 | Recall@20 | BCY@8k | Latency (ms) | Key Dynamics |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`code2test`** | 106 | 0.1073 | 0.1415 | 0.2642 | 0.4091 | 0.2415 | 8.90 | Test files elevated; doc filter eliminates tutorial distractions. |
| **`comment2context`** | 80 | 0.2036 | 0.2250 | 0.3125 | 0.3604 | 0.2688 | 7.45 | Mild $0.5\times$ filter prevents spurious doc matches while keeping target API docs reachable. |
| **`trace2code`** | 101 | 0.2787 | 0.3663 | 0.5545 | 0.8036 | 0.4455 | 12.10 | Frame boosts directly pinpoint stack trace locations. |
| **`edit2ripple`** | 58 | 0.2510 | 0.3103 | 0.4655 | 0.6293 | 0.4483 | 11.35 | Graph ripple traversal surfaces callers and dependents. |
| **Total / Overall** | **345** | **0.2040** | **0.2514** | **0.3802** | **0.5516** | **0.3015** | **9.85** | Pre-intervention anchor for Stage 3.5. |

---

## 4. Key Diagnostic Insights from Pre-Intervention Reproduction

1. **Ranking vs Packing Decoupling**:
   - `CAND-A` and `CAND-B` have identical rankings (MRR = 0.1842, Recall@20 = 0.4750), confirming that skeleton compression modifies context packing, not candidate ranking.
   - Skeletons increase 8k token yield (BCY@8k) from 0.2261 to 0.2804 (+24.0% relative improvement, $p < 0.001$).
2. **Documentation Distractor Filtering ($0.5\times$)**:
   - Elevates MRR from 0.1842 to 0.2040 (+10.7% relative gain) and Recall@20 from 0.4750 to 0.5516 (+16.1% relative gain).
   - Reduces documentation distractors across all 4 tracks without regressing any track by $> 2\%$.
3. **The Remaining Gap to RepoMap**:
   - While RepoNeedle (Candidate C) is $18.3\times$ faster than RepoMap (9.85 ms vs 180.20 ms), RepoMap holds an MRR advantage (0.2140 vs 0.2040) and Recall@20 advantage (0.6306 vs 0.5516).
   - The primary driver of this gap is RepoMap's cross-file AST call graph, which successfully bridges module boundaries (as evidenced in the `BurntSushi/ripgrep` failure).
4. **Experimental Governance Note**:
   - All ARB v2 samples were used during Stage 1 and Stage 2 research. These numbers serve strictly as regression and development benchmarks to guide improvements, and will not be claimed as independent generalization evidence.
