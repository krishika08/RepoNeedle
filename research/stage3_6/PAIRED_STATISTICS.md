# REPONEEDLE STAGE 3.6: PAIRED STATISTICAL ANALYSIS & AUDIT REPORT

**Document ID**: `STAGE3.6-STAT-001`  
**Date**: October 2026  
**Benchmark Scope**: ARB v2 Full Positive Benchmark ($N=345$) across 4 Systems  
**Statistical Protocol**: 10,000 Clustered Bootstrap Resamples (Cluster Unit: Repository Environment, Seed: 42) + Wilcoxon Signed-Rank Test  

---

## 1. COMPREHENSIVE BENCHMARK SUMMARY (N=345 POSITIVE QUERIES)

| System ID | MRR | Recall@1 | Recall@5 | Recall@10 | Recall@20 | Precision@5 | Precision@10 | Precision@20 | BCY@4k | BCY@8k | BCY@16k | Mean Latency (ms) | Median Latency (ms) | p95 Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BASE-BM25`** | 0.1735 | 0.0464 | 0.1986 | 0.3118 | 0.4549 | 0.0568 | 0.0441 | 0.0322 | 0.0464 | 0.0493 | 0.0633 | 109.79 ms | 20.85 ms | 478.58 ms |
| **`CAND-C`** | 0.1399 | 0.0159 | 0.2111 | 0.3196 | 0.5105 | 0.0557 | 0.0441 | 0.0355 | 0.0159 | 0.0188 | 0.0406 | 132.30 ms | 31.50 ms | 561.46 ms |
| **`CAND-F`** | 0.1351 | 0.0116 | 0.1824 | 0.3316 | 0.5078 | 0.0504 | 0.0452 | 0.0358 | 0.0116 | 0.0159 | 0.0329 | 133.33 ms | 32.42 ms | 566.28 ms |
| **`BASE-REPOMAP`** | 0.2293 | 0.0725 | 0.3337 | 0.5110 | 0.6599 | 0.0186 | 0.0139 | 0.0087 | 0.0326 | 0.0652 | 0.0732 | 180.20 ms | 180.20 ms | 180.20 ms |

---

## 2. PAIRED COMPARISONS & HYPOTHESIS TESTING

### 2.1 Candidate C vs. Candidate F

- **Mean Difference in MRR (Target - Base)**: **-0.0048**
  - **95% Clustered Bootstrap CI**: `[-0.0153, +0.0076]`
  - **Wilcoxon Signed-Rank Test**: $p = 0.1164$ (Not Statistically Significant ($p \ge 0.05$))
  - **Paired $t$-test**: $t = -1.386$, $p = 0.1667$
  - **Query-Level Outcome**: **75 Wins, 141 Ties, 129 Losses**

- **Mean Difference in Recall@20 (Target - Base)**: **-0.0027**
  - **95% Clustered Bootstrap CI**: `[-0.0227, +0.0230]`
  - **Wilcoxon Signed-Rank Test**: $p = 0.8473$ (Not Statistically Significant ($p \ge 0.05$))
  - **Paired $t$-test**: $t = -0.294$, $p = 0.7687$
  - **Query-Level Outcome**: **11 Wins, 324 Ties, 10 Losses**

- **Mean Difference in Token Yield (BCY@8k)**: **-0.0029**
  - **95% Clustered Bootstrap CI**: `[-0.0076, +0.0025]`
  - **Query-Level Outcome**: **1 Wins, 342 Ties, 2 Losses**

### 2.2 BM25 Baseline vs. Candidate F

- **Mean Difference in MRR (Target - Base)**: **-0.0384**
  - **95% Clustered Bootstrap CI**: `[-0.0884, +0.0300]`
  - **Wilcoxon Signed-Rank Test**: $p = 0.0483$ (Statistically Significant ($p < 0.05$))
  - **Paired $t$-test**: $t = -3.425$, $p = 0.0007$
  - **Query-Level Outcome**: **166 Wins, 26 Ties, 153 Losses**

- **Mean Difference in Recall@20 (Target - Base)**: **+0.0529**
  - **95% Clustered Bootstrap CI**: `[-0.0091, +0.1689]`
  - **Wilcoxon Signed-Rank Test**: $p = 0.0023$ (Statistically Significant ($p < 0.05$))
  - **Paired $t$-test**: $t = 3.030$, $p = 0.0026$
  - **Query-Level Outcome**: **40 Wins, 285 Ties, 20 Losses**

- **Mean Difference in Token Yield (BCY@8k)**: **-0.0333**
  - **95% Clustered Bootstrap CI**: `[-0.0645, -0.0010]`
  - **Query-Level Outcome**: **5 Wins, 322 Ties, 18 Losses**

### 2.3 RepoMap Baseline vs. Candidate F

- **Mean Difference in MRR (Target - Base)**: **-0.0942**
  - **95% Clustered Bootstrap CI**: `[-0.1171, -0.0574]`
  - **Wilcoxon Signed-Rank Test**: $p = 0.0000$ (Statistically Significant ($p < 0.05$))
  - **Paired $t$-test**: $t = -6.780$, $p = 0.0000$
  - **Query-Level Outcome**: **99 Wins, 20 Ties, 226 Losses**

- **Mean Difference in Recall@20 (Target - Base)**: **-0.1520**
  - **95% Clustered Bootstrap CI**: `[-0.2016, -0.1076]`
  - **Wilcoxon Signed-Rank Test**: $p = 0.0000$ (Statistically Significant ($p < 0.05$))
  - **Paired $t$-test**: $t = -6.332$, $p = 0.0000$
  - **Query-Level Outcome**: **28 Wins, 227 Ties, 90 Losses**

- **Mean Difference in Token Yield (BCY@8k)**: **-0.0493**
  - **95% Clustered Bootstrap CI**: `[-0.0717, -0.0287]`
  - **Query-Level Outcome**: **5 Wins, 315 Ties, 25 Losses**

---

## 3. PER-TASK BREAKDOWN

| Task Type | Sample Count | System ID | MRR | Recall@20 | BCY@8k |
| :--- | :---: | :--- | :---: | :---: | :---: |
| `code2test` | 106 | `BASE-BM25` | 0.0685 | 0.3116 | 0.0031 |
| `code2test` | 106 | `CAND-C` | 0.0638 | 0.3478 | 0.0031 |
| `code2test` | 106 | `CAND-F` | 0.0601 | 0.3384 | 0.0000 |
| `code2test` | 106 | `BASE-REPOMAP` | 0.2284 | 0.6123 | 0.0975 |
| `comment2context` | 80 | `BASE-BM25` | 0.1657 | 0.3042 | 0.0354 |
| `comment2context` | 80 | `CAND-C` | 0.1176 | 0.3000 | 0.0063 |
| `comment2context` | 80 | `CAND-F` | 0.1240 | 0.3312 | 0.0104 |
| `comment2context` | 80 | `BASE-REPOMAP` | 0.1590 | 0.4937 | 0.0333 |
| `edit2ripple` | 58 | `BASE-BM25` | 0.2452 | 0.5589 | 0.0172 |
| `edit2ripple` | 58 | `CAND-C` | 0.1356 | 0.5790 | 0.0000 |
| `edit2ripple` | 58 | `CAND-F` | 0.1284 | 0.5718 | 0.0000 |
| `edit2ripple` | 58 | `BASE-REPOMAP` | 0.2344 | 0.6164 | 0.0431 |
| `trace2code` | 101 | `BASE-BM25` | 0.2487 | 0.6650 | 0.1271 |
| `trace2code` | 101 | `CAND-C` | 0.2397 | 0.8086 | 0.0561 |
| `trace2code` | 101 | `CAND-F` | 0.2265 | 0.7888 | 0.0462 |
| `trace2code` | 101 | `BASE-REPOMAP` | 0.2829 | 0.8663 | 0.0693 |

---

## 4. PER-LANGUAGE BREAKDOWN

| Language | Query Count | System ID | MRR | Recall@20 | BCY@8k |
| :--- | :---: | :--- | :---: | :---: | :---: |
| `go` | 142 | `BASE-BM25` | 0.2665 | 0.6681 | 0.0974 |
| `go` | 142 | `CAND-C` | 0.1734 | 0.6751 | 0.0329 |
| `go` | 142 | `CAND-F` | 0.1587 | 0.6511 | 0.0258 |
| `go` | 142 | `BASE-REPOMAP` | 0.2850 | 0.7786 | 0.0857 |
| `java` | 9 | `BASE-BM25` | 0.1894 | 0.5556 | 0.0370 |
| `java` | 9 | `CAND-C` | 0.1976 | 0.7593 | 0.0370 |
| `java` | 9 | `CAND-F` | 0.1420 | 0.7593 | 0.0000 |
| `java` | 9 | `BASE-REPOMAP` | 0.3371 | 0.7037 | 0.1667 |
| `javascript` | 26 | `BASE-BM25` | 0.0204 | 0.0321 | 0.0000 |
| `javascript` | 26 | `CAND-C` | 0.0281 | 0.0641 | 0.0000 |
| `javascript` | 26 | `CAND-F` | 0.0265 | 0.0641 | 0.0000 |
| `javascript` | 26 | `BASE-REPOMAP` | 0.0314 | 0.1410 | 0.0000 |
| `md` | 3 | `BASE-BM25` | 0.0387 | 0.3333 | 0.0000 |
| `md` | 3 | `CAND-C` | 0.0623 | 0.1111 | 0.0000 |
| `md` | 3 | `CAND-F` | 0.0900 | 0.1111 | 0.0000 |
| `md` | 3 | `BASE-REPOMAP` | 0.1730 | 0.1111 | 0.1111 |
| `pyi` | 1 | `BASE-BM25` | 0.0159 | 0.0000 | 0.0000 |
| `pyi` | 1 | `CAND-C` | 0.0179 | 0.0000 | 0.0000 |
| `pyi` | 1 | `CAND-F` | 0.0164 | 0.0000 | 0.0000 |
| `pyi` | 1 | `BASE-REPOMAP` | 0.0667 | 1.0000 | 0.0000 |
| `python` | 98 | `BASE-BM25` | 0.1274 | 0.3231 | 0.0289 |
| `python` | 98 | `CAND-C` | 0.1423 | 0.4949 | 0.0102 |
| `python` | 98 | `CAND-F` | 0.1417 | 0.5272 | 0.0102 |
| `python` | 98 | `BASE-REPOMAP` | 0.1956 | 0.6718 | 0.0408 |
| `rst` | 8 | `BASE-BM25` | 0.0882 | 0.1042 | 0.0000 |
| `rst` | 8 | `CAND-C` | 0.0786 | 0.1667 | 0.0000 |
| `rst` | 8 | `CAND-F` | 0.0697 | 0.1667 | 0.0000 |
| `rst` | 8 | `BASE-REPOMAP` | 0.1474 | 0.3542 | 0.0000 |
| `rust` | 48 | `BASE-BM25` | 0.1223 | 0.3906 | 0.0000 |
| `rust` | 48 | `CAND-C` | 0.1208 | 0.3663 | 0.0104 |
| `rust` | 48 | `CAND-F` | 0.1441 | 0.3733 | 0.0174 |
| `rust` | 48 | `BASE-REPOMAP` | 0.2683 | 0.6372 | 0.0938 |
| `typescript` | 10 | `BASE-BM25` | 0.0584 | 0.4000 | 0.0000 |
| `typescript` | 10 | `CAND-C` | 0.0545 | 0.4000 | 0.0000 |
| `typescript` | 10 | `CAND-F` | 0.0473 | 0.3000 | 0.0000 |
| `typescript` | 10 | `BASE-REPOMAP` | 0.0971 | 0.6500 | 0.0000 |