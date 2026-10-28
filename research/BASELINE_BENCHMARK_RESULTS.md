# BASELINE BENCHMARK RESULTS: AUDITED ARB v2 DATASET

**Document ID**: `BB-2026-001`  
**Evaluation Date**: 2026-10-28  
**Dataset**: Official Agent Retrieval Bench v2 (`eyuansu62/agent-retrieval-bench`, Commit `9e4d68937f29`)  
**Evaluator**: `agent_retrieval_bench` v0.2.1  
**Source Prediction Files**:
- Positive: [`reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl`](file:///F:/RepoNeedle/reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl) ($N=345$)
- Selective: [`reports/full_arb_validation/checkpoint_selective.jsonl`](file:///F:/RepoNeedle/reports/full_arb_validation/checkpoint_selective.jsonl) ($N=82$)

---

## 1. Verified Headline Metrics Across All Positive Samples ($N=345$)

Every metric below has been verified directly by independent re-calculation from raw prediction records on disk:

| System / Baseline | MRR | Recall@5 | Recall@10 | Recall@20 | BCY@4k | BCY@8k | BCY@16k | BCY@32k |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoNeedle (Baseline v0.1.0)** | **0.2287** | **0.3011** | **0.4110** | **0.4279** | **0.2436** | **0.3450** | **0.4192** | **0.4279** |
| **Official RepoMap** | 0.2140 | 0.3185 | 0.4786 | **0.6306** | 0.2024 | **0.3788** | **0.5235** | **0.6166** |
| **Official Lexical** | 0.1574 | 0.2292 | 0.3548 | 0.4940 | 0.1488 | 0.2650 | 0.3886 | 0.4882 |
| **Official BM25** | 0.1520 | 0.1899 | 0.3034 | 0.4452 | 0.1220 | 0.2051 | 0.3184 | 0.4365 |
| *Qwen3-Embedding-4B (Ext Ref)* | *0.2379* | *—* | *—* | *0.6306* | *—* | *0.3409* | *—* | *—* |
| *Qwen3-Embedding-8B (Ext Ref)* | *0.2336* | *—* | *—* | *0.7029* | *—* | *0.3732* | *—* | *—* |
| *pplx-embed-v1-4b (Ext Ref)* | *0.2267* | *—* | *—* | *0.6072* | *—* | *0.3549* | *—* | *—* |
| *jina-code-0.5b (Ext Ref)* | *0.1914* | *—* | *—* | *0.4823* | *—* | *0.2783* | *—* | *—* |

---

## 2. Matched Paired Statistical Tests (10,000 Bootstrap Resamples)

| Comparison | Mean Difference ($\Delta_{\text{MRR}}$) | Relative Gain | 95% Repo-Clustered CI | Paired $t$-test ($p$-val) | Wilcoxon $W$ ($p$-val) | Wins / Ties / Losses | Statistically Significant |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoNeedle vs BM25** | **+0.0767** | **+50.5%** | **[+0.0202, +0.1129]** | $t = 4.776$ ($p = 2.65\times 10^{-6}$) | $W = 22384.0$ ($p = 0.0096$) | 148 / 18 / 179 | **YES ($p < 0.01$)** |
| **RepoNeedle vs RepoMap** | **+0.0148** | **+6.9%** | **[-0.0466, +0.0619]** | $t = 0.827$ ($p = 0.4089$) | $W = 23821.5$ ($p = 0.3032$) | 122 / 26 / 197 | **NO (Parity in MRR)** |
| **RepoNeedle vs Lexical** | **+0.0713** | **+45.3%** | **[+0.0307, +0.1029]** | $t = 4.529$ ($p = 8.17\times 10^{-6}$) | $W = 22521.5$ ($p = 0.1215$) | 133 / 29 / 183 | **YES ($p < 0.001$)** |

---

## 3. Task Breakdown ($N=345$)

| Task Track | Sample Count ($N$) | Metric | Official BM25 | Official Lexical | Official RepoMap | RepoNeedle | Gain vs BM25 | Gain vs RepoMap |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`code2test`** | $N=106$ | **MRR** | 0.1057 | 0.0663 | 0.1942 | **0.2660** | **+151.7%** | **+37.0%** |
| | | Recall@5 | 0.1305 | 0.0676 | 0.2645 | **0.3918** | +200.2% | +48.1% |
| | | Recall@20 | 0.3066 | 0.2469 | 0.5572 | **0.5931** | +93.4% | +6.4% |
| | | **BCY@8k** | 0.1541 | 0.0928 | 0.3462 | **0.4814** | **+212.4%** | **+39.1%** |
| **`comment2context`** | $N=80$ | **MRR** | **0.1974** | 0.1530 | 0.1532 | 0.1708 | **-13.5%** | +11.5% |
| | | Recall@5 | **0.2146** | 0.1667 | 0.1750 | 0.1646 | -23.3% | -5.9% |
| | | Recall@20 | **0.5292** | 0.4979 | 0.4688 | 0.2083 | -60.6% | -55.6% |
| | | **BCY@8k** | 0.2604 | 0.2167 | **0.2792** | 0.1896 | -27.2% | -32.1% |
| **`trace2code`** | $N=101$ | **MRR** | 0.1638 | 0.2075 | **0.2723** | 0.2337 | +42.7% | **-14.2%** |
| | | Recall@5 | 0.2228 | 0.3432 | **0.4604** | 0.2855 | +28.1% | -38.0% |
| | | Recall@20 | 0.4934 | 0.6964 | **0.8465** | 0.4092 | -17.1% | -51.7% |
| | | **BCY@8k** | 0.1931 | 0.3795 | **0.5066** | 0.2954 | +53.0% | -41.7% |
| **`edit2ripple`** | $N=58$ | **MRR** | 0.1536 | **0.2428** | 0.2323 | 0.2320 | +51.0% | -0.1% |
| | | Recall@5 | 0.2069 | **0.4124** | 0.3678 | 0.3506 | +69.5% | -4.7% |
| | | Recall@20 | 0.4986 | 0.5876 | **0.6121** | 0.4612 | -7.5% | -24.7% |
| | | **BCY@8k** | 0.2428 | **0.4468** | 0.3534 | 0.3966 | +63.3% | +12.2% |

---

## 4. Selective Retrieval Baseline ($N=82$ Abstention Samples)

| Evaluation Track | Sample Count ($N$) | Correctly Abstained | Return Rate (False Positives) | Abstention Accuracy |
| :--- | :---: | :---: | :---: | :---: |
| **Natural No-Gold Issues** | 50 | 0 | 50 (100.0%) | **0.0%** |
| **Counterfactual Wrong-Repo** | 32 | 0 | 32 (100.0%) | **0.0%** |
| **Combined Selective Benchmark** | **82** | **0** | **82 (100.0%)** | **0.0%** |

---

## 5. Methodological Status of ARB v2

**Crucial Research Governance Principle**:  
Because ARB v2 has been inspected, diagnosed, and used to calibrate initial thresholds during the v0.1.0 cycle, **ARB v2 is formally designated as the existing development/regression benchmark**. 

Future architectural choices, hyperparameter adjustments, or model integrations tuned using ARB v2 must **not** claim unbiased generalization until tested on an independent, previously untouched held-out repository collection.

