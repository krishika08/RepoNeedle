# RepoNeedle Stage 3.9: Gate B Failure & Ranking Dynamics Analysis

## 1. Executive Summary

- **Total Evaluated Positive Queries**: 345 across 25 repositories in ARB v2.
- **Top-3 Lexical Freeze Violations**: 0 queries violated top-3 rank preservation (100.0% invariant compliance).
- **Cascade vs. BM25 Comparison**:
  - **Wins (Cascade > BM25)**: 232 queries
  - **Losses (Cascade < BM25)**: 18 queries
  - **Ties (Cascade == BM25)**: 95 queries
- **Key Empirical Takeaway**:
  - In Stage 3.8, Candidate F suffered **70 catastrophic early-rank demotions** (`BM25_WIN_CAND_DEMOTED`) where BM25 had correctly ranked the gold file in top 3, but unnormalized PageRank diffusion demoted it.
  - The `CascadedRanker` completely eliminates all top-3 demotions by freezing ranks 0, 1, 2. Consequently, early-rank precision and reciprocal rank floor are strictly bounded below by BM25.

---

## 2. Wins Analysis: Where Graph Expansion Succeeded

Queries where bounded graph expansion promoted gold files into eligible ranks (>= 4):

| Query ID | Repository | Task Track | BM25 Rank | Cascade Rank | BM25 MRR | Cascade MRR | $\Delta$ MRR |
|---|---|---|---:|---:|---:|---:|---:|
| `1dd2bdfdcf70` | `etcd-io/etcd` | `code2test` | 12 | 4 | 0.0833 | 0.2500 | +0.1667 |
| `cbb729b2af79` | `gin-gonic/gin` | `edit2ripple` | 12 | 4 | 0.0833 | 0.2500 | +0.1667 |
| `d5f1198f6fb5` | `etcd-io/etcd` | `comment2context` | 10 | 4 | 0.1000 | 0.2500 | +0.1500 |
| `725dd77bdee8` | `gin-gonic/gin` | `code2test` | 8 | 4 | 0.1250 | 0.2500 | +0.1250 |
| `eb14454231d3` | `gin-gonic/gin` | `code2test` | 8 | 4 | 0.1250 | 0.2500 | +0.1250 |
| `9c620240e44f` | `huggingface/transformers` | `code2test` | 23 | 6 | 0.0435 | 0.1667 | +0.1232 |
| `8e6bf4a9d26a` | `astral-sh/ruff` | `comment2context` | 118 | 8 | 0.0085 | 0.1250 | +0.1165 |
| `148cbb036342` | `etcd-io/etcd` | `edit2ripple` | 7 | 4 | 0.1429 | 0.2500 | +0.1071 |
| `e0a0b8ad2d50` | `etcd-io/etcd` | `code2test` | 7 | 4 | 0.1429 | 0.2500 | +0.1071 |
| `2bbbe7ecba9c` | `pytest-dev/pytest` | `code2test` | 7 | 4 | 0.1429 | 0.2500 | +0.1071 |
| `7f2b7ed09afc` | `fastapi/fastapi` | `code2test` | 73 | 9 | 0.0137 | 0.1111 | +0.0974 |
| `0631449332f9` | `caddyserver/caddy` | `edit2ripple` | 36 | 8 | 0.0278 | 0.1250 | +0.0972 |
| `ba14e2bd5668` | `etcd-io/etcd` | `code2test` | 17 | 7 | 0.0588 | 0.1429 | +0.0840 |
| `e1280404f66f` | `etcd-io/etcd` | `comment2context` | 6 | 4 | 0.1667 | 0.2500 | +0.0833 |
| `bb23acb59ca8` | `etcd-io/etcd` | `comment2context` | 6 | 4 | 0.1667 | 0.2500 | +0.0833 |

---

## 3. Losses Analysis: Where Cascade Regressed Against BM25

Total losses: 18 queries.

| Query ID | Repository | Task Track | BM25 Rank | Cascade Rank | BM25 MRR | Cascade MRR | $\Delta$ MRR |
|---|---|---|---:|---:|---:|---:|---:|
| `a56cae404e50` | `fastapi/fastapi` | `code2test` | 9 | 141 | 0.1111 | 0.0071 | -0.1040 |
| `38c2a13af5bd` | `etcd-io/etcd` | `comment2context` | 5 | 7 | 0.2000 | 0.1429 | -0.0571 |
| `41deac7db89b` | `etcd-io/etcd` | `comment2context` | 4 | 5 | 0.2500 | 0.2000 | -0.0500 |
| `117ee2d955a7` | `etcd-io/etcd` | `edit2ripple` | 5 | 6 | 0.2000 | 0.1667 | -0.0333 |
| `262ecc80fa36` | `huggingface/transformers` | `edit2ripple` | 5 | 6 | 0.2000 | 0.1667 | -0.0333 |
| `18a155cebfee` | `tokio-rs/tokio` | `edit2ripple` | 6 | 7 | 0.1667 | 0.1429 | -0.0238 |
| `ed5f5fce7ddb` | `pallets/click` | `trace2code` | 6 | 7 | 0.1667 | 0.1429 | -0.0238 |
| `d33132ce299c` | `huggingface/transformers` | `code2test` | 7 | 8 | 0.1429 | 0.1250 | -0.0179 |
| `35154a761b37` | `tokio-rs/tokio` | `comment2context` | 8 | 9 | 0.1250 | 0.1111 | -0.0139 |
| `34b14301c567` | `tokio-rs/tokio` | `trace2code` | 9 | 10 | 0.1111 | 0.1000 | -0.0111 |
| `44eb66d77e31` | `etcd-io/etcd` | `comment2context` | 10 | 11 | 0.1000 | 0.0909 | -0.0091 |
| `95131f4a1d5c` | `gin-gonic/gin` | `trace2code` | 11 | 12 | 0.0909 | 0.0833 | -0.0076 |
| `02faf838effb` | `gin-gonic/gin` | `edit2ripple` | 14 | 15 | 0.0714 | 0.0667 | -0.0048 |
| `269e3e34c64f` | `clap-rs/clap` | `edit2ripple` | 69 | 79 | 0.0145 | 0.0127 | -0.0018 |
| `405caf34d52d` | `microsoft/playwright` | `comment2context` | 28 | 29 | 0.0357 | 0.0345 | -0.0012 |

---

## 4. Remaining Gap to RepoMap Baseline

| Metric | BASE-BM25 | CAND-C | CAND-F | CAND-CASCADE | BASE-REPOMAP |
|---|---:|---:|---:|---:|---:|
| MRR (Canonical) | 0.1735 | 0.1399 | 0.1351 | (See CASCADE_ABLATIONS.csv) | 0.2293 |
| Recall@20 (Fractional) | 0.4549 | 0.5105 | 0.5078 | (See CASCADE_ABLATIONS.csv) | 0.6599 |

### Root Causes for Remaining RepoMap Advantage:
1. **Repository Map Global Graph**: RepoMap builds an entire repository call-tree and token-budgeted tree representation using tree-sitter tags and global PageRank across all symbols. RepoNeedle's offline lightweight polyglot parser extracts top-level symbols and regex imports, which misses fine-grained intra-class method calls.
2. **Context Window Tree Density**: RepoMap packs signatures and docstrings directly into the prompt tree, providing high token efficiency, whereas chunk packing in RepoNeedle packs entire file chunks.
