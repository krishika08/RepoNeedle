# RepoNeedle Stage 3.16 — ContextBench Dataset Integrity Report

**Document ID**: `STAGE3-16-INTEGRITY-001`  
**Date**: October 2026  
**Auditor**: Autonomous Verification Harness  
**Target Benchmark**: Contextbench/ContextBench (EuniAI)  

---

## 1. Authoritative Benchmark Specifications

According to official ContextBench documentation (`https://euniai.github.io/ContextBench/`), the benchmark provides two official configurations:

### 1.1 Full Configuration (`default`)
- **Target File**: `full.parquet` (or `full.jsonl`)
- **Total Task Count**: Exactly **1,136 tasks**
- **Repository Coverage**: Exactly **66 independent repositories**
- **Programming Languages (8)**:
  - Python
  - Java
  - JavaScript
  - TypeScript
  - Go
  - C++
  - C
  - Rust
- **Benchmark Purpose**: Comprehensive real-world repository-level retrieval evaluation.

### 1.2 Verified Subset Configuration (`contextbench_verified`)
- **Target File**: `contextbench_verified.parquet` (or `contextbench_verified.jsonl`)
- **Total Task Count**: Exactly **500 tasks**
- **Repository Coverage**: Exactly **35 repositories**
- **Benchmark Purpose**: Human-verified, high-precision evaluation subset with audited issue descriptions and ground-truth contexts.

---

## 2. Required Schema & Field Integrity Rules

The deterministic intake validator ([`research/external_data/contextbench/validate_contextbench.py`](file:///F:/RepoNeedle/research/external_data/contextbench/validate_contextbench.py)) enforces the following schema:

| Column Name | Required Type | Constraints & Integrity Checks | Retrieval Accessibility |
|---|---|---|---|
| `instance_id` | String | Must be non-empty and globally unique within configuration | Permitted (Identification only) |
| `repo` | String | Must be non-empty string in format `owner/repo` | Permitted (Repository lookup) |
| `base_commit` | String | Must be non-empty 40-character or abbreviated Git SHA | Permitted (Snapshot checkout) |
| `problem_statement` | String | Must be non-empty string representing natural language issue | **Primary Retrieval Query** |
| `language` | String | Lowercase language identifier (e.g. `python`, `go`) | Permitted (Language schedule selection) |
| `gold_context` | List / JSON | Non-empty list of target files and character/line spans | **STRICTLY FORBIDDEN IN RETRIEVAL** (Evaluation only) |
| `patch` | String | Issue resolution patch | **STRICTLY FORBIDDEN IN RETRIEVAL** (Evaluation only) |
| `test_patch` | String | Test patch | **STRICTLY FORBIDDEN IN RETRIEVAL** (Evaluation only) |
| `f2p` / `p2p` | List / JSON | Test case transitions | **STRICTLY FORBIDDEN IN RETRIEVAL** (Evaluation only) |

---

## 3. Strict Prevention of Configuration Conflation

The full configuration (1,136 tasks) and verified subset (500 tasks) have different statistical power and noise profiles:
- The intake layer strictly verifies file names and row counts to ensure `full.parquet` and `contextbench_verified.parquet` are never mixed.
- Results on the 500-instance subset must be explicitly reported as `ContextBench-Verified-500` and must never be conflated with the 1,136-instance full benchmark.

---

## 4. Comparison with Unofficial Mirrors

| Property | Official ContextBench (`EuniAI`) | Unofficial Mirror (`Schwerli/ContextBench`) | Governance Decision |
|---|---|---|---|
| **Full Task Count** | **1,136** | Divergent / Non-matching | Prohibited |
| **Verified Task Count**| **500** | Non-standard | Prohibited |
| **Repository Count** | **66** | Unverified | Prohibited |
| **Authority** | Official EuniAI Authors | Third-party reupload | Prohibited |
| **Status** | **MANDATORY BENCHMARK** | **REJECTED** | Only official EuniAI artifacts accepted |
