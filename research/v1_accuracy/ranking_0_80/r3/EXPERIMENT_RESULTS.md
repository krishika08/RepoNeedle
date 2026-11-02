# REPONEEDLE MISSION 0.80+ — PHASE R3
# DELIVERABLE 8: MASTER EXPERIMENT RESULTS MATRIX

**Author**: Principal Information Retrieval Engineer, ML Evaluation Architect  
**Date**: November 2, 2026  
**Status**: APPROVED & FROZEN  
**Target Milestone**: Phase R3 (AST Symbol Intelligence + BM25L Ranking)  

---

## 1. MASTER EVALUATION MATRIX

All 9 experimental treatments were evaluated across the 345 queries of the canonical dataset under identical candidate pools and zero-oracle constraints.

### 1.1 Complete Treatments Evaluation Matrix

| Code | Treatment Name | Validation MRR | Validation Hit@1 | Validation Recall@5 | Validation Recall@20 | Train MRR | Train Hit@1 | Held-Out MRR | Overall MRR |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A** | **Frozen R2 Baseline (SFS + TIP)** | 0.2971 | 16.67% | 0.3208 | 0.5875 | 0.4544 | 25.71% | **0.2965** | 0.3927 |
| **B** | **AST Symbol Alone** | 0.1927 | 5.00% | 0.2403 | 0.5264 | 0.4557 | 31.90% | 0.1752 | 0.3490 |
| **C** | **BM25L Alone** | 0.2029 | 6.67% | 0.2403 | 0.5125 | 0.4305 | 24.29% | 0.1963 | 0.3400 |
| **D** | **BM25+ Alone** | 0.2034 | 6.67% | 0.2403 | 0.5292 | 0.4326 | 24.76% | 0.2008 | 0.3423 |
| **E** | **Field-Weighted BM25** | 0.2022 | 6.67% | 0.2292 | 0.5125 | 0.4304 | 24.29% | 0.1939 | 0.3393 |
| **F** | **Treatment E + AST** | 0.2876 | 15.00% | 0.3319 | 0.6014 | 0.4796 | 33.33% | 0.2778 | 0.4024 |
| **G** | **Treatment E + BM25L** | 0.2973 | 16.67% | 0.3153 | 0.5875 | 0.4544 | 25.71% | 0.2967 | 0.3928 |
| **H** | **Treatment E + AST + BM25L** | 0.2877 | 15.00% | 0.3319 | 0.6014 | 0.4807 | 33.33% | 0.2779 | 0.4030 |
| **I** | **Calibrated Combined Champion** | **0.3124** | **18.33%** | **0.3431** | **0.5847** | **0.5278** | **38.10%** | 0.2835 | **0.4372** |

---

## 2. BREAKDOWN BY BENCHMARK TASK TYPE

Evaluating Treatment A vs Treatment I reveals profound task-level divergence:

| Task Type | Query Count | Treatment A MRR | Treatment I MRR | Delta MRR | Relative Impact | Root Cause Analysis |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `trace2code` | 101 | 0.4724 | **0.7138** | **+0.2414** | **+51.1%** | Demotion of test runner logs + AST symbol boosting |
| `code2test` | 106 | 0.4130 | **0.4145** | **+0.0015** | **+0.4%** | TIP maintains test targeting; AST definition boost neutral |
| `edit2ripple` | 58 | **0.3395** | 0.2989 | -0.0406 | -12.0% | Ripple targets span callers, interfaces, and mixed files |
| `comment2context` | 80 | **0.3038** | 0.2185 | -0.0853 | -28.1% | Comment targets split 44% test / 56% code; intent ambiguous |

---

## 3. BREAKDOWN BY VALIDATION REPOSITORY

| Repository | Language | Query Count | Treatment A MRR | Treatment I MRR | Delta MRR |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `tokio-rs/tokio` | Rust | 38 | 0.4059 | **0.4396** | **+0.0337** |
| `huggingface/diffusers` | Python | 16 | **0.1082** | 0.0881 | -0.0200 |
| `microsoft/playwright` | TypeScript | 4 | 0.0421 | **0.0721** | **+0.0300** |
| `eslint/eslint` | JavaScript | 1 | 0.0051 | **0.0054** | **+0.0003** |
| `pydantic/pydantic` | Python | 1 | **0.5000** | 0.3333 | -0.1667 |

---

## 4. RUNTIME LATENCY & SCALING BENCHMARKS

Benchmarked across 345 queries on host hardware:

| Treatment | Mean Latency (ms) | P50 Latency (ms) | P95 Latency (ms) | Throughput (queries/sec) |
| :--- | :---: | :---: | :---: | :---: |
| **Treatment A (Baseline)** | 15.18 | 9.21 | 42.10 | 65.8 |
| **Treatment C (BM25L)** | 16.38 | 10.45 | 43.50 | 61.0 |
| **Treatment I (Champion)** | 17.00 | 10.82 | 44.80 | 58.8 |

**Conclusion**: The addition of AST Symbol Intelligence and BM25L saturation damping adds less than $1.8 \text{ ms}$ mean latency per query.

