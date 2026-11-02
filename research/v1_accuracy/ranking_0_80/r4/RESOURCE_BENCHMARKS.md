# RepoNeedle — Phase R4: Resource & Computational Benchmarks

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R4 — Dense Semantic + Multi-Hop Structural Retrieval  
**Date**: November 2, 2026  
**Status**: Authoritative Computational Profile  

---

## 1. Executive Summary

A core requirement of the RepoNeedle project is **lightweight, CPU-first, zero-GPU execution**. Ranking improvements must not be achieved by introducing heavy deep learning frameworks (PyTorch, ONNX) or excessive memory footprints that would prevent RepoNeedle from running as a fast local CLI tool or inside restricted developer sandbox environments.

This report documents the empirical compute, memory, disk, and latency benchmarks measured directly on physical repository corpora.

---

## 2. Experimental Corpus Specification

Benchmarks were measured on the reference repository snapshot `clap-rs`:
- **Document Count**: 422 files
- **Total Uncompressed Source Size**: 3.41 MB
- **Language**: Rust
- **Hardware Profile**: Standard x86_64 CPU core (Windows PowerShell environment), Single-threaded execution, Zero GPU acceleration.

---

## 3. Subsystem Resource Profiles

### 3.1 Dense Semantic Engine (`DenseSemanticEngine`)

The dense semantic engine uses Latent Semantic Indexing (LSI) with Truncated SVD ($d=128$) over subword n-gram TF-IDF matrices:

| Resource Metric | Measured Value | Production Target / Budget | Status |
| :--- | :---: | :---: | :---: |
| **Offline Indexing Time** | **20.62 s** | $< 60\text{ s}$ per repository | **PASSED** |
| **Indexing Throughput** | **20.46 docs/sec** | $> 10\text{ docs/sec}$ | **PASSED** |
| **Peak Memory Allocation** | **75.07 MB** | $< 250\text{ MB}$ | **PASSED** |
| **Total Index Storage** | **7,711 KB** ($\approx 7.5\text{ MB}$) | $< 50\text{ MB}$ | **PASSED** |
| **Storage per Document** | **18.71 KB / doc** | $< 50\text{ KB / doc}$ | **PASSED** |
| **Query Latency (Mean)** | **0.672 ms** | $< 5.0\text{ ms}$ | **PASSED** |
| **Query Latency (P50)** | **0.658 ms** | $< 3.0\text{ ms}$ | **PASSED** |
| **Query Latency (P95)** | **0.916 ms** | $< 10.0\text{ ms}$ | **PASSED** |

### 3.2 Multi-Hop Call-Graph Engine (`MultiHopGraphEngine`)

The structural engine extracts file dependencies and performs 2-hop BFS path expansion with hub dampening:

| Resource Metric | Measured Value | Production Target / Budget | Status |
| :--- | :---: | :---: | :---: |
| **Graph Construction Time** | **0.975 s** | $< 5.0\text{ s}$ per repository | **PASSED** |
| **Construction Throughput** | **432.89 docs/sec** | $> 100\text{ docs/sec}$ | **PASSED** |
| **Peak Memory Allocation** | **4.32 MB** | $< 50\text{ MB}$ | **PASSED** |
| **Topology** | **422 nodes, 23 edges** | Scales linearly with code size | **PASSED** |
| **2-Hop Traversal (Mean)** | **0.016 ms** (16 $\mu$s) | $< 1.0\text{ ms}$ | **PASSED** |
| **2-Hop Traversal (P50)** | **0.015 ms** (15 $\mu$s) | $< 0.5\text{ ms}$ | **PASSED** |
| **2-Hop Traversal (P95)** | **0.017 ms** (17 $\mu$s) | $< 2.0\text{ ms}$ | **PASSED** |

---

## 4. End-to-End Query Latency Across R4 Treatments

Evaluating total query execution time (lexical retrieval + candidate scoring + semantic projection + graph expansion + ranking):

| Treatment Code | Treatment Name | Mean Latency (ms) | P50 (ms) | P95 (ms) | CPU Utilization |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **A** | Frozen R2 Baseline | 11.65 ms | 3.22 ms | 28.73 ms | 1 core |
| **B** | Dense Alone | 9.30 ms | 3.05 ms | 29.44 ms | 1 core |
| **C** | Graph Alone | 10.43 ms | 3.04 ms | 28.35 ms | 1 core |
| **D** | **R2 + Dense Retrieval** | **9.74 ms** | **3.53 ms** | **30.03 ms** | **1 core** |
| **E** | R2 + Graph Retrieval | 12.46 ms | 3.21 ms | 56.99 ms | 1 core |
| **F** | Dense + Graph | 23.12 ms | 7.64 ms | 73.37 ms | 1 core |
| **G** | R2 + Dense + Graph | 22.10 ms | 7.53 ms | 73.22 ms | 1 core |
| **H** | **Calibrated Hybrid Fusion** | **22.34 ms** | **6.41 ms** | **72.50 ms** | **1 core** |

---

## 5. Architectural Compliance Verdict

1. **Memory Ceiling**: At peak execution, dense SVD indexing consumes **75.1 MB RAM**, and graph indexing consumes **4.3 MB RAM**. Total combined working memory remains well below the strict **250 MB** local environment budget.
2. **Interactive SLA**: At **9.74 ms** mean query latency for Treatment D and **22.34 ms** for Treatment H, both architectures comfortably satisfy the **< 100 ms** interactive response SLA for developer tools.
3. **Storage Overhead**: An index footprint of **18.7 KB / doc** means a typical repository of 2,000 files requires less than **38 MB** of index storage, which is readily cacheable in memory or on local disk.
4. **Hardware Independence**: The entire implementation relies exclusively on `numpy` and `scipy.sparse.linalg`, requiring zero CUDA, GPU, or neural runtime dependencies.

