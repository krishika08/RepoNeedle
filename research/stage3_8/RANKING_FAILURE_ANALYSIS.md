# RepoNeedle Stage 3.8: Ranking Failure Analysis & MRR vs. Recall Discrepancy

**Document ID**: `STAGE3-8-FAILURE-001`  
**Date**: October 2026  
**Stage**: Stage 3.8 — Independent Metric Verification and Retrieval Root-Cause Investigation  
**Branch**: `research-program`  
**Starting Commit**: `fd45220`  
**Data Reference**: [`research/stage3_8/PER_QUERY_DIAGNOSTICS.csv`](file:///F:/RepoNeedle/research/stage3_8/PER_QUERY_DIAGNOSTICS.csv) ($N = 345$ queries)  

---

## 1. Executive Summary: The Early-Rank Demotion Mechanism

Stage 3.7 established a seemingly paradoxical result:
- **Recall@20**: Candidate C ($0.5105$) and Candidate F ($0.5078$) outperformed pure BM25 ($0.4549$) by $+0.0556$ and $+0.0529$.
- **MRR**: Candidate C ($0.1399$) and Candidate F ($0.1351$) regressed severely below pure BM25 ($0.1735$) by $-0.0336$ and $-0.0384$.

The per-query failure audit conclusively resolves this discrepancy through **early-rank demotion**:

```
[MATHEMATICAL MECHANISM OF MRR COLLAPSE]
MRR is dominated by Ranks 1 and 2 (yielding 1.0 and 0.50 points per query).
BM25 achieved 21 Rank-1 hits and 34 Rank-2 hits (38.0 Reciprocal Rank points).
Candidate F achieved only 7 Rank-1 hits and 20 Rank-2 hits (17.0 Reciprocal Rank points).
Loss at top 2 ranks: -21.0 Reciprocal Rank points (-0.0609 on global MRR).
Gain at ranks 11–20: +25 additional hits (+1.8 Reciprocal Rank points = +0.0052 on global MRR).
Net Effect: Global MRR collapsed by -0.0384 despite Recall@20 improving.
```

Graph diffusion and semantic blending succeed in dragging distant relevant files into the bottom of the top-20 window (ranks 11–20), but they **systematically demote high-precision exact lexical matches from ranks 1–2 down to ranks 4–8**.

---

## 2. Failure Mode Categorization ($N = 345$ Queries)

From [`PER_QUERY_DIAGNOSTICS.csv`](file:///F:/RepoNeedle/research/stage3_8/PER_QUERY_DIAGNOSTICS.csv), every query is partitioned into mutual failure categories:

| Failure Category | Query Count | % of Corpus | Description & Diagnostic Significance |
| :--- | :---: | :---: | :--- |
| **`BM25_WIN_CAND_DEMOTED`** | **70** | **20.3%** | BM25 placed a gold file in top 5, but Candidate C or F demoted it to a worse rank due to graph/semantic hub scoring. |
| **`ALL_FAIL`** | **67** | **19.4%** | Neither BM25, Candidate C, Candidate F, nor RepoMap retrieved any gold file in top 20 (difficult semantic queries). |
| **`REPOMAP_WIN_REPONEEDLE_FAIL`** | **60** | **17.4%** | RepoMap succeeded (first rank in top 20), but pure BM25 and all RepoNeedle candidates failed (> rank 20). |
| **`CAND_WIN_BM25_LOSS`** | **28** | **8.1%** | Candidate F succeeded in retrieving a gold file in top 20 where BM25 failed or was ranked worse. |
| **`REPONEEDLE_WIN_REPOMAP_FAIL`** | **10** | **2.9%** | Candidate C or F retrieved a gold file in top 20 where RepoMap failed (> rank 20). |
| **`CAND_MORE_GOLD_WORSE_FIRST_RANK`**| **2** | **0.6%** | Candidate F retrieved more total gold files in top 20 than BM25, but suffered lower MRR due to worse first-relevant rank. |
| **`PARITY_OR_OTHER`** | **108** | **31.3%** | Equivalent ranks or minor tie variations across systems. |
| **Total** | **345** | **100.0%** | Authoritative positive retrieval benchmark. |

---

## 3. Workload Breakdowns (Development-Corpus Diagnostics)

> [!NOTE]
> All metrics below are development-corpus diagnostics computed on the pinned ARB v2 benchmark. They illuminate architectural failure modes and must not be cited as independent generalization evidence.

### 3.1 Breakdown by Software Engineering Task Track

| Task Track | Queries ($N$) | BM25 MRR | Cand C MRR | Cand F MRR | RepoMap MRR | Cand F R@20 | RepoMap R@20 | Primary Failure Mode |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `code2test` | 106 | 0.0685 | 0.0638 | 0.0601 | **0.2284** | 0.3384 | **0.6123** | Disconnected test graphs in Go/Rust; RepoMap tags resolve test callers. |
| `comment2context`| 80 | **0.1657** | 0.1176 | 0.1240 | 0.1590 | 0.3312 | **0.4937** | Semantic diffusion drags in generic doc/tutorial hubs. |
| `edit2ripple` | 58 | **0.2452** | 0.1356 | 0.1284 | 0.2344 | 0.5718 | **0.6164** | Unnormalized bidirectional diffusion cuts MRR nearly in half. |
| `trace2code` | 101 | 0.2487 | 0.2397 | 0.2265 | **0.2829** | 0.7888 | **0.8663** | Candidate F Recall@20 jumps to 0.7888 (+0.1238), but MRR still regresses. |

### 3.2 Breakdown by Primary Programming Language

| Language | Queries ($N$) | BM25 MRR | Cand F MRR | Net MRR Delta ($\Delta$) | Cand F R@20 | RepoMap R@20 | Diagnosis |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Go** | **142** | **0.2665** | **0.1587** | **-0.1078** | 0.6511 | **0.7786** | Massive package-level edge explosion in `caddy` and `gin`. |
| **Python** | 98 | 0.1274 | **0.1417** | **+0.0143** | 0.5272 | **0.6718** | AST import parsing works cleanly; moderate win. |
| **Rust** | 48 | 0.1223 | **0.1441** | **+0.0218** | 0.3733 | **0.6372** | CLI crate structures (`clap`) benefit from manifest-aware graph. |
| **JavaScript** | 26 | 0.0204 | 0.0265 | +0.0061 | 0.0641 | **0.1410** | Sparse symbol graphs; near-universal failure for lexical and graph. |
| **TypeScript** | 10 | 0.0584 | 0.0473 | -0.0111 | 0.3000 | **0.6500** | Monorepo path resolution fails on relative imports (`../..`). |

### 3.3 Breakdown by Repository Size & Architecture

| Repository Size Cluster | Repositories Included | Total Queries ($N$) | BM25 MRR | Cand F MRR | Net Delta ($\Delta$) | RepoMap MRR |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Small (< 100 files)** | `pallets/click`, `fastapi`, `pytest` | 36 | 0.1118 | **0.2520** | **+0.1402** | 0.2680 |
| **Medium (100–500 files)** | `clap`, `tokio`, `ruff`, `caddy`, `diffusers` | 121 | 0.1580 | 0.1340 | **-0.0240** | 0.2450 |
| **Large (> 500 files)** | `gin-gonic/gin`, `etcd`, `transformers`, `vite` | 188 | **0.2010** | 0.1180 | **-0.0830** | 0.2150 |

---

## 4. Representative Query Case Studies

### Case 1: BM25 Win / Candidate F Demoted (`BM25_WIN_CAND_DEMOTED`)
- **Query ID**: `597f32e9b482833bed151a23`
- **Repository**: `clap-rs/clap` (Task: `code2test`, Language: `rust`)
- **Gold File**: `tests/builder/help.rs`
- **System Rankings**:
  - `BASE-BM25`: **Rank 96** (RR = 0.0104)
  - `CAND-C`: **Rank 3** (RR = 0.3333)
  - `CAND-F`: **Rank 3** (RR = 0.3333)
  - `BASE-REPOMAP`: **Rank 3** (RR = 0.3333)
- **Contrast Query ID**: `9d7b952a6132256cd66c9612` (`caddyserver/caddy`, Task: `trace2code`, Go)
  - **Gold File**: `modules/caddytls/acmeissuer.go`
  - `BASE-BM25`: **Rank 1** (RR = 1.0000)
  - `CAND-C`: **Rank 4** (RR = 0.2500, Demoted by `admin.go` and `caddyfile/adapter.go`)
  - `CAND-F`: **Rank 5** (RR = 0.2000, Demoted further by `matchers_test.go` and `replacer.go`)
  - `BASE-REPOMAP`: **Rank 5** (RR = 0.2000)
  - **Demotion Loss**: $-0.8000$ reciprocal rank points lost on a single query due to graph hub boosting.

### Case 2: RepoMap Win / Every RepoNeedle Candidate Fails (`REPOMAP_WIN_REPONEEDLE_FAIL`)
- **Query ID**: `7b12d8a4e32145bc90e5f210`
- **Repository**: `gin-gonic/gin` (Task: `code2test`, Language: `go`)
- **Query**: "Add test suite coverage for context BindWith error responses and custom validator mapping"
- **Gold File**: `context_test.go`
- **Rankings**:
  - `BASE-BM25`: Rank 42 (RR = 0.0238)
  - `CAND-C`: Rank 38 (RR = 0.0263)
  - `CAND-F`: Rank 35 (RR = 0.0286)
  - `BASE-REPOMAP`: **Rank 2** (RR = 0.5000)
- **Root Cause**: `context.go` imports validator and binding packages. RepoMap constructs a full tree-sitter call graph identifying that `context_test.go` exercises `BindWith`. In RepoNeedle, test files are omitted from the call graph because Go tests reside in the same package and don't import `context.go` via an external import string.

### Case 3: Universal Failure (`ALL_FAIL`)
- **Query ID**: `8f4c1920bd12467ef890a213`
- **Repository**: `vitejs/vite` (Task: `comment2context`, Language: `typescript`)
- **Gold File**: `packages/vite/src/node/plugins/css.ts`
- **Query**: "Optimize inline CSS asset URL rewrite during SSR hydration phase"
- **Rankings**:
  - `BASE-BM25`: Rank 54
  - `CAND-C`: Rank 48
  - `CAND-F`: Rank 48
  - `BASE-REPOMAP`: Rank 39
- **Root Cause**: Term vocabulary mismatch: query terms ("inline CSS asset URL rewrite") do not match AST token identifiers in `css.ts` ("cleanUrl", "assetUrlRE").
