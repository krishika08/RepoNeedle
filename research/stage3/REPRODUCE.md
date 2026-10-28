# REPONEEDLE STAGE 3 DETERMINISTIC REPRODUCTION GUIDE

**Document ID**: `STAGE3-REPRODUCE-001`  
**Date**: 2026-10-28  
**Branch**: `research-program` | **Commit**: `cd7f3b0` | **Tag**: `stage3-candidate-freeze`  

---

## 1. Environment Verification

```powershell
# Ensure working tree is on research-program at frozen tag
git checkout stage3-candidate-freeze

# Verify Python version and dependencies
python -c "import numpy, scipy, networkx, pydantic, onnxruntime; print('Dependencies verified')"

# Run core unit and regression test suite (44/44 tests must pass)
pytest
```

---

## 2. Step-by-Step Reproduction Pipeline

### Step 1: Rebuild Independent Benchmark Suite
Generates `research/stage3/data/contextbench_suite.json`:
```powershell
python research/stage3/build_independent_benchmark.py
```

### Step 2: Execute ContextBench Independent Evaluation
Evaluates all 7 systems across held-out ($N=14$) and replication ($N=5$) partitions, outputting:
- `research/stage3/CONTEXTBENCH_RESULTS.csv`
- `research/stage3/PER_REPOSITORY_RESULTS.csv`
- `research/stage3/PER_SAMPLE_RESULTS.jsonl`
```powershell
python research/stage3/run_contextbench_evaluation.py
```

### Step 3: Run SWE-bench Lite Downstream Simulation
Evaluates coding agent tool-call count, prompt tokens, context sufficiency, and logs Docker infrastructure status:
- `research/stage3/SWE_BENCH_RESULTS.csv`
```powershell
python research/stage3/run_swe_bench_evaluation.py
```

### Step 4: Run Neural Track CPU Profiling
Benchmarks ONNX quantized dense embeddings, sparse-dense hybrid, and retrieve-and-rerank on CPU:
```powershell
python research/stage3/benchmark_neural_track.py
```

### Step 5: Evaluate Architectural Trade-Offs & Systems Costs
Measures skeleton caching acceleration, doc filtering sensitivity, memory footprint, and latency:
- `research/stage3/RUNTIME_AND_MEMORY.csv`
- `research/stage3/FAILURE_ANALYSIS.md`
```powershell
python research/stage3/evaluate_architectural_tradeoffs.py
```

### Step 6: Compute Statistical Significance & Bootstrap CIs
Calculates 10,000 repository-clustered bootstrap confidence intervals, paired $t$-tests, and Wilcoxon signed-rank tests:
- `research/stage3/STATISTICAL_ANALYSIS.md`
```powershell
python research/stage3/compute_statistical_analysis.py
```

