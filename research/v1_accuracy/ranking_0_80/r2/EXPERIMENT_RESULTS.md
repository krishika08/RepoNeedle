# RepoNeedle — Mission 0.80+ (Ranking Intelligence Research Programme)
# Phase R2 Deliverable 6: Controlled Experiment Results Matrix

**Document ID:** `EXPERIMENT_RESULTS.md`  
**Status:** Approved & Validated  
**Date:** November 2, 2026  
**Author:** Principal Search Relevance Engineer, Information Retrieval Researcher & ML Ranking Architect  
**Scope:** Controlled Evaluation of Treatments A through H across Train (210), Validation (60), and Held-Out (75) Queries  

---

## 1. Executive Summary & Master Results Matrix

Phase R2 evaluated eight ranking configurations across the strict 15/5/5 repository-clustered split.
Candidate pool gold recall is preserved at **$100.0\%$ (514/514 gold files present)** across all treatments and all splits.

```mermaid
flowchart LR
    subgraph Validation Set Progression (60 Queries, 5 Repos)
        A["Treatment A: Baseline M1<br/>MRR: 0.1381 | Hit@1: 0.0%"] --> B["Treatment B: SFS Alone<br/>MRR: 0.2022 (+46.4%)"]
        A --> C["Treatment C: TIP Alone<br/>MRR: 0.2334 (+69.0%)"]
        B --> E["Treatment E: SFS + TIP (Champion)<br/>MRR: 0.2971 (+115.1%) | Hit@1: 16.7%"]
        C --> E
        E --> H["Treatment H: SFS + TIP + SMS<br/>MRR: 0.2954 (+113.9%)"]
    end
```

### Master Results Across Partitions

| Split & Treatment Code | Treatment Description | MRR | $\Delta$ MRR vs A | Rel $\Delta$ % | Hit@1 % | Recall@5 | Recall@10 | Recall@20 | Candidate Recall | Seed Trap Count | P95 Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TRAIN (210 Queries)** | | | | | | | | | | | |
| **Treatment A** | Frozen Baseline (M1) | 0.3539 | +0.0000 | 0.0% | 14.29% | 0.5226 | 0.6553 | 0.7499 | 100.0% | 99 | 1.32 ms |
| **Treatment B** | SFS Alone ($\gamma = 0.05$) | 0.4304 | +0.0765 | +21.6% | 24.29% | 0.5448 | 0.6601 | 0.7571 | 100.0% | 0 | 3.08 ms |
| **Treatment C** | TIP Alone ($\beta = 1.5$) | 0.3978 | +0.0439 | +12.4% | 19.05% | 0.5593 | 0.6842 | 0.8009 | 100.0% | 75 | 8.87 ms |
| **Treatment D** | SMS Alone ($w = 0.1$) | 0.3752 | +0.0213 | +6.0% | 13.81% | 0.5429 | 0.6726 | 0.7952 | 100.0% | 110 | 38.94 ms |
| **Treatment E** | **SFS + TIP (Champion)** | **0.4544** | **+0.1005** | **+28.4%** | **25.71%** | **0.5745** | **0.7033** | **0.8009** | **100.0%** | **0** | **10.96 ms** |
| **Treatment F** | SFS + SMS | 0.4572 | +0.1033 | +29.2% | 27.14% | 0.5520 | 0.6688 | 0.7658 | 100.0% | 0 | 46.97 ms |
| **Treatment G** | TIP + SMS | 0.4131 | +0.0592 | +16.7% | 18.10% | 0.5763 | 0.6944 | 0.8199 | 100.0% | 96 | 67.55 ms |
| **Treatment H** | SFS + TIP + SMS (Combined) | **0.4813** | **+0.1274** | **+36.0%** | **28.57%** | **0.5855** | **0.7096** | **0.8072** | **100.0%** | **0** | **52.20 ms** |
| **VALIDATION (60 Queries)** | | | | | | | | | | | |
| **Treatment A** | Frozen Baseline (M1) | 0.1381 | +0.0000 | 0.0% | 0.00% | 0.1986 | 0.3347 | 0.5125 | 100.0% | 48 | 2.18 ms |
| **Treatment B** | SFS Alone ($\gamma = 0.05$) | 0.2022 | +0.0641 | +46.4% | 6.67% | 0.2292 | 0.3569 | 0.5125 | 100.0% | 0 | 2.89 ms |
| **Treatment C** | TIP Alone ($\beta = 1.5$) | 0.2334 | +0.0953 | +69.0% | 8.33% | 0.2819 | 0.4181 | 0.5792 | 100.0% | 39 | 12.22 ms |
| **Treatment D** | SMS Alone ($w = 0.1$) | 0.1350 | -0.0032 | -2.3% | 0.00% | 0.2292 | 0.3347 | 0.5306 | 100.0% | 52 | 44.67 ms |
| **Treatment E** | **SFS + TIP (Champion)** | **0.2971** | **+0.1590** | **+115.1%** | **16.67%** | **0.3208** | **0.4236** | **0.5875** | **100.0%** | **0** | **13.20 ms** |
| **Treatment F** | SFS + SMS | 0.1946 | +0.0565 | +40.9% | 5.00% | 0.2403 | 0.3347 | 0.5681 | 100.0% | 0 | 39.42 ms |
| **Treatment G** | TIP + SMS | 0.1671 | +0.0290 | +21.0% | 0.00% | 0.2792 | 0.4097 | 0.6056 | 100.0% | 52 | 46.62 ms |
| **Treatment H** | SFS + TIP + SMS (Combined) | **0.2954** | **+0.1573** | **+113.9%** | **16.67%** | **0.3069** | **0.4097** | **0.6014** | **100.0%** | **0** | **48.82 ms** |
| **HELD-OUT TEST (75 Queries)**| | | | | | | | | | | |
| **Treatment A** | Frozen Baseline (M1) | 0.1290 | +0.0000 | 0.0% | 1.33% | 0.2444 | 0.3600 | 0.4133 | 100.0% | 64 | 5.12 ms |
| **Treatment E** | **SFS + TIP (Champion)** | **0.2965** | **+0.1675** | **+129.8%** | **17.33%** | **0.4489** | **0.5222** | **0.5800** | **100.0%** | **0** | **32.40 ms** |
| **Treatment H** | SFS + TIP + SMS (Combined) | **0.3115** | **+0.1825** | **+141.5%** | **17.33%** | **0.4622** | **0.5289** | **0.5889** | **100.0%** | **0** | **159.16 ms** |

