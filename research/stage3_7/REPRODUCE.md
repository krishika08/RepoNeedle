# Reproduction Guide: Stage 3.7 Failure Deconstruction & Controlled Component Isolation

**Document ID**: `STAGE3-7-REPRO-002`
**Stage**: Stage 3.7 — Retrieval Failure Deconstruction & Controlled Component Isolation
**Date**: October 31, 2026
**Status**: Step-by-Step Verifiable Reproduction Guide
**Workspace**: `F:\RepoNeedle`
**Branch**: `research/stage3_7`

---

## 1. Environment Verification

Ensure the runtime environment is properly configured. From the root directory `F:\RepoNeedle`:

```powershell
python -c "import sys, numpy, scipy, pytest; print('Python:', sys.version.split()[0], '| NumPy:', numpy.__version__, '| SciPy:', scipy.__version__, '| Pytest:', pytest.__version__)"
```
- Expected Python: `>= 3.12`
- Expected Packages: `numpy >= 1.26`, `scipy >= 1.13`, `networkx >= 3.0`, `pytest >= 8.0`

Verify that the frozen immutable Git tags are intact:
```powershell
git rev-parse "v0.1.0-baseline^{commit}" "stage3-candidate-freeze^{commit}"
```
- Expected Commit Hashes:
  ```
  8e0042553a14b6e3c6cf5b35823c4da84181a8e9
  cd7f3b01e28695f9a9357e0815069e0eae85baca
  ```

---

## 2. BM25 Document-Length Inflation Audit

To audit the mathematical impact of polyglot symbol extraction on BM25 effective document lengths and ranking degradation:

```powershell
python research/stage3_7/scripts/audit_bm25_length.py
```
- **Generated File**: `research/stage3_7/BM25_LENGTH_DIAGNOSTICS.csv`
- **Expected Results**:
  - Pearson correlation between length inflation and rank degradation: $r \approx 0.4989$ ($p < 10^{-32}$)
  - Spearman rank correlation: $r \approx 0.6029$ ($p < 10^{-51}$)

---

## 3. Graph Hub Dilution & Score-Diffusion Diagnostics

To measure graph degree distributions, hub concentration, and directional score diffusion across all queries:

```powershell
python research/stage3_7/scripts/audit_graph_hubs.py
```
- **Generated Files**:
  - `research/stage3_7/GRAPH_HUB_DIAGNOSTICS.csv`
  - `research/stage3_7/GRAPH_DIFFUSION_RESULTS.csv`
- **Expected Results**:
  - Max node degree: up to 3,890.
  - Bidirectional diffusion degrades 44.4% of gold target files and improves only 21.8%.
  - Hub normalization ($1 / \sqrt{\text{degree}}$) improves 41.8% of degraded instances over raw diffusion.

---

## 4. Controlled 8-Experiment Matrix (EXP-371 to EXP-378)

To evaluate all 8 controlled configurations under the unconstrained candidate-generation protocol across all $N=345$ positive ARB v2 samples:

```powershell
python research/stage3_7/scripts/evaluate_experiment_matrix.py
```
- **Generated Files**:
  - `research/stage3_7/RANKING_RESULTS.csv`
  - `research/stage3_7/PER_QUERY_RESULTS.jsonl` (2,760 evaluated query records)
  - `research/stage3_7/EXPERIMENT_REGISTRY.jsonl`
- **Expected Aggregate Results**:
  - `EXP-371` (CAND-C): MRR = 0.1409, Recall@20 = 0.5143
  - `EXP-372` (CAND-F): MRR = 0.1351, Recall@20 = 0.5078
  - `EXP-373` (CAND-F-NO-DIFF): MRR = 0.1399, Recall@20 = 0.5105
  - `EXP-374` (CAND-F-DECOUPLED): MRR = 0.1358, Recall@20 = 0.5078
  - `EXP-375` (CAND-F-FWD-ONLY): MRR = 0.1314, Recall@20 = 0.4827
  - `EXP-376` (CAND-F-BWD-ONLY): MRR = 0.1427, Recall@20 = 0.5216
  - `EXP-377` (CAND-F-HUBNORM): MRR = 0.1427, Recall@20 = 0.5078
  - `EXP-378` (CAND-COMBINED): MRR = 0.2052, Recall@20 = 0.5508, Hit@20 = 0.6406

---

## 5. Statistical Hypothesis Testing & Resampling

To execute 10,000 repository-clustered bootstrap resamples and cluster-level paired tests:

```powershell
python research/stage3_7/scripts/compute_paired_statistics.py
```
- **Generated File**: `research/stage3_7/STATISTICAL_COMPARISON.md`
- **Expected Results**:
  - EXP-378 vs EXP-371 MRR diff: $+0.0642$ ($p_{\text{wilcoxon}} = 0.0024$, $p_{\text{ttest}} = 0.0250$).
  - Clustered wins/ties/losses: 279 / 16 / 50.

---

## 6. Efficiency and Resource Benchmarking

To measure index build times, graph construction, latency percentiles, and memory RSS:

```powershell
python research/stage3_7/scripts/benchmark_runtime_and_memory.py
```
- **Generated File**: `research/stage3_7/RUNTIME_AND_MEMORY.csv`

---

## 7. Component Isolation Regression Tests

```powershell
pytest tests/test_stage3_7_component_isolation.py -v
```
- Expected: All tests pass.
