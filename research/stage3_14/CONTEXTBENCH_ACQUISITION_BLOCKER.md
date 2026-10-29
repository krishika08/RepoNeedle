# RepoNeedle Stage 3.14: ContextBench Acquisition Blocker & Independent Validation Protocol

**Stage**: Stage 3.14 — Reproducibility, Historical Errata, and Independent Validation Gate  
**Date**: October 2026  
**Status**: Formal Evaluation Gate Blocker  
**Branch**: `research-program`  
**Base Commit**: `bf7f4c8`  

---

## 1. Executive Statement of Blocker

Independent validation of RepoNeedle on the official **ContextBench** benchmark remains **BLOCKED BY EXTERNAL DATA ACCESS**.

Automated retrieval attempts to download the official dataset from Hugging Face via the sandbox environment failed with:
```
urllib.error.HTTPError: HTTP Error 403: Forbidden
URL: https://huggingface.co/datasets/Contextbench/ContextBench
```

In accordance with strict research integrity standards:
- **No synthetic data substitution**: We do not manufacture mock instances or substitute arbitrary micro-suites as "ContextBench".
- **No benchmark leakage**: ARB v2 was utilized throughout development Stages 1 through 3.13; evaluation on ARB v2 constitutes regression and development benchmarking, not independent generalization.
- **Fail-Closed Governance**: The independent evaluation gate remains formally closed until genuine official ContextBench artifacts are placed into the workspace and cryptographically validated.

---

## 2. Benchmark Specification & Target Manifest

| Attribute | Specification |
| :--- | :--- |
| **Official Benchmark** | ContextBench (Hugging Face Datasets) |
| **Repository Identifier** | `Contextbench/ContextBench` |
| **Official URL** | [`https://huggingface.co/datasets/Contextbench/ContextBench`](https://huggingface.co/datasets/Contextbench/ContextBench) |
| **Target Local Workspace Path** | `F:\RepoNeedle\data\contextbench\` |
| **Accepted Formats** | `contextbench_test.jsonl`, `contextbench.json`, or `.parquet` |
| **Required Schema Fields** | `id` (string), `repository` (string), `base_commit` (string), `query` (string), `gold_files` (list of non-empty file path strings) |
| **Verification Gate Script** | [`research/stage3_14/validate_contextbench.py`](file:///F:/RepoNeedle/research/stage3_14/validate_contextbench.py) |

---

## 3. Minimal User Handoff Instructions for Manual Ingestion

To complete genuine independent evaluation, the user or authorized operator must perform the following manual data acquisition outside the sandbox:

### Step 1: Download Official ContextBench Dataset
Using an external terminal with authorized Hugging Face credentials and network access:

```bash
# Option A: Using the Hugging Face CLI
huggingface-cli download Contextbench/ContextBench --repo-type dataset --local-dir F:/RepoNeedle/data/contextbench

# Option B: Using Python datasets library
python -c "
from datasets import load_dataset
ds = load_dataset('Contextbench/ContextBench')
ds['test'].to_json('F:/RepoNeedle/data/contextbench/contextbench_test.jsonl')
print('ContextBench downloaded successfully.')
"
```

### Step 2: Run Deterministic Verification Script
From the repository root (`F:\RepoNeedle`):

```powershell
python research/stage3_14/validate_contextbench.py --data-dir data/contextbench
```

**Expected Validator Responses:**
- If files are missing: Exits with Code 2 (`[STATUS: BLOCKED BY EXTERNAL DATA ACCESS]`).
- If checksum mismatch: Exits with Code 3 (`[STATUS: REJECTED (Code 3)] Checksum mismatch`).
- If schema invalid: Exits with Code 4 (`[STATUS: REJECTED (Code 4)] Missing required field`).
- If valid and verified: Exits with Code 0 (`[STATUS: VERIFIED AND READY] Valid ContextBench dataset`).

### Step 3: Execute Independent Evaluation
Once verified with Code 0, the independent benchmark harness will execute blind evaluation across frozen baseline `v0.1.0-baseline` (`8e00425`), candidate freeze `stage3-candidate-freeze` (`cd7f3b0`), `CONFIG-09`, `CONFIG-10`, and pinned `BASE-REPOMAP`.
