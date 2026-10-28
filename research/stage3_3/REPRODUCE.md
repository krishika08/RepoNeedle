# REPONEEDLE STAGE 3.3: COMPLETE REPRODUCTION GUIDE

**Document ID**: `STAGE3.3-REPRODUCE-001`  
**Date**: 2026-10-28  
**Scope**: Deterministic Protocol for Reproducing Stage 3.3 Network Probes, Evaluations, and Budget Saturation Experiments  

---

## 1. System Requirements & Verification

### 1.1 Python Environment & Dependencies
- Python version: `Python 3.12+`
- Required packages: `pytest`, `numpy`, `scipy`, `pydantic`, `pyyaml`
- Standard libraries: `ctypes`, `tracemalloc`, `urllib`, `json`, `csv`, `pathlib`, `time`

### 1.2 Git State Verification
```powershell
# Verify branch
git branch --show-current
# Expected: research-program

# Verify candidate freeze tag
git rev-parse stage3-candidate-freeze
# Expected: cd7f3b0c8e37d5ff4b1ea27c0065b75ad4f71a9e

# Verify v0.1.0 baseline tag
git rev-parse v0.1.0-baseline
# Expected: 8e00425a1b32d2948bbda1810416b0df470a273e
```

### 1.3 Baseline Unit & Regression Tests
```powershell
python -m pytest
```
**Expected Outcome**: `44 passed in ~3.5s` (100% passing).

---

## 2. Step-by-Step Reproduction Workflow

### Step 1: Probe Official Acquisition Channels & Network Blockers
Run the deterministic network probes to verify environmental policy isolation:

```powershell
# Probe 1: Git remote over HTTPS
git ls-remote https://github.com/EuniAI/ContextBench.git HEAD
# Expected: fatal: SEC_E_UNTRUSTED_ROOT (0x80090325)

# Probe 2: Python HTTP probe on official README and Hugging Face API
python -c "
import urllib.request
for u in ['https://raw.githubusercontent.com/EuniAI/ContextBench/main/README.md', 'https://huggingface.co/api/datasets/Contextbench/ContextBench']:
    try: urllib.request.urlopen(u)
    except urllib.error.HTTPError as e: print(u, e.code, e.read().decode('utf-8', errors='ignore')[:100])
"
# Expected: HTTP Error 403 Forbidden on both endpoints (Request ... not allowed by policy)
```

---

### Step 2: Run Matched Candidate Evaluation & Saturated Budget Analysis
Executes the 7 frozen systems across the Held-Out ($N=14$) and Replication ($N=5$) partitions, and benchmarks budget saturation behavior on the full 133-file `pallets/click` repository:

```powershell
python research/stage3_3/run_stage3_3_eval.py
```

**Artifacts Generated**:
- `research/stage3_3/CONTEXTBENCH_RESULTS.csv` (File and Block level metrics)
- `research/stage3_3/PER_REPOSITORY_RESULTS.csv` (Per-repository breakdowns)
- `research/stage3_3/SATURATED_BUDGET_ANALYSIS.csv` (Budget saturation metrics on `click`)
- `research/stage3_3/PER_SAMPLE_RESULTS.jsonl` (Per-sample JSONL rankings)

---

### Step 3: Compute Statistical Significance and Bootstrap CIs
Computes paired $t$-tests and 10,000 clustered bootstrap iterations using fixed seed (`rng = np.random.default_rng(42)`):

```powershell
python research/stage3_3/generate_stage3_3_stats.py
```

**Artifact Generated**:
- `research/stage3_3/STATISTICAL_ANALYSIS.md`

---

## 3. Directory Layout of Stage 3.3 Artifacts

```
research/stage3_3/
├── CONTEXTBENCH_RESULTS.csv          # File and Block metrics across partitions
├── DATASET_PROVENANCE.md             # Protocol-by-protocol network audit
├── FAILURE_ANALYSIS.md               # Root cause diagnostics
├── generate_stage3_3_stats.py        # Statistical script
├── OVERLAP_AND_SPLIT_AUDIT.md        # 66-repository overlap cross-reference
├── PER_REPOSITORY_RESULTS.csv        # Detailed per-repo score tables
├── PER_SAMPLE_RESULTS.jsonl          # Raw per-query rankings and token counts
├── REPRODUCE.md                      # This reproduction guide
├── run_stage3_3_eval.py              # Candidate evaluation harness
├── SATURATED_BUDGET_ANALYSIS.csv     # Saturated budget evaluation on pallets/click
├── STAGE3_3_DECISION_REPORT.md       # Definitive synthesis decision report
├── STATISTICAL_ANALYSIS.md           # Significance testing and CI analysis
└── TASK_ACCOUNTING.csv               # Task-by-task provenance catalog
```
