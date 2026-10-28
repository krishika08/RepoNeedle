# REPONEEDLE STAGE 3.2: COMPLETE REPRODUCTION GUIDE

**Document ID**: `STAGE3.2-REPRODUCE-001`  
**Date**: 2026-10-28  
**Scope**: Step-by-Step Deterministic Protocol for Reproducing All Stage 3.2 Evaluations, Statistics, and Benchmarks  

---

## 1. System Requirements & Environment Verification

### 1.1 Python Environment
- Python version: `Python 3.12+`
- Required Python packages: `pytest`, `numpy`, `scipy`, `pydantic`, `pyyaml`
- Standard libraries: `ctypes`, `tracemalloc`, `json`, `csv`, `pathlib`, `time`

### 1.2 Git State Verification
Verify the Git branch, HEAD commit, and frozen tags:

```powershell
# Verify branch
git branch --show-current
# Expected output: research-program

# Verify frozen candidate tag
git rev-parse stage3-candidate-freeze
# Expected output: cd7f3b0c8e37d5ff4b1ea27c0065b75ad4f71a9e

# Verify v0.1.0 baseline tag
git rev-parse v0.1.0-baseline
# Expected output: 8e00425a1b32d2948bbda1810416b0df470a273e
```

### 1.3 Baseline Unit & Regression Test Suite
Run the 44-test regression suite to verify system integrity:

```powershell
python -m pytest
```
**Expected Outcome**: `44 passed in ~3.5s` (100% passing).

---

## 2. Step-by-Step Reproduction Workflow

### Step 1: Run Candidate Retrieval Evaluation
Executes all 7 frozen systems (`BASE-BM25`, `BASE-REPOMAP`, `CAND-A`, `CAND-B`, `CAND-C`, `CAND-D`, `CAND-E`) across the 14 held-out repositories and 5 replication repositories under strictly matched 8,000-token budgets:

```powershell
python research/stage3_2/evaluate_candidates.py
```

**Artifacts Generated**:
- `research/stage3_2/CANDIDATE_EVALUATION.csv` (Aggregated candidate metrics across partitions)
- `research/stage3_2/PER_REPOSITORY_RESULTS.csv` (Per-repository breakdowns for all 7 systems)
- `research/stage3_2/PER_SAMPLE_RESULTS.jsonl` (Per-sample JSONL with full hit rankings and token usage)

---

### Step 2: Compute Statistical Significance & Clustered Bootstrap CIs
Computes paired $t$-tests and 10,000 clustered bootstrap iterations using fixed seed (`rng = np.random.default_rng(42)`):

```powershell
python research/stage3_2/generate_statistical_analysis.py
```

**Artifact Generated**:
- `research/stage3_2/STATISTICAL_ANALYSIS.md` (Verifies Candidate C vs BM25: $\Delta = +0.0357$, 95% CI $[0.0000, +0.1071]$, $p = 0.3356$).

---

### Step 3: Profile Multi-Scale Runtime Latency and Memory
Profiles cold/warm query latencies, Python heap (`tracemalloc`), and process working set (RSS via Windows `K32GetProcessMemoryInfo`) across synthetic micro, medium (`pallets/click`), and large (`caddyserver/caddy`) repositories:

```powershell
python research/stage3/audit_runtime_and_memory.py
```

**Artifact Generated**:
- `research/stage3_2/RUNTIME_AND_MEMORY.csv`

---

### Step 4: Verify Absence of Neural Model Artifacts
Verifies that no `.onnx` files exist in the repository or local cache:

```powershell
Get-ChildItem -Path F:\RepoNeedle -Recurse -Filter "*.onnx" -ErrorAction SilentlyContinue
Get-ChildItem -Path C:\Users\krish\.cache -Recurse -Filter "*.onnx" -ErrorAction SilentlyContinue
Get-ChildItem -Path C:\Users\krish\.gemini -Recurse -Filter "*.onnx" -ErrorAction SilentlyContinue
```
**Expected Output**: 0 files returned. Confirms `research/stage3_2/MODEL_ARTIFACT_VERIFICATION.md`.

---

### Step 5: Verify Host Container Engine Status
Inspects virtualization and container daemon availability:

```powershell
Get-Command docker -ErrorAction SilentlyContinue
Get-Command podman -ErrorAction SilentlyContinue
wsl -l -v
```
**Expected Output**: Commands fail with `CommandNotFoundException` or `The Windows Subsystem for Linux is not installed`. Confirms `research/stage3_2/SWE_BENCH_EXECUTION_REPORT.md`.

---

## 3. Directory Layout of Stage 3.2 Artifacts

```
research/stage3_2/
├── CANDIDATE_EVALUATION.csv          # Aggregate metrics for 7 frozen systems
├── DATASET_PROVENANCE.md             # Dataset distribution and proxy audit
├── evaluate_candidates.py            # Evaluation execution harness
├── FAILURE_ANALYSIS.md               # Diagnostic root-cause report
├── generate_statistical_analysis.py  # Statistical significance and bootstrap script
├── HELDOUT_MANIFEST.json             # Locked manifest of 14 held-out + 5 dev repos
├── MODEL_ARTIFACT_VERIFICATION.md    # Forensic neural track audit
├── PER_REPOSITORY_RESULTS.csv        # Detailed per-repo score tables
├── PER_SAMPLE_RESULTS.jsonl          # Raw per-query rankings and token counts
├── REPRODUCE.md                      # This reproduction guide
├── RUNTIME_AND_MEMORY.csv            # Multi-scale latency, heap, and RSS data
├── STATISTICAL_ANALYSIS.md           # Significance testing and CI analysis
└── SWE_BENCH_EXECUTION_REPORT.md     # Infrastructure and container audit
```
