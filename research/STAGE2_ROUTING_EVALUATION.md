# STAGE 2 TASK ROUTING EVALUATION & ARCHITECTURAL REPORT

**Document ID**: `STAGE2-ROUTING-001`  
**Evaluation Date**: 2026-10-28  
**Sample Count**: $N=345$ Positive Development Queries across 4 tracks  
**Scope**: Quantitative diagnosis of the autonomous router vs static fusion vs oracle routing.

## 1. Classification Performance of Current vs Improved Autonomous Router

### Current Keyword Router Confusion Matrix ($N=345$, Accuracy: 36.2%)

| Ground Truth \ Predicted | `code2test` | `comment2context` | `trace2code` | `edit2ripple` | Total | Class Recall |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`code2test`** | 22 | 70 | 4 | 10 | 106 | 20.8% |
| **`comment2context`** | 20 | 55 | 1 | 4 | 80 | 68.8% |
| **`trace2code`** | 59 | 0 | 42 | 0 | 101 | 41.6% |
| **`edit2ripple`** | 17 | 33 | 2 | 6 | 58 | 10.3% |

### Improved Pattern Router Confusion Matrix ($N=345$, Accuracy: 45.5%)

| Ground Truth \ Predicted | `code2test` | `comment2context` | `trace2code` | `edit2ripple` | Total | Class Recall |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`code2test`** | 32 | 71 | 3 | 0 | 106 | 30.2% |
| **`comment2context`** | 2 | 77 | 0 | 1 | 80 | 96.2% |
| **`trace2code`** | 2 | 51 | 48 | 0 | 101 | 47.5% |
| **`edit2ripple`** | 8 | 50 | 0 | 0 | 58 | 0.0% |

### Per-Task Classification Breakdown

| Task Track | True Count ($N$) | Current Precision | Current Recall | Current F1 | Improved Precision | Improved Recall | Improved F1 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`code2test`** | 106 | 18.6% | 20.8% | 0.20 | 72.7% | 30.2% | 0.43 |
| **`comment2context`** | 80 | 34.8% | 68.8% | 0.46 | 30.9% | 96.2% | 0.47 |
| **`trace2code`** | 101 | 85.7% | 41.6% | 0.56 | 94.1% | 47.5% | 0.63 |
| **`edit2ripple`** | 58 | 30.0% | 10.3% | 0.15 | 0.0% | 0.0% | 0.00 |

---

## 2. Downstream Retrieval Impact across the Three Explicit Protocols

As mandated by Stage 2 Governance, we distinguish three explicitly labeled regimes:

1. **ORACLE-ROUTING DIAGNOSTIC (Upper Bound)**: Ground-truth task type supplied at query time (Stage 1 pipeline).
2. **AUTONOMOUS-ROUTING EVALUATION (Practical Deployment)**: Task inferred from raw query text (EXP-002 full ranking).
3. **ROUTING-ABLATION EVALUATION (Fixed Static Fusion)**: Documented equal static fusion without routing (EXP-004 full ranking).

| Task Type | Sample Count ($N$) | Oracle Routing (Diag. Bound) | Autonomous Routing (`EXP-002`) | Routing Ablation (`EXP-004`) | Net Gain: Static vs Autonomous |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`code2test`** | 106 | 0.2660 | 0.1049 | 0.0760 | -0.0289 |
| **`comment2context`** | 80 | 0.1708 | 0.1370 | 0.1868 | **+0.0498** |
| **`trace2code`** | 101 | 0.2337 | 0.1116 | 0.2608 | **+0.1492** |
| **`edit2ripple`** | 58 | 0.2320 | 0.2351 | 0.2453 | **+0.0102** |
| **Overall Benchmark** | **345** | **0.2287** | **0.1362** | **0.1842** | **+0.0481 (+35.3%)** |

### Empirical Discoveries on Task Routing
1. **Static Equal Fusion Strongly Outperforms Autonomous Heuristic Routing**: Overall MRR improves from **0.1362** to **0.1842** (+35.2% relative gain) when the fragile keyword heuristic is disabled.
2. **Why Autonomous Heuristic Routing Degrades Retrieval**: When the keyword router misclassifies a query (e.g. classifying `trace2code` as `comment2context`, or applying frame boosts to non-existent file paths), it heavily penalizes lexical signals. Static fusion guarantees steady baseline term coverage regardless of query formatting.
3. **Oracle Diagnostic Confirms High Theoretical Ceiling**: If the task context is known a priori (e.g. when an agent explicitly calls a specialized tool `find_tests_for_code` or `find_trace_root_cause`), routing provides strong gains (MRR 0.2287). However, for a generic single-entrypoint retriever, static hybrid fusion is the superior architecture.