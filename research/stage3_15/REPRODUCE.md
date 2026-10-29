# RepoNeedle Stage 3.15: Experimental Reproduction Guide

**Stage**: Stage 3.15 — Official ContextBench Acquisition and Independent Evaluation Gate  
**Date**: October 2026  
**Document ID**: `STAGE3-15-REPRO-001`  
**Branch**: `research-program`  
**Base Commit**: `3e889fc`  

---

## 1. Environment & Tag Verification

Open PowerShell in the repository root (`F:\RepoNeedle`):

```powershell
# 1. Verify working directory
cd F:\RepoNeedle

# 2. Verify git branch and commit status
git branch --show-current
# Expected: research-program

# 3. Verify immutable frozen tags are intact
git cat-file -p v0.1.0-baseline
# Expected: object 8e004255... tag v0.1.0-baseline

git cat-file -p stage3-candidate-freeze
# Expected: object cd7f3b01... tag stage3-candidate-freeze
```

---

## 2. Reproduce Acquisition Probing & Blocker Evidence

Verify that standard network endpoints are inaccessible from within the sandbox execution environment:

```powershell
python -c "
import urllib.request
try:
    urllib.request.urlopen('https://huggingface.co/datasets/Contextbench/ContextBench', timeout=5)
    print('ONLINE')
except Exception as e:
    print(f'PROBE RESULT: {e}')
"
```
**Expected Output:**
```
PROBE RESULT: HTTP Error 403: Forbidden
```

Inspect the machine-readable provenance log:
```powershell
Get-Content research/stage3_15/ACQUISITION_ATTEMPTS.json
```

---

## 3. Reproduce Fail-Closed Validation Gate

Execute the deterministic validation gate script when no dataset is present in `data/contextbench/`:

```powershell
python research/stage3_15/validate_contextbench.py
```
**Expected Output:**
```
================================================================================
REPONEEDLE: CONTEXTBENCH INDEPENDENT VALIDATION GATE (STAGE 3.15)
Target Directory: F:\RepoNeedle\data\contextbench
Official Source:  https://huggingface.co/datasets/Contextbench/ContextBench
================================================================================

[STATUS: BLOCKED — DATA ACCESS]
No ContextBench artifacts found in F:\RepoNeedle\data\contextbench.
Network boundary prevents automated acquisition from Hugging Face.
See research/stage3_15/DATASET_PROVENANCE.md for handoff instructions.
```
*(Process exits with Code 2).*

---

## 4. Run Automated Safeguards & Regression Tests

Execute the Stage 3.15 safeguard test suite and the complete test suite:

```powershell
# Run Stage 3.15 specific safeguard tests
python -m pytest tests/test_stage3_15_safeguards.py -v

# Run full repository test suite (97+ tests)
python -m pytest tests/ -q
```
**Expected Result:**
All tests pass 100% green without failure or regression.

---

## 5. External Operator Handoff (For Independent Validation)

When executing outside sandbox isolation with authorized network access:

1. Download the official dataset:
   ```bash
   huggingface-cli download Contextbench/ContextBench --repo-type dataset --local-dir F:/RepoNeedle/data/contextbench
   ```
2. Validate the artifact:
   ```powershell
   python research/stage3_15/validate_contextbench.py --data-dir data/contextbench --expected-sha256 2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8
   ```
3. Run the locked evaluation adapter:
   ```powershell
   python research/stage3_15/contextbench_adapter.py --dataset data/contextbench/contextbench_full.jsonl --output-dir research/stage3_15
   ```
