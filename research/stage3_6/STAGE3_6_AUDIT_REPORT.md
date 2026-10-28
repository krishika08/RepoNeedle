# REPONEEDLE STAGE 3.6: AUTHORITATIVE AUDIT & REPRODUCIBILITY REPORT

**Audit Date**: October 2026  
**Document ID**: `STAGE3.6-AUDIT-001`  
**Git Workspace**: `F:\RepoNeedle`  
**Git Branch**: `research-program`  
**Committed HEAD**: `fcab83b`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e00425`)  
**Frozen Candidate Freeze Tag**: `stage3-candidate-freeze` (`cd7f3b0`)  
**Independent Validation Status**: **`BLOCKED / PRELIMINARY`** (Official ContextBench network download blocked by environment boundary)  

---

## 1. EXECUTIVE SUMMARY & DEFINITIVE VERDICT

This report constitutes the authoritative audit and replication of Stage 3.5 claims.
We explicitly examine whether **Candidate F (EXP-CAND-F-POLYGLOT-DIFF)** is genuinely superior to **frozen Candidate C**, **internal BM25 (EXP-016)**, and reference **RepoMap** under one unified, reproducible evaluation contract across all $N=345$ positive ARB v2 queries.

### The Verdict: Candidate F is NOT a Proven Winner Over RepoMap
In accordance with preregistered research-verification rules:
1. **Candidate F vs. Candidate C**:
   - On the full $N=345$ benchmark, Candidate F demonstrates **no statistically significant overall advantage** over Candidate C:
     - MRR: $0.1351$ vs. $0.1399$ (Mean difference: $-0.0048$, $95\%\text{ CI}: [-0.0153, +0.0076]$, Wilcoxon $p = 0.1164$).
     - Recall@20: $0.5078$ vs. $0.5105$ (Mean difference: $-0.0027$, $95\%\text{ CI}: [-0.0227, +0.0230]$, Wilcoxon $p = 0.8473$).
   - Candidate F wins on 75 queries, loses on 131 queries, and ties on 139 queries against Candidate C.
2. **RepoMap Retains Decisive Superiority**:
   - Authoritative Aider RepoMap achieves **$0.2293$ MRR** and **$0.6599$ Recall@20**, holding a statistically significant $+0.0942$ MRR advantage ($p < 0.0001$) and $+0.1520$ Recall@20 lead ($p < 0.0001$) over Candidate F.
   - The Stage 3.5 claim that Candidate F achieved MRR $0.2152$ versus RepoMap $0.2140$ was based on synthetic 2-file ripgrep fixtures containing hardcoded string bypasses. Under canonical evaluation, that claim is **retracted**.
3. **Candidate F's Genuine Advantage is Operational Latency**:
   - Median warm query latency: **$32.42\text{ ms}$** (Candidate F) vs. **$180.20\text{ ms}$** (RepoMap).
   - Zero LLM and zero tree-sitter dependencies, operating within $<180\text{ MB}$ of process memory.

---

## 2. RECONCILED SYSTEM SUMMARY (ARB v2 POSITIVE BENCHMARK, N=345)

All four systems evaluated under the identical evaluation harness (`research/stage3_6/CANONICAL_FULL_CORPUS_RESULTS.csv`):

| System ID | Architectural Description | MRR | Recall@5 | Recall@10 | Recall@20 | Precision@5 | BCY@8k | Latency (p50) | Latency (p95) | Process RSS (Peak) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BASE-BM25** | Pure BM25 Keyword Baseline (EXP-016) | 0.1735 | 0.1986 | 0.3118 | 0.4549 | 0.0568 | 0.0493 | 20.85 ms | 478.58 ms | 145.2 MB |
| **CAND-C** | Static Hybrid + Doc Filter (0.5x) | 0.1399 | 0.2111 | 0.3196 | 0.5105 | 0.0557 | 0.0188 | 31.50 ms | 561.46 ms | 168.5 MB |
| **CAND-F** | Candidate C + Polyglot Graph Diffusion | 0.1351 | 0.1824 | 0.3316 | 0.5078 | 0.0504 | 0.0159 | 32.42 ms | 566.28 ms | 179.4 MB |
| **BASE-REPOMAP**| Aider AST PageRank Reference | **0.2293** | **0.3337** | **0.5110** | **0.6599** | **0.0186** | **0.0652** | 180.20 ms | 180.20 ms | 265.0 MB |

---

## 3. METRIC DISCREPANCIES RECONCILED (PHASE 2 AUDIT)

Forensic examination of Stage 3.4 and Stage 3.5 code resolved the reported metric discrepancies:
1. **Binary Hit@20 vs Multi-Target Fractional Recall**:
   - Stage 3.5 calculated binary Hit@20 ($170/345 = 0.4928$ for BM25 and $196/345 = 0.5681$ for RepoMap), mislabeled them as fractional recall, and compared them against Candidate C's fractional recall ($0.5516$).
   - Official ARB v2 metric implementation (`sample_metrics`) calculates multi-target fractional recall. Under the official contract, BM25 Recall@20 is **0.4549** and RepoMap Recall@20 is **0.6599**.
2. **Excise of Synthetic Bypass Rules**:
   - Stage 3.5 `reponeedle/core/graph.py` contained hardcoded strings: `"search.rs", "standard.rs"` and `("core" in my_crate and "printer" in o_crate)` specifically targeting the synthetic 2-file `BurntSushi/ripgrep` fixture.
   - These rules were completely excised in Stage 3.6. Genuine cross-crate resolution strictly uses `Cargo.toml` path dependencies and module imports.

---

## 4. PAIRED STATISTICAL ANALYSIS (PHASE 4 AUDIT)

Paired bootstrap confidence intervals ($B=10,000$ iterations, seed=42) and Wilcoxon signed-rank tests:

| Comparison | Metric | Mean Difference | 95% Query Bootstrap CI | 95% Repo Clustered CI | Wins / Ties / Losses | Wilcoxon p-value | Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **CAND-F vs. CAND-C** | MRR | -0.0048 | [-0.0153, +0.0076] | [-0.0175, +0.0078] | 75 / 139 / 131 | 0.1164 | Not Significant |
| **CAND-F vs. CAND-C** | Recall@20 | -0.0027 | [-0.0227, +0.0230] | [-0.0289, +0.0271] | 75 / 164 / 106 | 0.8473 | Not Significant |
| **CAND-F vs. RepoMap**| MRR | -0.0942 | [-0.1145, -0.0734] | [-0.1251, -0.0632] | 89 / 18 / 238 | < 0.0001 | **RepoMap Superior** |
| **CAND-F vs. RepoMap**| Recall@20 | -0.1520 | [-0.1772, -0.1264] | [-0.1984, -0.1085] | 78 / 38 / 229 | < 0.0001 | **RepoMap Superior** |
| **CAND-F vs. BM25** | MRR | -0.0384 | [-0.0544, -0.0221] | [-0.0621, -0.0142] | 118 / 26 / 201 | 0.0002 | **BM25 Superior MRR** |
| **CAND-F vs. BM25** | Recall@20 | +0.0528 | [+0.0305, +0.0754] | [+0.0184, +0.0882] | 165 / 42 / 138 | 0.0018 | **CAND-F Superior Recall**|

---

## 5. PER-TASK BREAKDOWN

| Task Track | Query Count | BASE-BM25 MRR | CAND-C MRR | CAND-F MRR | BASE-REPOMAP MRR |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `code2test` | 91 | 0.0685 | 0.0638 | 0.0601 | **0.1632** |
| `comment2context` | 89 | 0.1657 | 0.1176 | 0.1240 | **0.2031** |
| `trace2code` | 98 | 0.2487 | 0.2397 | 0.2265 | **0.2984** |
| `edit2ripple` | 67 | 0.2452 | 0.1356 | 0.1284 | **0.2520** |

---

## 6. INDEPENDENT VALIDATION STATUS (PHASE 7 AUDIT)

* **Status**: **`BLOCKED / PRELIMINARY`**
* **External Blocker**: Network access to Hugging Face (`Contextbench/ContextBench`) and GitHub is strictly isolated under environment execution policy.
* **Integrity Commitment**: ARB v2 is recognized as a development benchmark, NOT an independent test set. No synthetic data has been relabeled as ContextBench.

---

## 7. DELIVERABLE ARTIFACT PATHS

All required Stage 3.6 deliverables are committed and verifiable:
1. `research/stage3_6/STAGE3_6_AUDIT_REPORT.md` (this report)
2. `research/stage3_6/METRIC_DISCREPANCY_TABLE.csv`
3. `research/stage3_6/CANONICAL_FULL_CORPUS_RESULTS.csv`
4. `research/stage3_6/PER_QUERY_PAIRED_RESULTS.csv`
5. `research/stage3_6/PAIRED_STATISTICAL_TESTS.csv`
6. `research/stage3_6/PER_TASK_RESULTS.csv`
7. `research/stage3_6/RUNTIME_MEMORY_RESULTS.csv`
8. `research/stage3_6/EXPERIMENT_REGISTRY.jsonl`
9. `research/stage3_6/REPRODUCE.md`
