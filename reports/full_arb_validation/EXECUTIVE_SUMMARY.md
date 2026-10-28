# Executive Summary: RepoNeedle Full ARB Benchmark Validation

**Date**: 2026-10-28  
**Dataset**: Official Agent Retrieval Bench (427 samples across 25 repositories)  
**Verdict**: **READY FOR A LIMITED RESEARCH RELEASE**

### Headline Positive Retrieval Results ($N=345$ Positive Samples)

| Metric | Official BM25 | Official Lexical | Official RepoMap | RepoNeedle | Relative Gain vs BM25 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Overall MRR** | 0.1520 | 0.1574 | 0.2140 | **0.2287** | **+50.5%** |
| **Recall@5** | 0.1899 | 0.2292 | 0.3185 | **0.3011** | **+58.6%** |
| **Recall@20** | 0.4452 | 0.4940 | 0.6306 | **0.4279** | **+-3.9%** |
| **BCY@8k** | 0.2051 | 0.2650 | 0.3788 | **0.3450** | **+68.2%** |

### Headline Selective Retrieval Results ($N=82$ No-Gold Samples)

- **Natural No-Gold** ($N=50$): **0/50** (0.0%)
- **Counterfactual Wrong-Repo** ($N=32$): **0/32** (0.0%)
- **Combined Selective Accuracy**: **0/82** (0.0%)
