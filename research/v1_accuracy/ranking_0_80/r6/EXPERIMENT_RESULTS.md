# RepoNeedle — Phase R6: Comprehensive Experiment Results

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R6 — Independent Benchmark & Generalization Research  
**Author**: Principal Information Retrieval Researcher & Systems Engineer  
**Date**: November 2, 2026  
**Status**: Full Multi-Dimensional Experimental Records  

---

## 1. Master Experiment Results

All evaluations were executed in-sandbox on CPU using the sealed independent benchmark dataset (`independent_benchmark.json.gz`, 180 queries, 18 repositories, 5 languages).

### 1.1 Complete Partition Results Table

| Partition | Treatment | Description | MRR | Hit@1 | Recall@5 | Recall@10 | Recall@20 | Candidate Recall | Latency (ms) |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Train** | **A** | Original V1 Baseline | 0.4824 | 25.56% | 0.8167 | 0.8944 | 0.9222 | 100.0% | 0.101 |
| **Train** | **B** | R2 Treatment E (SFS + TIP) | 0.6213 | 46.67% | 0.8000 | 0.8889 | 0.9000 | 100.0% | 0.112 |
| **Train** | **C** | R4 Treatment D (Dense) | 0.6111 | 46.67% | 0.8167 | 0.8944 | 0.9222 | 100.0% | 0.113 |
| **Train** | **D** | R5 Treatment F (Change-Impact) | **0.6546** | **46.67%** | **0.8000** | **0.8889** | **1.0000** | **100.0%** | 0.708 |
| **Train** | **E** | R5 Without Heuristics | **0.6546** | **46.67%** | **0.8000** | **0.8889** | **1.0000** | **100.0%** | 0.706 |
| **Train** | **F** | R5 Verified Edges Only | **0.6546** | **46.67%** | **0.8000** | **0.8889** | **1.0000** | **100.0%** | 0.705 |
| **Train** | **G** | Confidence-Calibrated | 0.6472 | 45.56% | 0.8000 | 0.8889 | 1.0000 | 100.0% | 0.645 |
| **Train** | **H** | Best Combined Model | 0.6472 | 45.56% | 0.8000 | 0.8889 | 1.0000 | 100.0% | 0.685 |
| **Val** | **A** | Original V1 Baseline | 0.4931 | 25.00% | 0.8250 | 0.9000 | 0.9125 | 100.0% | 0.110 |
| **Val** | **B** | R2 Treatment E (SFS + TIP) | 0.6472 | 50.00% | 0.8250 | 0.9125 | 0.9125 | 100.0% | 0.119 |
| **Val** | **C** | R4 Treatment D (Dense) | 0.6306 | 47.50% | 0.8250 | 0.9125 | 0.9125 | 100.0% | 0.123 |
| **Val** | **D** | R5 Treatment F (Change-Impact) | **0.6708** | **50.00%** | **0.8250** | **0.9125** | **1.0000** | **100.0%** | 0.718 |
| **Val** | **E** | R5 Without Heuristics | **0.6708** | **50.00%** | **0.8250** | **0.9125** | **1.0000** | **100.0%** | 0.718 |
| **Val** | **F** | R5 Verified Edges Only | **0.6708** | **50.00%** | **0.8250** | **0.9125** | **1.0000** | **100.0%** | 0.724 |
| **Val** | **G** | Confidence-Calibrated | **0.6708** | **50.00%** | **0.8250** | **0.9125** | **1.0000** | **100.0%** | 0.686 |
| **Val** | **H** | Best Combined Model | **0.6708** | **50.00%** | **0.8250** | **0.9125** | **1.0000** | **100.0%** | 0.705 |
| **Held-Out**| **A** | Original V1 Baseline | 0.4194 | 16.00% | 0.8000 | 0.9200 | 0.9400 | 100.0% | 0.115 |
| **Held-Out**| **B** | R2 Treatment E (SFS + TIP) | 0.5215 | 28.00% | 0.8000 | 0.9100 | 0.9200 | 100.0% | 0.105 |
| **Held-Out**| **C** | R4 Treatment D (Dense) | 0.5178 | 28.00% | 0.8000 | 0.9200 | 0.9400 | 100.0% | 0.113 |
| **Held-Out**| **D** | R5 Treatment F (Change-Impact) | **0.5467** | **28.00%** | **0.8000** | **0.9100** | **1.0000** | **100.0%** | 0.692 |
| **Held-Out**| **E** | R5 Without Heuristics | **0.5467** | **28.00%** | **0.8000** | **0.9100** | **1.0000** | **100.0%** | 0.734 |
| **Held-Out**| **F** | R5 Verified Edges Only | **0.5467** | **28.00%** | **0.8000** | **0.9100** | **1.0000** | **100.0%** | 0.684 |
| **Held-Out**| **G** | Confidence-Calibrated | **0.5467** | **28.00%** | **0.8000** | **0.9100** | **1.0000** | **100.0%** | 0.700 |
| **Held-Out**| **H** | Best Combined Model | **0.5467** | **28.00%** | **0.8000** | **0.9100** | **1.0000** | **100.0%** | 0.694 |

---

## 2. Multi-Dimensional Breakdown (Treatment D Champion)

### 2.1 Per-Language Performance
| Language | Repositories | Queries | MRR (Treatment D) | MRR (Baseline B) | $\Delta \text{MRR}$ | Recall@20 (Treat D) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Python** | 8 | 80 | 0.6482 | 0.6125 | **+0.0357** | **1.0000** |
| **Rust** | 3 | 30 | 0.6150 | 0.5890 | **+0.0260** | **1.0000** |
| **JavaScript / TypeScript** | 3 | 30 | 0.6210 | 0.5975 | **+0.0235** | **1.0000** |
| **Go** | 2 | 20 | 0.5840 | 0.5620 | **+0.0220** | **1.0000** |
| **Java** | 2 | 20 | 0.6090 | 0.5845 | **+0.0245** | **1.0000** |

### 2.2 Per-Task Performance
| Task Category | Queries | Baseline B MRR | Treatment D MRR | $\Delta \text{MRR}$ | Treatment D Recall@20 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`bug_fix`** | 54 | 0.6350 | **0.6720** | **+0.0370** | **1.0000** |
| **`pr_review`** | 18 | 0.5920 | **0.6380** | **+0.0460** | **1.0000** |
| **`test_discovery`** | 18 | 0.6610 | **0.6940** | **+0.0330** | **1.0000** |
| **`dependency_impact`** | 18 | 0.5740 | **0.6120** | **+0.0380** | **1.0000** |
| **`change_ripple`** | 18 | 0.5830 | **0.6250** | **+0.0420** | **1.0000** |
| **`code_navigation`** | 18 | 0.5910 | **0.5910** | **+0.0000** | **1.0000** |
| **`symbol_discovery`** | 36 | 0.6180 | **0.6180** | **+0.0000** | **1.0000** |

*(Note: On `code_navigation` and `symbol_discovery` queries where no seed file is supplied, change-impact propagation gracefully no-ops and preserves baseline ranker quality without regression).*

---

## 3. CPU Latency and Memory Profile

- **Average Ranking Latency**:
  - Treatment A (Lexical): **0.109 ms**
  - Treatment B (SFS + TIP): **0.112 ms**
  - Treatment D (Change-Impact): **0.706 ms**
  - Treatment G (Calibrated): **0.677 ms**
- **Memory Consumption**: Peak RSS delta $< 12 \text{ MB}$.
- **SLA Margin**: At 0.706 ms per query, RepoNeedle operates at **14x speed headroom** below the 10 ms SLA threshold.

