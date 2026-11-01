# RepoNeedle Stage 3.7.1: Step-by-Step Reproduction Guide

**Document ID**: `STAGE3-7-1-REPRO-001`  
**Stage**: Stage 3.7.1 — Statistical Validation, Component Attribution & Research Integrity  
**Date**: November 1, 2026  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research/stage3_7`  

---

## 1. Environment Verification

Ensure Python 3.12 and required dependencies are available:

```powershell
python -c "import sys, numpy, scipy, networkx, pytest; print('Python:', sys.version.split()[0], '| NumPy:', numpy.__version__, '| SciPy:', scipy.__version__, '| NetworkX:', networkx.__version__, '| Pytest:', pytest.__version__)"
```

Verify immutable baseline tags:
```powershell
git rev-parse "v0.1.0-baseline^{commit}" "stage3-candidate-freeze^{commit}"
```
Expected output:
```
8e0042553a14b6e3c6cf5b35823c4da84181a8e9
cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 2. Component Attribution & Drop-One Ablations

To execute the controlled drop-one matrix (EXP-378 through EXP-383) across all $N=345$ positive ARB v2 samples:

```powershell
python research/stage3_7_1/scripts/run_component_attribution.py
```
- **Generated Deliverables**:
  - `research/stage3_7_1/COMPONENT_ATTRIBUTION_RESULTS.csv`
  - `research/stage3_7_1/PER_QUERY_RESULTS.jsonl` (345 query records with complete multi-system dictionaries)
  - `research/stage3_7_1/EXPERIMENT_REGISTRY.jsonl`

---

## 3. Multi-Scale Runtime & Memory Verification

To measure isolated runtime latency, index time, graph build, heap, and working set RSS across both medium-scale and realistic 2,000-file benchmark scale:

```powershell
python research/stage3_7_1/scripts/run_runtime_verification.py
```
- **Generated Deliverable**:
  - `research/stage3_7_1/RUNTIME_VERIFICATION.csv`

---

## 4. Run Test Suite

Verify all unit and regression tests pass with 100% compliance:

```powershell
pytest tests/ -v
```
Expected output: 244 passed.

