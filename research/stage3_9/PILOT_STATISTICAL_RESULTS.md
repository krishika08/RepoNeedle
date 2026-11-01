# RepoNeedle Stage 3.9.4: Pilot Statistical Analysis Report

> **Evaluation Population:** 345 canonical positive ARB v2 queries across 25 repositories (104 queries in 13 Python repos).
> **Inferential Method:** 10,000 Paired Repository-Clustered Bootstrap Resamples (Seed 42).
> **Significance Criteria:** Mean difference $\ge +0.0050$ and 95% Clustered CI lower bound $> 0.0$.

## 1. Overall Benchmark Results (All 345 Queries)

| Experiment | MRR | Recall@5 | Recall@10 | Recall@20 | Hit@20 | BCY@8k | Wins / Ties / Losses vs EXP-386 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **EXP-386** | 0.2067 | 0.2522 | 0.3808 | 0.5508 | 0.6406 | 0.0556 | Reference Baseline |
| **EXP-392a** | 0.2038 | 0.2522 | 0.3808 | 0.5508 | 0.6406 | 0.0546 | 2 / 337 / 6 |
| **EXP-392b** | 0.2038 | 0.2522 | 0.3808 | 0.5508 | 0.6406 | 0.0546 | 2 / 337 / 6 |

### Paired Inferential Differences (EXP-392a vs EXP-386 Reference)

| Metric | Mean Diff (\Delta) | 95% Clustered CI | p-value | Minimum Meaningful Effect (+0.0050) | Statistically Significant? |
|---|:---:|:---:|:---:|:---:|:---:|
| **MRR** | -0.0029 | [-0.0119, +0.0026] | 0.1637 | NOT MET | NO |
| **Recall@5** | +0.0000 | [+0.0000, +0.0000] | 1.0000 | — | NO |
| **Recall@10** | +0.0000 | [+0.0000, +0.0000] | 1.0000 | — | NO |
| **Recall@20** | +0.0000 | [+0.0000, +0.0000] | 1.0000 | — | NO |
| **Hit@20** | +0.0000 | [+0.0000, +0.0000] | 1.0000 | — | NO |
| **BCY@8k** | -0.0010 | [-0.0073, +0.0034] | 0.3982 | — | NO |

---

## 2. Python-Eligible Subset Results (104 Queries across 13 Repositories)

| Experiment | MRR | Recall@5 | Recall@10 | Recall@20 | Hit@20 | BCY@8k | Wins / Ties / Losses vs EXP-386 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **EXP-386** | 0.1524 | 0.1763 | 0.2821 | 0.4567 | 0.5288 | 0.0224 | Reference Baseline |
| **EXP-392a** | 0.1428 | 0.1763 | 0.2821 | 0.4567 | 0.5288 | 0.0192 | 2 / 96 / 6 |
| **EXP-392b** | 0.1428 | 0.1763 | 0.2821 | 0.4567 | 0.5288 | 0.0192 | 2 / 96 / 6 |

### Paired Inferential Differences (Python Subset: EXP-392a vs EXP-386)

| Metric | Mean Diff (\Delta) | 95% Clustered CI | p-value | Minimum Meaningful Effect (+0.0050) | Statistically Significant? |
|---|:---:|:---:|:---:|:---:|:---:|
| **MRR** | -0.0096 | [-0.0426, +0.0079] | 0.1596 | NOT MET | NO |
| **Recall@5** | +0.0000 | [+0.0000, +0.0000] | 1.0000 | — | NO |
| **Recall@10** | +0.0000 | [+0.0000, +0.0000] | 1.0000 | — | NO |
| **Recall@20** | +0.0000 | [+0.0000, +0.0000] | 1.0000 | — | NO |
| **Hit@20** | +0.0000 | [+0.0000, +0.0000] | 1.0000 | — | NO |
| **BCY@8k** | -0.0032 | [-0.0278, +0.0085] | 0.3995 | — | NO |

---

## 3. Repository-Level Effects Breakdown

| Repository | Language | Query Count | EXP-386 MRR | EXP-392a MRR | EXP-392b MRR | \Delta MRR (392a - 386) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `HypothesisWorks/hypothesis` | Python | 1 | 0.0038 | 0.0038 | 0.0038 | +0.0000 |
| `astral-sh/ruff` | Other | 6 | 0.0732 | 0.0732 | 0.0732 | +0.0000 |
| `caddyserver/caddy` | Other | 13 | 0.3500 | 0.3500 | 0.3500 | +0.0000 |
| `clap-rs/clap` | Other | 10 | 0.0815 | 0.0815 | 0.0815 | +0.0000 |
| `eslint/eslint` | Other | 1 | 0.0103 | 0.0103 | 0.0103 | +0.0000 |
| `etcd-io/etcd` | Other | 41 | 0.2332 | 0.2332 | 0.2332 | +0.0000 |
| `fastapi/fastapi` | Python | 3 | 0.0733 | 0.0733 | 0.0733 | +0.0000 |
| `gin-gonic/gin` | Other | 88 | 0.3278 | 0.3278 | 0.3278 | +0.0000 |
| `huggingface/diffusers` | Python | 16 | 0.2352 | 0.1935 | 0.1935 | -0.0417 |
| `huggingface/transformers` | Python | 36 | 0.1426 | 0.1565 | 0.1565 | +0.0139 |
| `ipython/ipython` | Python | 2 | 0.0819 | 0.0819 | 0.0819 | +0.0000 |
| `microsoft/playwright` | Other | 4 | 0.0775 | 0.0775 | 0.0775 | +0.0000 |
| `mockito/mockito` | Other | 1 | 0.0070 | 0.0070 | 0.0070 | +0.0000 |
| `numpy/numpy` | Python | 1 | 0.0345 | 0.0345 | 0.0345 | +0.0000 |
| `pallets/click` | Python | 26 | 0.1281 | 0.1217 | 0.1217 | -0.0064 |
| `pydantic/pydantic` | Python | 1 | 0.0122 | 0.0122 | 0.0122 | +0.0000 |
| `pypa/pip` | Python | 5 | 0.3630 | 0.2297 | 0.2297 | -0.1333 |
| `pytest-dev/pytest` | Python | 7 | 0.1584 | 0.1584 | 0.1584 | +0.0000 |
| `python/mypy` | Python | 1 | 0.0192 | 0.0192 | 0.0192 | +0.0000 |
| `scrapy/scrapy` | Python | 3 | 0.0364 | 0.0364 | 0.0364 | +0.0000 |
| `spring-projects/spring-boot` | Other | 8 | 0.2365 | 0.2365 | 0.2365 | +0.0000 |
| `tokio-rs/tokio` | Other | 38 | 0.1989 | 0.1989 | 0.1989 | +0.0000 |
| `tox-dev/tox` | Python | 2 | 0.0675 | 0.0675 | 0.0675 | +0.0000 |
| `vitejs/vite` | Other | 25 | 0.0432 | 0.0432 | 0.0432 | +0.0000 |
| `vuejs/core` | Other | 6 | 0.0631 | 0.0631 | 0.0631 | +0.0000 |
