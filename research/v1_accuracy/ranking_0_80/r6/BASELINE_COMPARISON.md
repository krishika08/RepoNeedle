# RepoNeedle — Phase R6: Baseline Comparison Report

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R6 — Independent Benchmark & Generalization Research  
**Author**: Search Relevance Engineer & Principal IR Researcher  
**Date**: November 2, 2026  
**Status**: Formal Multi-Treatment Baseline Audit  

---

## 1. Executive Summary

Phase R6 benchmarks RepoNeedle's ranking performance across an independent cohort of **18 previously unexamined repositories** (9 Train, 4 Validation, 5 Held-Out; total $N=180$ queries).

This report presents a controlled comparison across the historical baselines and newly formulated treatments:
- **Treatment A**: Original V1 Baseline (Raw BM25 / lexical scoring)
- **Treatment B**: R2 Treatment E (Seed File Suppression + Test Intent Prior)
- **Treatment C**: R4 Treatment D (Dense Semantic Subword Alignment + Multi-Hop Structural)
- **Treatment D**: R5 Treatment F (Full Typed Change-Impact Retrieval)
- **Treatment E**: R5 Without Heuristic Edges (Ablated directory proximity, test stem, doc match)
- **Treatment F**: R5 With Verified Graph Relationships Only (AST calls, imports, symbols, build)
- **Treatment G**: R5 With Confidence-Calibrated Relationship Evidence (Bayesian confidence propagation)
- **Treatment H**: Best Combined Model (Calibrated Impact + Verified Symbols + TIP)

---

## 2. Multi-Treatment Performance Comparison

### 2.1 Validation Partition ($N=40$ Queries, 4 Independent Repositories)

| Treatment | Architecture / Features | MRR | Hit@1 | Recall@5 | Recall@10 | Recall@20 | Candidate Recall | Latency (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A** | Original V1.0.0 (Lexical BM25) | 0.4931 | 25.00% | 0.8250 | 0.9000 | 0.9125 | 100.0% | 0.110 |
| **B** | R2 Treatment E (SFS + TIP) | 0.6472 | 50.00% | 0.8250 | 0.9125 | 0.9125 | 100.0% | 0.119 |
| **C** | R4 Treatment D (Dense Semantic) | 0.6306 | 47.50% | 0.8250 | 0.9125 | 0.9125 | 100.0% | 0.123 |
| **D** | R5 Treatment F (Typed Change-Impact) | **0.6708** | **50.00%** | **0.8250** | **0.9125** | **1.0000** | **100.0%** | 0.718 |
| **E** | R5 Without Heuristics | **0.6708** | **50.00%** | **0.8250** | **0.9125** | **1.0000** | **100.0%** | 0.718 |
| **F** | R5 Verified Edges Only | **0.6708** | **50.00%** | **0.8250** | **0.9125** | **1.0000** | **100.0%** | 0.724 |
| **G** | Confidence-Calibrated Impact | **0.6708** | **50.00%** | **0.8250** | **0.9125** | **1.0000** | **100.0%** | 0.686 |
| **H** | Best Combined Model | **0.6708** | **50.00%** | **0.8250** | **0.9125** | **1.0000** | **100.0%** | 0.705 |

### 2.2 Relative Gain vs Authoritative Reference (Treatment B)

On the independent validation set:
- **Treatment D $\Delta \text{MRR}$**: $+0.0236$ (+3.65% relative gain)
- **Treatment D $\Delta \text{Recall@20}$**: $+0.0875$ (+9.59% relative gain, reaching 100.0% gold target recall)
- **Candidate Recall**: 100.0% preserved across all treatments.
- **CPU Latency**: 0.718 ms (well below 10 ms SLA).

---

## 3. Analysis of Baseline Limitations

1. **Failure of Raw BM25 (Treatment A)**:
   - On queries with anchor or seed files provided in the developer prompt, raw BM25 ranks the seed file at rank 1 due to word overlap, while the true target file (e.g. regression test or downstream caller) is pushed down.
   - MRR on Treatment A is limited to 0.4931 on Validation and 0.4194 on Held-Out.
2. **Impact of Seed File Suppression (Treatment B)**:
   - SFS immediately suppresses anchor files, elevating target files into the top ranks and lifting MRR from 0.4931 to 0.6472 (+15.41 points).
3. **Superiority of Structural Graph Guidance (Treatments D–H)**:
   - Typed change-impact edges bridge the lexical gap between implementation files and their tests/callers, elevating recall at rank 20 from 91.25% to **100.0%** with zero target loss.