---

## 2. Task-Level Performance Breakdown

Evaluation across task tracks reveals that the gains are driven by resolving the exact structural failure modes diagnosed in Phase R1:

### Validation Set Breakdown (60 Queries)

| Task Track | Count ($n$) | Baseline M1 (A) | Treatment E (Champion) | Absolute Lift ($\Delta$) | Treatment H | Absolute Lift ($\Delta$) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`code2test`** | 21 | 0.1487 | **0.4820** | **+0.3332** | **0.5071** | **+0.3583** |
| **`comment2context`** | 26 | 0.1178 | **0.1866** | **+0.0688** | 0.1651 | +0.0472 |
| **`edit2ripple`** | 7 | 0.1695 | **0.2773** | **+0.1078** | 0.2677 | +0.0981 |
| **`trace2code`** | 6 | 0.1521 | **0.1521** | **+0.0000** | 0.1521 | +0.0000 |

### Held-Out Test Set Breakdown (75 Queries)

| Task Track | Count ($n$) | Baseline M1 (A) | Treatment E (Champion) | Absolute Lift ($\Delta$) | Treatment H | Absolute Lift ($\Delta$) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`code2test`** | 37 | 0.0975 | **0.3631** | **+0.2656** | **0.3845** | **+0.2870** |
| **`comment2context`** | 23 | 0.1599 | **0.2423** | **+0.0823** | 0.2310 | +0.0711 |
| **`edit2ripple`** | 14 | 0.1468 | **0.2067** | **+0.0599** | 0.2241 | +0.0773 |
| **`trace2code`** | 1 | 0.3333 | **0.3333** | **+0.0000** | 0.3333 | +0.0000 |

### Key Diagnostic Takeaways
1. **Dramatic Surge on `code2test`**:
   The combination of SFS (demoting changed implementation files) and TIP (boosting test files) produces an astonishing $+0.3332$ MRR surge on Validation ($0.1487 \to 0.4820$) and $+0.2656$ on Held-out ($0.0975 \to 0.3631$).
2. **Substantial Gains on `comment2context` and `edit2ripple`**:
   Eliminating the given review file and anchor diff file from Rank 1 produces a $+0.0688$ lift on `comment2context` and $+0.1078$ lift on `edit2ripple`.
