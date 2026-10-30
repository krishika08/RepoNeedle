# RepoNeedle Stage 3.16 — Reproduction Guide

**Stage**: Stage 3.16 — Official ContextBench Acquisition & Independent Validation Gate  
**Date**: October 2026  
**Document ID**: `STAGE3-16-REPRO-001`  
**Git Branch**: `research-program`  
**Base Commit**: `143e8bc`  

---

## 1. Environment & Tag Verification

Open PowerShell or terminal in the repository root (`F:\RepoNeedle`):

```bash
# 1. Verify working directory
cd F:\RepoNeedle

# 2. Verify git branch and working tree status
git branch --show-current
# Expected: research-program

git status
# Expected: nothing to commit, working tree clean

# 3. Verify immutable baseline tags are intact
git rev-parse v0.1.0-baseline^{commit}
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse stage3-candidate-freeze^{commit}
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 2. Reproduce In-Sandbox Acquisition Probing & Blocker Evidence

Verify that outbound requests to external endpoints are blocked by the sandbox network boundary:

```bash
python -c "
import urllib.request
for url in [
    'https://huggingface.co/datasets/Contextbench/ContextBench',
    'https://raw.githubusercontent.com/EuniAI/ContextBench/main/README.md',
    'https://euniai.github.io/ContextBench/'
]:
    try:
        urllib.request.urlopen(url, timeout=5)
        print('ONLINE:', url)
    except Exception as e:
        print(f'BLOCKED: {url} -> {type(e).__name__}: {e}')
"
```
**Expected Output:**
All endpoints report `HTTPError: HTTP Error 403: Forbidden`.

---

## 3. Reproduce Fail-Closed Intake Validation Gate

Run the intake validator when no dataset files are present:

```bash
python research/external_data/contextbench/validate_contextbench.py
```
**Expected Output:**
```
================================================================================
REPONEEDLE: OFFICIAL CONTEXTBENCH VALIDATION GATE (STAGE 3.16)
Data Directory: F:\RepoNeedle\research\external_data\contextbench
================================================================================

[STATUS: BLOCKED - DATA ACCESS]
No ContextBench artifacts found in F:\RepoNeedle\research\external_data\contextbench.
Network boundary prevents automated acquisition from Hugging Face.
See research/external_data/contextbench/ACQUISITION_BLOCKER.md for handoff instructions.
```
*(Process exits with Code 2).*

---

## 4. Run Automated Test Suites

Run the Stage 3.16 test suite and full repository test suite:

```bash
# Run Stage 3.16 specific test suite
pytest tests/test_stage3_16_contextbench_gate.py -v

# Run full repository test suite
pytest
```
All tests must pass synchronously with exit code 0.
