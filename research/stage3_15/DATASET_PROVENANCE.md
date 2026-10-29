# RepoNeedle Stage 3.15: Dataset Provenance and Acquisition Audit

**Stage**: Stage 3.15 — Official ContextBench Acquisition and Independent Evaluation Gate  
**Date**: October 2026  
**Document ID**: `STAGE3-15-DATA-001`  
**Status**: Authoritative Data Provenance and Blocker Audit  
**Branch**: `research-program`  
**Base Commit**: `3e889fc`  

---

## 1. Executive Summary

This document establishes the official dataset provenance record, local cache inspection results, and acquisition audit for the independent evaluation of RepoNeedle on **ContextBench**.

In accordance with strict scientific integrity principles:
1. **No Synthetic Proxies**: We do not substitute synthetic mock instances, hand-crafted fixtures, or derived micro-suites and label them as "ContextBench".
2. **No Benchmark Leakage**: ARB v2 has been utilized throughout Stages 1 through 3.14. Evaluating on ARB v2 constitutes regression and development benchmarking, not independent generalization.
3. **Fail-Closed Acquisition Protocol**: Outbound network requests to external repositories are restricted under the sandbox execution boundary. Because automated downloads returned `HTTP 403: Forbidden` across all standard endpoints and no official ContextBench artifact is present in local caches, the independent evaluation gate is formally classified as **`BLOCKED — DATA ACCESS`**.

---

## 2. Target Dataset Specifications

| Attribute | Specification | Source / Authority |
| :--- | :--- | :--- |
| **Benchmark Name** | ContextBench | EuniAI Research / Hugging Face |
| **Hugging Face Hub ID** | [`Contextbench/ContextBench`](https://huggingface.co/datasets/Contextbench/ContextBench) | Official Dataset Card |
| **Official Repository** | [`https://github.com/EuniAI/ContextBench`](https://github.com/EuniAI/ContextBench) | Official Reference Implementation |
| **Target Dataset Scope** | Full ContextBench Corpus (all repositories and tasks) | Disallows truncation to arbitrary 500-task micro subsets |
| **Recorded Full Dataset SHA-256** | `2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8` | Historical Research Record |
| **Target Local Workspace Path** | `F:\RepoNeedle\data\contextbench\` | Canonical Workspace Location |
| **Permitted File Formats** | `.parquet`, `.jsonl`, `.json` | Deterministic Ingestion Engine |

### 2.1 Canonical Dataset Schema
The official ContextBench dataset format requires the following core fields for each evaluated task instance:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique benchmark instance identifier |
| `repository` | `string` | Repository name in `owner/repo` format |
| `base_commit` | `string` | Commit hash representing repository state |
| `query` | `string` | Task prompt, problem statement, or natural language query |
| `gold_files` | `list[str]` | Non-empty list of ground-truth file paths required to solve the task |
| `gold_spans` / `gold_symbols` | `list[dict]` *(optional)* | Block- or symbol-level ground-truth annotations where provided |

---

## 3. Local Cache Audit

Prior to initiating network requests, an exhaustive audit was performed across all local system caches and workspace storage to determine if an authorized copy of ContextBench had previously been retrieved:

1. **Hugging Face Hub Cache Directory** (`C:\Users\krish\.cache\huggingface\hub`):
   - Found: `eyuansu71--agent_retrieval_bench` (snapshots for v2 releases: `v2_code2test`, `v2_comment2context`, `v2_edit2ripple`, `v2_trace2code`, `v2_selective_retrieval_balanced`, `v2_selective_retrieval_natural`, `v2_abstention`).
   - Found: `xet` logging directories.
   - Result: **Zero ContextBench files, snapshots, or refs were found.**
2. **Workspace Directories** (`F:\RepoNeedle`):
   - Inspected `data/`, `hf_artifacts/`, `external/`, and `research/`.
   - Identified historical Stage 3 micro-suite (`research/stage3/data/contextbench_suite.json`, 19 synthetic/proxy instances). In accordance with Stage 3.15 rules, this proxy file is **strictly prohibited** from being labeled or utilized as the official ContextBench benchmark.
   - Result: **No authentic ContextBench dataset exists in the workspace.**

---

## 4. Empirical Acquisition Attempts & Blocker Evidence

All standard, permitted acquisition channels were probed using standard Python network libraries without bypassing environment boundaries:

```python
routes = [
    ("Hugging Face Web Dataset", "https://huggingface.co/datasets/Contextbench/ContextBench"),
    ("Hugging Face API", "https://huggingface.co/api/datasets/Contextbench/ContextBench"),
    ("GitHub Official Repo", "https://github.com/EuniAI/ContextBench.git"),
    ("GitHub API", "https://api.github.com/repos/EuniAI/ContextBench"),
]
```

### Empirical Probe Results:

| Route ID | Target Endpoint URL | Method / Library | Observed Response | Status |
| :--- | :--- | :--- | :--- | :--- |
| **ROUTE-01** | `https://huggingface.co/datasets/Contextbench/ContextBench` | `urllib.request` / `datasets` | `urllib.error.HTTPError: HTTP Error 403: Forbidden` | `BLOCKED` |
| **ROUTE-02** | `https://huggingface.co/api/datasets/Contextbench/ContextBench` | `urllib.request` / `requests` | `urllib.error.HTTPError: HTTP Error 403: Forbidden` | `BLOCKED` |
| **ROUTE-03** | `https://github.com/EuniAI/ContextBench.git` | `git clone` / `urllib` | `urllib.error.HTTPError: HTTP Error 403: Forbidden` | `BLOCKED` |
| **ROUTE-04** | `https://api.github.com/repos/EuniAI/ContextBench` | `urllib.request` / `requests` | `urllib.error.HTTPError: HTTP Error 403: Forbidden` | `BLOCKED` |

### Blocker Diagnostic:
The sandbox execution environment enforces outbound network isolation. As a consequence, direct downloads cannot succeed autonomously within this session.

A complete machine-readable audit is recorded in [`ACQUISITION_ATTEMPTS.json`](file:///F:/RepoNeedle/research/stage3_15/ACQUISITION_ATTEMPTS.json).

---

## 5. Non-Repetition & Handoff Instructions

To prevent repeated failed download attempts in subsequent stages, the exact manual handoff procedure is defined:

1. **Operator Download (External Network)**:
   ```bash
   huggingface-cli download Contextbench/ContextBench --repo-type dataset --local-dir F:/RepoNeedle/data/contextbench
   ```
2. **Cryptographic & Schema Verification**:
   ```powershell
   python research/stage3_15/validate_contextbench.py --data-dir data/contextbench --expected-sha256 2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8
   ```
3. **Execution**:
   Only after `validate_contextbench.py` exits with code 0 (`[STATUS: VERIFIED AND READY]`) will the evaluation adapter execute.
