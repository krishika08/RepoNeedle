# RepoNeedle Stage 3.6 — Reproduction Guide

**Document ID**: `STAGE3.6-REPRO-001`  
**Date**: October 2026  
**Target Branch**: `research-program`  
**Target Commit**: Current HEAD on `research-program`  
**Python Version**: Python 3.10+ (tested on Windows 10/11 x64)

This guide provides clean, copy-pasteable PowerShell commands to reproduce every finding, benchmark result, statistical test, context packing analysis, and runtime/memory audit conducted in RepoNeedle Stage 3.6.

---

## 1. Environment & Prerequisites

### 1.1 Python Dependencies
Ensure the current virtual environment has all required dependencies installed:
```powershell
pip install pytest networkx scipy numpy pathspec
```

### 1.2 Working Directory
Always execute commands from the repository root:
```powershell
cd F:\RepoNeedle
```

---

## 2. Step-by-Step Execution Pipeline

### Step 1: Git Status & Frozen Baseline Integrity Verification
Verify that immutable Git tags and baseline trees are untouched:
```powershell
# 1. Verify frozen baseline tag
git rev-parse "v0.1.0-baseline^{commit}"
# Expected: 8e0042539cf9e585f52a7920dc7ca81155aa51c6

# 2. Verify frozen candidate freeze tag
git rev-parse "stage3-candidate-freeze^{commit}"
# Expected: cd7f3b0606ec040974cf978c4391264b38d38407

# 3. Check current branch
git branch --show-current
# Expected: research-program
```

### Step 2: Run Unit Test Suite
Verify that all unit tests pass (100% test pass rate):
```powershell
python -m pytest tests/ -v
# Expected: 50 passed in ~3.2 seconds
```

### Step 3: Run Graph Audit & Manifest Resolution Unit Tests
Verify that the excised hardcoded bypasses remain removed and polyglot graph resolution tests pass:
```powershell
python -m pytest tests/test_graph.py -v
# Expected: 8 passed (Cargo manifests, Go mod, package.json, Rust submodules, edge deduplication)
```

### Step 4: Run Unified Four-System Benchmark Evaluation (N=345 ARB v2 Samples)
Executes all four retrieval systems (`BASE-BM25`, `CAND-C`, `CAND-F`, `BASE-REPOMAP`) under one unified evaluation contract across all 345 positive benchmark samples:
```powershell
python -u -W ignore research\stage3_6\evaluate_systems.py
```
- **Output Artifact**: `research/stage3_6/PER_QUERY_RESULTS.csv` (1,380 query-system observations)
- **Expected Runtime**: ~12–18 minutes (depending on CPU throughput on large repositories like `huggingface/transformers`).

### Step 5: Compute Paired Statistical Significance & Confidence Intervals
Reads `PER_QUERY_RESULTS.csv` and executes 10,000 repository-clustered bootstrap resamples, paired $t$-tests, Wilcoxon signed-rank tests, and per-task / per-language breakdowns:
```powershell
python -u research\stage3_6\compute_paired_statistics.py
```
- **Output Artifact**: `research/stage3_6/PAIRED_STATISTICS.md`
- **Expected Runtime**: ~15–20 seconds.

### Step 6: Controlled Context Packing & Budget Saturation Isolation Audit
Evaluates context packing policies across 4k, 8k, and 16k token budgets on representative codebases (`pallets/click`, `caddyserver/caddy`, `tokio-rs/tokio`):
```powershell
python -u -W ignore research\stage3_6\audit_context_packing.py
```
- **Output Artifacts**:
  - `research/stage3_6/CONTEXT_PACKING_PER_QUERY.csv`
  - `research/stage3_6/CONTEXT_PACKING_RESULTS.csv`
- **Expected Runtime**: ~45–60 seconds.

### Step 7: Runtime, Latency, and Process Memory (PSAPI RSS) Audit
Measures index build time, retained heap delta, process baseline/retained/peak RSS via `K32GetProcessMemoryInfo`, and cold/p50/p95 latency across Micro, Medium, and Large repository scales:
```powershell
python -u -W ignore research\stage3_6\audit_runtime_and_memory.py
```
- **Output Artifact**: `research/stage3_6/RUNTIME_MEMORY_RESULTS.csv`
- **Expected Runtime**: ~30–45 seconds.

---

## 3. Artifact Checksum Verification

After running the pipeline, verify file integrity using PowerShell `Get-FileHash`:
```powershell
Get-FileHash research\stage3_6\* | Format-Table Algorithm, Hash, Path
```
All artifacts should match their expected structure, line counts, and verified SHA-256 checksums:

| Artifact Path | Line Count | SHA-256 Checksum |
| :--- | :---: | :--- |
| 
esearch/stage3_6/PER_QUERY_RESULTS.csv | 1,381 | 1311ee12001be7001f645532304e8b1bedd5663f82ab85d57a57c39d792a5007 |
| 
esearch/stage3_6/PAIRED_STATISTICS.md | 141 | 62bcb8dc3c1bc6d68f922b51c0f8b7459377e01e8dfbc6ea77678c59c57abdb |
| 
esearch/stage3_6/CONTEXT_PACKING_PER_QUERY.csv | 1,156 | 3527ac6325fb8bc503138292f680b22d1fe70533be02d2837ab992898948ae48 |
| 
esearch/stage3_6/CONTEXT_PACKING_RESULTS.csv | 16 | 3e31d0dccfcad9e9f86db7f4ed2db576b0ea269097fbdb847cc3b485795e0dff |
| 
esearch/stage3_6/RUNTIME_MEMORY_RESULTS.csv | 13 | f763eca98bc94e1fbf31675a0c86c18da07a7ab99341917aca54838f5f73379 |
| 
esearch/stage3_6/DECISION_REPORT.md | 82 | 45a7c94c88a18887371b8c7838f821bcd86f3b00e6a97e7f1add32dc30039ffd |
| 
esearch/stage3_6/REPRODUCIBILITY_REPORT.md | 85 | c4f963ea1d1fb308807946f3e9bcd3d17b3b57833b44ff31262620d6bf9fd600 |
| 
esearch/stage3_6/GRAPH_AUDIT.md | 127 | 5a17a7474264beb46a8e81bc12e490e688c5a656d59b70284fd325bd65f324a |
| 
esearch/stage3_6/FAILURE_ANALYSIS.md | 108 | 1e3d086438fe01b4ecdd94f32cd82ce81c2bfe9d0cd58af425427a844b4d7661 |
| 
esearch/stage3_6/EXPERIMENT_REGISTRY.jsonl | 7 | 189128193b2857d4e578f28d4e13601a52805272dc117c824fe60d10dabedd02 |
