# RepoNeedle Stage 3.17 — Deterministic Reproduction Guide

This document provides exact, copy-pasteable instructions for reproducing the Stage 3.17 audit and gate verification in `F:\RepoNeedle`.

---

## 1. Verify Git State & Baseline Tags

From the root of the repository:

```powershell
# 1. Verify current branch
git branch --show-current
# Expected: research-program

# 2. Verify immutable baseline tags
git rev-parse v0.1.0-baseline
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse stage3-candidate-freeze
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca

# 3. Verify clean working tree
git status
# Expected: nothing to commit, working tree clean
```

---

## 2. Verify Intake Validator & Fail-Closed Gate

Execute the official intake validator in the current workspace:

```powershell
python research/external_data/contextbench/validate_contextbench.py
$lastexit = $LASTEXITCODE
Write-Host "Validator Exit Code: $lastexit"
```

**Expected Result**:
```
================================================================================
REPONEEDLE: OFFICIAL CONTEXTBENCH VALIDATION GATE (STAGE 3.17)
Data Directory: F:\RepoNeedle\research\external_data\contextbench
Pinned Upstream Revision: c285579
================================================================================

[STATUS: BLOCKED - DATA ACCESS]
No ContextBench artifacts found in F:\RepoNeedle\research\external_data\contextbench.
Required artifacts:
  - full.parquet (expected SHA: 2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8, 26102607 bytes)
  - contextbench_verified.parquet (expected SHA: e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791, 9558250 bytes)
...
Validator Exit Code: 2
```

The exit code must be `2`.

---

## 3. External Acquisition & Unblocking Procedure (Outside Sandbox)

When an operator with external internet connectivity is available:

```bash
# 1. Download official ContextBench artifacts (commit c285579)
curl -L -o research/external_data/contextbench/full.parquet \
  https://huggingface.co/datasets/Contextbench/ContextBench/resolve/c285579/data/full.parquet

curl -L -o research/external_data/contextbench/contextbench_verified.parquet \
  https://huggingface.co/datasets/Contextbench/ContextBench/resolve/c285579/data/contextbench_verified.parquet

# 2. Run the validator again (must return Exit Code 0)
python research/external_data/contextbench/validate_contextbench.py
```

---

## 4. Run Automated Stage 3.17 Tests

Run pytest specifically against the Stage 3.17 evaluation gate test suite:

```powershell
pytest tests/test_stage3_17_evaluation_gate.py -v
```

All tests must pass synchronously.
