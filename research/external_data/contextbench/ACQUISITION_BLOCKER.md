# Official ContextBench Acquisition Blocker Notice

**Document ID**: `STAGE3-16-BLOCKER-001`  
**Stage**: Stage 3.16 — Official ContextBench Acquisition & Independent Validation Gate  
**Date**: October 2026  
**Status**: `BLOCKED — EXTERNAL DATA ACQUISITION REQUIRED`  

---

## 1. Executive Summary

Automated acquisition of the official `Contextbench/ContextBench` benchmark from within the sandbox execution environment is **BLOCKED by network isolation boundaries**.

In accordance with research integrity governance:
- **No network isolation boundaries were bypassed**.
- **No proxy workarounds or TLS verification disabling were used**.
- **No unofficial substitute mirrors (`Schwerli/ContextBench`) or synthetic datasets were substituted**.
- Bounded download attempts were performed and halted once HTTP 403 / network isolation was established.
- Independent external validation is formally **GATED** until the official artifacts are acquired through authorized external operator handoff.

---

## 2. Forensic Audit of Attempted In-Sandbox Acquisition Routes

| Route Attempted | Exact Command / API Call | Result Code / Exception | Root Cause |
|---|---|---|---|
| **Route 1: Standard HTTPS Download** | `urllib.request.urlopen("https://huggingface.co/datasets/Contextbench/ContextBench")` | `urllib.error.HTTPError: HTTP Error 403: Forbidden` | Outbound network calls to external hostnames are blocked by sandbox isolation boundary. |
| **Route 2: Hugging Face Datasets Library** | `datasets.load_dataset("Contextbench/ContextBench", "default")` | `ModuleNotFoundError: No module named 'datasets'` | The `datasets` package is not installed in the isolated local CPython environment, and package installation requires network access. |
| **Route 3: Raw Parquet Resolution** | `urllib.request.urlopen("https://huggingface.co/datasets/Contextbench/ContextBench/resolve/main/data/full.parquet")` | `urllib.error.HTTPError: HTTP Error 403: Forbidden` | Direct Parquet asset endpoint is blocked by sandbox network boundary. |
| **Route 4: Official GitHub Repository** | `urllib.request.urlopen("https://raw.githubusercontent.com/EuniAI/ContextBench/main/README.md")` | `urllib.error.HTTPError: HTTP Error 403: Forbidden` | Raw GitHub repository endpoints blocked by sandbox network boundary. |
| **Route 5: Official Documentation Site** | `urllib.request.urlopen("https://euniai.github.io/ContextBench/")` | `urllib.error.HTTPError: HTTP Error 403: Forbidden` | Documentation host blocked by sandbox network boundary. |

---

## 3. Strict Policies on Mirrors and Substitutes

1. **Rejection of `Schwerli/ContextBench`**:
   - The third-party Hugging Face dataset `Schwerli/ContextBench` displays divergent task row counts and modified metadata.
   - It is **STRICTLY PROHIBITED** from being substituted for the official benchmark.
2. **Rejection of Synthetic Datasets**:
   - Fabricating synthetic mock Parquet files to claim independent validation is a severe research integrity violation.
   - Stage 3.16 mandates that if the official dataset cannot be acquired, the formal governance verdict must be **`BLOCKED — EXTERNAL DATA ACQUISITION REQUIRED`**.

---

## 4. Required Out-of-Sandbox Operator Handoff Steps

To unblock independent validation:
1. An operator on a network-enabled machine executes the standard download script:
   ```bash
   python -c "
   from datasets import load_dataset
   ds = load_dataset('Contextbench/ContextBench', 'default')
   ds['train'].to_parquet('full.parquet')
   ds_ver = load_dataset('Contextbench/ContextBench', 'contextbench_verified')
   ds_ver['train'].to_parquet('contextbench_verified.parquet')
   "
   ```
2. Place the resulting `full.parquet` (1,136 tasks) and `contextbench_verified.parquet` (500 tasks) into:
   `F:\RepoNeedle\research\external_data\contextbench\`
3. Run the fail-closed intake validator:
   ```bash
   python research/external_data/contextbench/validate_contextbench.py
   ```
4. Once verified, execute the evaluation adapter:
   ```bash
   python research/contextbench_evaluation/adapter.py --config arm-101
   ```
