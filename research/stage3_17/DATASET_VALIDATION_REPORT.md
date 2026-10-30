# RepoNeedle Stage 3.17 — Dataset Validation & Integrity Audit Report

**Document ID**: `STAGE3-17-DATASET-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `548dab5eea6c71c3e9982676289098d9e0dca5f0`  
**Target Upstream Repository**: `https://huggingface.co/datasets/Contextbench/ContextBench`  
**Pinned Upstream Revision**: `c285579`  
**Validation Outcome**: **`BLOCKED — DATA ACQUISITION OR VALIDATION FAILED` (Exit Code 2)**  

---

## 1. Executive Summary

This audit evaluates the physical presence, cryptographic integrity, and structural schema of the official ContextBench benchmark artifacts within [`research/external_data/contextbench/`](file:///F:/RepoNeedle/research/external_data/contextbench).

In accordance with Stage 3.17 instructions:
> *"Validate the acquired datasets... Expected files: `research/external_data/contextbench/full.parquet` and `research/external_data/contextbench/contextbench_verified.parquet`. If either file is missing or validation fails, stop and report `BLOCKED`. Do not proceed with evaluation."*

The intake validator [`research/external_data/contextbench/validate_contextbench.py`](file:///F:/RepoNeedle/research/external_data/contextbench/validate_contextbench.py) was executed. It verified that neither file is present on the local filesystem, resulting in an immediate fail-closed exit with code `2`. In-sandbox network access to Hugging Face is blocked by standard container isolation (`HTTP Error 403: Forbidden`). Consequently, no benchmark evaluation could be conducted.

---

## 2. Upstream Dataset Specification & Integrity Contract

The benchmark dataset must correspond strictly to the official ContextBench release maintained by EuniAI (`Contextbench/ContextBench`) pinned to commit revision `c285579`.

### 2.1 Artifact Integrity Contract

| Configuration Name | Filename | Expected Upstream Revision | Expected Rows | Expected Repositories | Expected Languages | Expected File Size (Bytes) | Expected Cryptographic Hash (SHA-256) |
|---|---|---|---|---|---|---|---|
| **`default`** (Full) | `full.parquet` | `c285579` | **1,136** | **66** | **8** | **26,102,607** | `2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8` |
| **`contextbench_verified`** | `contextbench_verified.parquet` | `c285579` | **500** | **35** | **8** | **9,558,250** | `e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791` |

### 2.2 Schema & Consistency Constraints
1. **Mandatory Input Columns**: `instance_id`, `repo`, `base_commit`, `problem_statement`, `gold_context`.
2. **Identifier Uniqueness**: `instance_id` must be non-empty and globally unique across all rows.
3. **Gold Context Integrity**: `gold_context` must be non-empty and parseable into file/line target dictionaries.
4. **Subset Constraint**: The 500 tasks in `contextbench_verified.parquet` must constitute a strict mathematical subset of the 1,136 tasks in `full.parquet`.
5. **Forbidden Fields**: Evaluator input feeds must not expose `gold_context`, `patch`, `test_patch`, `f2p`, or `p2p`.

---

## 3. Local Audit & Validation Results

### 3.1 Validator Execution
The automated intake validator was executed:
```powershell
python research/external_data/contextbench/validate_contextbench.py
```

### 3.2 Command Output
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
Network boundary prevents automated acquisition from Hugging Face.
See research/external_data/contextbench/ACQUISITION_BLOCKER.md for handoff instructions.
ExitCode: 2
```

### 3.3 File System Verification
Direct inspection of `F:\RepoNeedle\research\external_data\contextbench\` confirms:
- `full.parquet`: **MISSING**
- `contextbench_verified.parquet`: **MISSING**
- Existing support files: `README.md`, `validate_contextbench.py`, `dataset_manifest.json`, `ACQUISITION_BLOCKER.md`, `.gitignore`.

---

## 4. Network Boundary & Security Isolation Forensics

To confirm whether automated intake was blocked by transient issues or intentional sandbox policy, network endpoints were probed during Stage 3.16:
1. `https://huggingface.co/datasets/Contextbench/ContextBench/resolve/c285579/data/full.parquet` $\to$ **`HTTP 403: Forbidden`**
2. `https://huggingface.co/datasets/Contextbench/ContextBench/raw/c285579/README.md` $\to$ **`HTTP 403: Forbidden`**
3. `https://raw.githubusercontent.com/EuniAI/ContextBench/main/README.md` $\to$ **`HTTP 403: Forbidden`**

### Security Compliance
In accordance with sandbox governance and system guidelines:
- No network sandbox bypasses were attempted.
- No TLS verification checks were disabled.
- No credential interceptions or unauthorized proxies were introduced.

---

## 5. Rejection of Unofficial Substitutes & Synthetic Data

### 5.1 Prohibition of `Schwerli/ContextBench`
An unofficial mirror exists on Hugging Face (`Schwerli/ContextBench`). Forensic audit of its metadata reveals:
- Row counts diverge from the official 1,136 benchmark tasks.
- Target split definitions and column annotations have been modified.
- **Verdict**: Formally rejected as an invalid benchmark substitute.

### 5.2 Prohibition of Synthetic / Mock Parquet Files
Generating artificial Parquet rows with dummy data to satisfy the file presence check would violate scientific integrity.
- **Verdict**: Fabricating synthetic benchmark evaluation numbers is strictly prohibited.

---

## 6. Audit Conclusion & Gate Verdict

Because neither `full.parquet` nor `contextbench_verified.parquet` is present, the benchmark evaluation gate fails closed:

```
[FINAL DECISION] BLOCKED — DATA ACQUISITION OR VALIDATION FAILED
```

Independent validation cannot proceed until an external operator acquires the two official Parquet files matching revision `c285579` and places them in `research/external_data/contextbench/`.