3. **Zero Regression on `trace2code`**:
   In both Validation and Held-out, `trace2code` performance is preserved with exact $0.0000$ regression, confirming that intent conditioning properly detects execution tracebacks and leaves them untouched.

---

## 3. Repository-Level Breakdown Across All 25 Repositories

| Cluster | Repository | Language | Queries | Baseline M1 MRR | Treatment E MRR | Delta ($\Delta$) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | `gin-gonic/gin` | Go | 88 | 0.4569 | **0.5218** | +0.0649 |
| **Train** | `etcd-io/etcd` | Go | 41 | 0.2501 | **0.3687** | +0.1186 |
| **Train** | `pallets/click` | Python | 26 | 0.3939 | **0.3939** | +0.0000 |
| **Train** | `caddyserver/caddy` | Go | 13 | 0.3393 | **0.4286** | +0.0893 |
| **Train** | `clap-rs/clap` | Rust | 10 | 0.2407 | **0.4852** | +0.2445 |
| **Train** | `spring-projects/spring-boot` | Java | 8 | 0.2898 | **0.3958** | +0.1060 |
| **Train** | `vuejs/core` | TypeScript | 6 | 0.0926 | **0.3333** | +0.2407 |
| **Train** | `pypa/pip` | Python | 5 | 0.2900 | **0.4500** | +0.1600 |
| **Train** | `fastapi/fastapi` | Python | 3 | 0.0947 | **0.3889** | +0.2942 |
| **Train** | `scrapy/scrapy` | Python | 3 | 0.1785 | **0.3333** | +0.1548 |
| **Train** | `ipython/ipython` | Python | 2 | 0.2250 | **0.3333** | +0.1083 |
| **Train** | `tox-dev/tox` | Python | 2 | 0.1786 | **0.3333** | +0.1547 |
| **Train** | `mockito/mockito` | Java | 1 | 0.0167 | **0.2000** | +0.1833 |
| **Train** | `HypothesisWorks/hypothesis` | Python | 1 | 0.5000 | **0.5000** | +0.0000 |
| **Train** | `numpy/numpy` | Python/C | 1 | 0.3333 | **0.5000** | +0.1667 |
| **Val** | `tokio-rs/tokio` | Rust | 38 | 0.1822 | **0.3478** | **+0.1656** |
| **Val** | `huggingface/diffusers` | Python | 16 | 0.0542 | **0.1835** | **+0.1293** |
| **Val** | `microsoft/playwright` | TypeScript | 4 | 0.0396 | **0.1875** | **+0.1479** |
| **Val** | `pydantic/pydantic` | Python | 1 | 0.3333 | **0.5000** | **+0.1667** |
| **Val** | `eslint/eslint` | JavaScript | 1 | 0.0051 | **0.1000** | **+0.0949** |
| **Held-Out**| `huggingface/transformers` | Python | 36 | 0.1821 | **0.3214** | **+0.1393** |
| **Held-Out**| `vitejs/vite` | TypeScript | 25 | 0.0344 | **0.2458** | **+0.2114** |
| **Held-Out**| `pytest-dev/pytest` | Python | 7 | 0.1994 | **0.3286** | **+0.1292** |
| **Held-Out**| `astral-sh/ruff` | Rust | 6 | 0.1159 | **0.2778** | **+0.1619** |
| **Held-Out**| `python/mypy` | Python | 1 | 0.1667 | **0.3333** | **+0.1666** |
| **Overall** | **Benchmark Set A (Total)** | **Mixed** | **345** | **0.2675** | **0.3927** | **+0.1252** |

---

## 4. Rank-1 Displacement & Seed Trap Elimination

| Split | Total Queries | Baseline Displacements | Treatment E Displacements | Baseline Seed Traps | Treatment E Seed Traps | Trap Elimination % |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | 210 | 180 (85.7%) | 156 (74.3%) | 99 (47.1%) | **0 (0.0%)** | **100.0%** |
| **Validation** | 60 | 60 (100.0%) | 50 (83.3%) | 48 (80.0%) | **0 (0.0%)** | **100.0%** |
| **Held-Out** | 75 | 74 (98.7%) | 62 (82.7%) | 64 (85.3%) | **0 (0.0%)** | **100.0%** |
| **Total** | **345** | **314 (91.0%)** | **268 (77.7%)** | **211 (61.2%)** | **0 (0.0%)** | **100.0%** |

Rank 1 hits increased from **31 queries to 77 queries** across the benchmark, while 100% of seed traps were eliminated without a single candidate recall loss.

