# RepoNeedle — Phase R5: Multi-Target Retrieval & Diversity Report

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R5 — Function-Level, Change-Aware Code Retrieval  
**Date**: November 2, 2026  
**Status**: Multi-Target Analysis & Trade-Off Evaluation  

---

## 1. Executive Summary

In realistic software engineering workflows, tasks rarely involve a single isolated file. Across the 345 benchmark queries in ARB v2:
- **57.4%** of queries target a single file.
- **32.8%** of queries target 2 files (typically 1 implementation + 1 test).
- **9.8%** of queries target 3 or more files (cross-cutting architectural changes).

Phase R5 investigated **Multi-Target Retrieval** using **Role-Aware Maximum Marginal Relevance (MMR)** to balance relevance, candidate diversity, and secondary-target discovery.

---

## 2. Target Role Taxonomy

To prevent monolithic ranking, candidates are classified into typed functional roles:

| Target Role | Description | Benchmark Proportion | Selection Policy |
| :--- | :--- | :---: | :--- |
| **`PRIMARY_IMPL`** | Core implementation file | 54.2% | Selected first as the semantic anchor |
| **`SUPPORT_IMPL`** | Secondary helper / utility file | 18.5% | Subject to directory saturation penalty |
| **`TEST`** | Companion test harness | 23.4% | Receives role diversity bonus ($1.25\times$) |
| **`CONFIG_BUILD`** | Build manifest / packaging | 2.5% | Promoted if task mentions build/config |
| **`DOCS`** | Public documentation | 1.4% | Kept in tail context unless specifically queried |

---

## 3. Empirical Results: Treatment G (Role-Aware MMR) vs Treatment B (Dense Baseline)

| Split | Metric | Treatment B (R4 Dense) | Treatment G (Multi-Target MMR) | Delta ($\Delta$) | Analysis |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Validation** | **MRR** | **0.3276** | **0.3266** | -0.0010 | Top-1 accuracy preserved |
| | **Hit@1** | **21.67%** | **21.67%** | 0.00% | Exactly 13/60 at Rank 1 |
| | Recall@5 | **0.3625** | 0.3194 | -0.0431 | Diversity shifts positions 2–5 |
| | Recall@10 | **0.4264** | 0.3847 | -0.0417 | Companion test promoted, but co-located impls shifted |
| | Recall@20 | **0.5792** | 0.4694 | -0.1098 | Near-duplicate gold files pushed beyond Rank 20 |
| | Complete Cov | **48.3%** | 36.7% | -11.6% | Co-located golds demoted by directory penalty |
| **Held-Out** | **MRR** | **0.2973** | 0.2887 | -0.0086 | Slight regression on out-of-distribution |
| | Hit@1 | 17.33% | 17.33% | 0.00% | Anchor accuracy invariant |
| | Recall@20 | **0.5978** | 0.5356 | -0.0622 | Directory penalty reduces deep recall |
| **Train** | **MRR** | **0.4568** | 0.4464 | -0.0104 | Anchor precision stable |
| | Recall@20 | **0.8033** | 0.7456 | -0.0577 | Deep candidate dispersion |

---

## 4. Crucial Information Retrieval Finding: The "Co-Located Gold" Trap

The empirical evaluation reveals a profound structural tension between **general diversity** and **multi-file gold truth**:

### 4.1 The Pathology
In real repositories, when a feature touches multiple files, they are frequently **co-located in the same directory**:
- Example: Query modifying command help templates targets:
  1. `clap_builder/src/output/help_template.rs`
  2. `clap_builder/src/output/usage.rs`
- Both files reside in `clap_builder/src/output/`.
- When Role-Aware MMR selects `help_template.rs` at Rank 1, it applies the directory saturation penalty (`dir_counts >= 2 => penalty 0.65x`) to subsequent files in `clap_builder/src/output/`.
- As a consequence, `usage.rs` is penalized for being redundant, dropping from Rank 4 to Rank 24.
- **Outcome**: Validation Recall@20 drops from 57.92% to 46.94%.

### 4.2 Engineering Takeaway for Production
1. **Aggressive MMR diversity is counter-productive when benchmark gold labels include co-located siblings.**
2. **Selective Diversity**: Diversity penalties must only apply across *dissimilar roles* (e.g., suppressing multiple documentation files or duplicate build manifests), but must NEVER penalize same-directory source files unless token overlap exceeds 90%.
3. MMR is valuable for context packing to eliminate literal code duplicate windows, but should not be used as an aggressive candidate ranker during top-20 retrieval.

