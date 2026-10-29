# RepoNeedle Stage 3.7: Comprehensive Metric Discrepancy Ledger

**Document ID**: `STAGE3-7-LEDGER-001`  
**Date**: October 2026  
**Stage**: Stage 3.7 — Canonical Evaluation Reconciliation and Research Integrity Gate  
**Branch**: `research-program`  
**Base Commit**: `9a9944a`  

---

## 1. Executive Summary

This ledger provides complete forensic accounting of all historical retrieval performance claims across Stages 1 through 3.6. Every claimed metric value is documented with its original source, candidate pool boundary, metric definition, canonical replacement, and authoritative comparability verdict.

### Formal Classification Taxonomy:
- `REPRODUCED_CANONICAL`: The value is verified and reproducible under the official, unconstrained full-corpus evaluation contract.
- `REPRODUCED_LEGACY_PROTOCOL`: The value is reproducible only when applying legacy candidate pool pre-filtering or chunk-level evaluations.
- `NON_COMPARABLE`: The value reflects a different metric definition (e.g. Binary Hit@K vs Multi-Target Fractional Recall) or different corpus denominator.
- `INVALIDATED`: The claim relied on synthetic micro-fixtures, hardcoded string bypasses, or unmeasured static constants.
- `NOT_REPRODUCIBLE`: The result cannot be replicated from committed code or data.
- `BLOCKED_DATA_ACCESS`: Evaluation cannot proceed due to external network policy constraints.

---

## 2. Discrepancy & Reconciliation Ledger

| Claim ID | Configuration | Metric Claimed | Historical Value | Source Report & Evaluator | Candidate Pool Scope | Exact Metric Definition | Canonical Value | Comparability Verdict | Forensic Explanation & Resolution |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- | :---: | :--- | :--- |
| **DISC-01** | `BASE-BM25` | Recall@20 | **0.4467** | Stage 3.4 Baseline / `evaluate_graph_retrieval.py` | Chunk-filtered corpus | Multi-target fractional recall | **0.4549** | `REPRODUCED_LEGACY_PROTOCOL` | Evaluated on ARB chunk subsets. When evaluated across the complete full repository corpus, canonical fractional recall is 0.4549. |
| **DISC-02** | `BASE-BM25` | Recall@20 | **0.4928** | Stage 3.5 Decision Report Table 1.2 | Full positive corpus ($N=345$) | Binary Hit@20 ($170/345 = 0.4928$) | **0.4549** | `NON_COMPARABLE` | Evaluated binary hit rate (at least one gold target in top 20) and mislabeled it as fractional recall. |
| **DISC-03** | `BASE-REPOMAP` | Recall@20 | **0.6306** | Stage 3.4 Report / `evaluate_graph_retrieval.py` | Older v1.1 reference subset | Multi-target fractional recall | **0.6599** | `REPRODUCED_LEGACY_PROTOCOL` | Static paper reference from v1.1 evaluation. Live evaluation of version-pinned official RepoMap (`9e4d689`) achieves 0.6599 on full positive corpus. |
| **DISC-04** | `BASE-REPOMAP` | Recall@20 | **0.5681** | Stage 3.5 Decision Report Table 1.2 | Full positive corpus ($N=345$) | Binary Hit@20 ($196/345 = 0.5681$) | **0.6599** | `NON_COMPARABLE` | Computed binary hit rate and mislabeled as fractional recall. Pinned RepoMap achieves 0.6599 fractional recall and 0.7478 binary hit rate. |
| **DISC-05** | `CAND-C` | Recall@20 | **0.5516** | Stage 3.4 Report & Stage 3.5 Table 1.2 | Candidate-restricted pools (`tests_only`, `code_only`) | Multi-target fractional recall | **0.5105** | `NON_COMPARABLE` | Evaluated on restricted candidate pools using pre-computed Stage 2 lookup dictionaries. Under unconstrained full corpus, true fractional recall is 0.5105. |
| **DISC-06** | `BASE-REPOMAP` | MRR | **0.2140** | Stage 3.5 Report & `evaluate_graph_retrieval.py:278` | Unmeasured paper reference | Mean Reciprocal Rank (Top 20) | **0.2293** | `INVALIDATED` | Unmeasured static constant hardcoded in evaluation script. Pinned official RepoMap (`9e4d689`) achieves 0.2293 MRR. |
| **DISC-07** | `CAND-C` | MRR | **0.2040** | Stage 3.4 Candidate Freeze (`cd7f3b0`) | Candidate-restricted pools | Mean Reciprocal Rank (Top 20) | **0.1399** | `NON_COMPARABLE` | Candidate pools pre-filtered candidates. When evaluated on unconstrained full repository corpus, Candidate C drops to 0.1399 MRR. |
| **DISC-08** | `CAND-F` | MRR | **0.2152** | Stage 3.5 Decision Report (`4f78cc3`) | Synthetic 2-file micro-fixtures | Mean Reciprocal Rank (Top 20) | **0.1351** | `INVALIDATED` | Relied on hardcoded string bypasses in `graph.py` and uncoupled Stage 2 lookups. End-to-end full corpus execution collapses to 0.1351 MRR. |
| **DISC-09** | `CAND-F` | Recall@20 | **0.5652** | Stage 3.5 Decision Report (`4f78cc3`) | Full positive corpus ($N=345$) | Binary Hit@20 ($195/345 = 0.5652$) | **0.5078** | `INVALIDATED` | Mislabeled binary hit rate as fractional recall. True full-corpus fractional recall is 0.5078. |
| **DISC-10** | `ContextBench` | All Metrics | **Pending** | Hugging Face Hub `Contextbench/ContextBench` | Independent benchmark | Documented official metrics | **Pending** | `BLOCKED_DATA_ACCESS` | Outbound network blocked by sandbox environment (HTTP 403 Forbidden). Fail-closed gates enforced. |

---

## 3. Resolution of the Candidate C MRR Drop ($0.2040 \to 0.1399$)

A key question raised in Stage 3.7 is the resolution of Candidate C's MRR drop:
- Stage 3.4 Candidate C MRR: `0.2040`
- Stage 3.6/3.7 Canonical Candidate C MRR: `0.1399`
- Total drop: $\mathbf{-0.0641}$

### Per-Task Breakdown Analysis:
| Task Track | Sample Count ($N$) | Stage 3.4 Reported MRR (Restricted Pool) | Canonical MRR (Full Corpus) | Task Delta ($\Delta$) | Root Cause Mechanism |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `code2test` | 106 | 0.1073 | **0.0638** | $-0.0435$ | In Stage 3.4, candidates were pre-filtered to `tests_only` (~50 test files). On full corpus (~1,000 files), BM25 matches code files, tutorials, and examples ahead of tests. |
| `comment2context`| 80 | 0.2036 | **0.1176** | $-0.0860$ | In Stage 3.4, pre-filtered to files containing docstrings. Full corpus introduces hundreds of distractors. |
| `edit2ripple` | 58 | 0.2510 | **0.1356** | $-0.1154$ | In Stage 3.4, ripples were pre-selected by 1-hop AST callers. Full corpus requires unrestricted multi-hop search. |
| `trace2code` | 101 | 0.2787 | **0.2397** | $-0.0390$ | Pre-filtered to `code_only`. Full corpus introduces stack frame name collisions. |
| **Overall** | **345** | **0.2040** | **0.1399** | $\mathbf{-0.0641}$ | **Candidate pool restriction accounted for 100% of the discrepancy.** |

When Candidate F is evaluated on the exact same unconstrained full corpus, it achieves **0.1351** MRR, which is $-0.0048$ below Candidate C ($0.1399$).
