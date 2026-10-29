# Reproduction Guide: Stage 3.7 Metric & Evaluation Audit

**Document ID**: `STAGE3-7-REPRO-001`  
**Stage**: Stage 3.7 — Forensic Evaluation Reconciliation and Research Integrity Audit  
**Date**: October 28, 2026  
**Status**: Step-by-Step Verifiable Reproduction Guide  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  

---

## 1. Environment Verification

Ensure the runtime environment is properly configured. From the root directory `F:\RepoNeedle`, execute:

```powershell
python -c "import sys, numpy, scipy, pytest; print('Python:', sys.version.split()[0], '| NumPy:', numpy.__version__, '| SciPy:', scipy.__version__, '| Pytest:', pytest.__version__)"
```
- Expected Python: `>= 3.12`
- Expected Packages: `numpy >= 1.26`, `scipy >= 1.13`, `pytest >= 8.0`

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

## 2. Automated Regression Unit Tests

Execute the full suite of regression unit tests covering the metric contract, mathematical definitions, character vs token budget packing, tag immutability, shortcut excision, and fail-closed audit checks:

```powershell
python -m pytest tests/test_stage3_7_metrics.py tests/test_stage3_7_fail_closed_audit.py -v
```
- Expected output: `16 passed` (9 metric tests + 7 fail-closed audit tests).

To run the complete RepoNeedle unit test suite:
```powershell
python -m pytest tests/
```
- Expected output: `117 passed`.

---

## 3. Regenerating Canonical Stage 3.7 Evaluation Results

To deterministically recompute the canonical evaluation aggregates and per-query JSONL records:

```powershell
python research/stage3_7/generate_canonical_stage3_7.py
```
- Generates `research/stage3_7/CANONICAL_RESULTS.csv` and `research/stage3_7/PER_QUERY_RESULTS.jsonl` (345 queries x 4 systems = 1,380 evaluations).

---

## 4. Reconciling the Stage 3.5 vs. Stage 3.6 Discrepancies

To inspect the exact macro metrics across all 4 systems from the authoritative dataset `research/stage3_6/PER_QUERY_RESULTS.csv`, execute:

```powershell
python -c "
import csv, numpy as np
from collections import defaultdict
with open('research/stage3_6/PER_QUERY_RESULTS.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
by_sys = defaultdict(lambda: defaultdict(list))
for r in rows:
    s = r['system_id']
    for k in ['mrr', 'recall_at_5', 'recall_at_10', 'recall_at_20', 'bcy_at_8k', 'latency_ms']:
        by_sys[s][k].append(float(r[k]))
for s in ['BASE-BM25', 'CAND-C', 'CAND-F', 'BASE-REPOMAP']:
    v = by_sys[s]
    print(f'{s:<15} | MRR: {np.mean(v[\"mrr\"]):.4f} | R@5: {np.mean(v[\"recall_at_5\"]):.4f} | R@20: {np.mean(v[\"recall_at_20\"]):.4f} | CharCov@8k: {np.mean(v[\"bcy_at_8k\"]):.4f} | Lat(p50): {np.median(v[\"latency_ms\"]):.2f}ms')
"
```

Expected Output:
```
BASE-BM25       | MRR: 0.1735 | R@5: 0.1986 | R@20: 0.4549 | CharCov@8k: 0.0493 | Lat(p50): 20.85ms
CAND-C          | MRR: 0.1399 | R@5: 0.2111 | R@20: 0.5105 | CharCov@8k: 0.0188 | Lat(p50): 31.50ms
CAND-F          | MRR: 0.1351 | R@5: 0.1824 | R@20: 0.5078 | CharCov@8k: 0.0159 | Lat(p50): 32.42ms
BASE-REPOMAP    | MRR: 0.2293 | R@5: 0.3337 | R@20: 0.6599 | CharCov@8k: 0.0652 | Lat(p50): 180.20ms
```

---

## 5. Re-Running the Statistical Audit

To verify the Wilcoxon signed-rank and repository-clustered bootstrap results:

```powershell
python research/stage3_6/compute_paired_statistics.py
```
- Expected Wilcoxon $p$-value: `0.0023`
- Expected 95% Clustered Bootstrap CI: `[-0.0091, +0.1689]`

---

## 6. Artifact Checksum Verification

Verify that all research artifacts match their recorded SHA-256 hashes:

```powershell
python -c "
import hashlib
from pathlib import Path
for p in sorted(Path('research/stage3_7').glob('*.md')):
    content = p.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    print(f'{p.name:<30} | {len(content.splitlines()):<5} lines | {sha}')
"
```
