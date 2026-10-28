# REPONEEDLE STAGE 3.4: COMPLETE REPRODUCTION GUIDE

**Document ID**: `STAGE3.4-REPRODUCE-001`  
**Date**: 2026-10-28  
**Scope**: Deterministic Protocol for Reproducing Stage 3.4 Overlap Audits, Full-Corpus Evaluations, and Diagnostic Benchmarks  

---

## 1. System Requirements & Environment Verification

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

# Verify baseline tag
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

### Step 1: Re-Audited Overlap & Clean Held-Out Partition Recalibration ($N=12$)
To verify that `pallets/flask` and `psf/requests` were part of Stage 1 development and recompute clean $N=12$ statistics:

```powershell
python -c "
import json, numpy as np
from scipy import stats

with open('research/stage3_3/PER_SAMPLE_RESULTS.jsonl') as f:
    records = [json.loads(l) for l in f if l.strip()]

genuinely_held_out = [
    'django/django', 'sympy/sympy', 'scikit-learn/scikit-learn',
    'astropy/astropy', 'matplotlib/matplotlib', 'sphinx-doc/sphinx',
    'mwaskom/seaborn', 'pydata/xarray', 'google/guava',
    'facebook/react', 'golang/go', 'BurntSushi/ripgrep'
]

by_sys = {}
for r in records:
    if r['repo'] in genuinely_held_out:
        by_sys.setdefault(r['system_id'], []).append(r)

r_bm25 = np.array([x['file_recall'] for x in by_sys['BASE-BM25']])
r_c = np.array([x['file_recall'] for x in by_sys['CAND-C']])
diff = r_c - r_bm25

print(f'N=12 Clean Held-Out Mean Recall: Cand-C={np.mean(r_c):.4f}, BM25={np.mean(r_bm25):.4f}')
print(f'Mean Diff: +{np.mean(diff):.4f}, Rel Gain: +{(np.mean(diff)/np.mean(r_bm25))*100:.2f}%')
rng = np.random.default_rng(42)
n = len(diff)
boot = [np.mean(diff[rng.integers(0, n, size=n)]) for _ in range(10000)]
print(f'10,000 Bootstrap CI: [{np.percentile(boot, 2.5):.4f}, +{np.percentile(boot, 97.5):.4f}]')
"
```
**Expected Outcome**:
- `Cand-C = 0.9167`, `BM25 = 0.8750`, `Rel Gain = +4.76%`
- `95% Bootstrap CI: [0.0000, +0.1250]` (Rules 1 & 2 fail).

---

### Step 2: Full-Corpus ARB v2 Evaluation ($N=345$ Positive Samples)
To inspect the in-distribution development/regression metrics across all 25 full repository snapshots:

```powershell
python -c "
import csv
with open('research/stage3_4/FULL_CORPUS_RESULTS.csv') as f:
    for row in csv.DictReader(f):
        print(f\"{row['System ID']:25} | MRR: {row['Overall MRR']} | R@20: {row['Recall@20']} | BCY@8k: {row['BCY@8k']}\")
"
```

---

### Step 3: Multi-Scale Latency and Memory Profiling
To measure CPU query latency, Python heap (`tracemalloc`), and working set RSS (`K32GetProcessMemoryInfo`):

```powershell
python research/stage3/audit_runtime_and_memory.py
```
**Expected Outcome**:
- Heap: $\le 45.1$ MB
- RSS: 80.7 MB (micro), 103.1 MB (`click`), 110.3 MB (`caddy`)
- Median Warm Latency: 1.87–11.78 ms.

---

### Step 4: External Validation Handoff Check
To verify the state of the official ContextBench download endpoint and checksum:

```powershell
# Probe download endpoint
python -c "
import urllib.request
url = 'https://huggingface.co/datasets/Contextbench/ContextBench/resolve/main/data/full.parquet?download=true'
try: urllib.request.urlopen(url)
except urllib.error.HTTPError as e: print('Expected blocker verified:', e.code, e.read().decode('utf-8', errors='ignore')[:100])
"
```
**Expected Outcome**: `HTTP Error 403: Forbidden: Request ... on huggingface.co not allowed by policy`.

---

## 3. Directory Layout of Stage 3.4 Artifacts

```
research/stage3_4/
├── EVIDENCE_INTEGRITY_AUDIT.md       # Diagnostic scope and narrative correction
├── FAILURE_ANALYSIS.md               # Controlled diagnostics of weaknesses
├── FULL_CORPUS_RESULTS.csv           # 345-sample full ARB v2 regression results
├── REPOSITORY_OVERLAP_AUDIT.md       # Full lifecycle 25-repo cross-reference
├── REPRODUCE.md                      # This reproduction guide
├── RUNTIME_AND_MEMORY.csv            # Multi-scale latency, heap, and RSS data
└── STAGE3_4_DECISION_REPORT.md       # Definitive synthesis decision report
```
