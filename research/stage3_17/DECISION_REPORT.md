# RepoNeedle Stage 3.17 — Final Governance & Evaluation Gate Decision Report

**Document ID**: `STAGE3-17-DECISION-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `548dab5eea6c71c3e9982676289098d9e0dca5f0`  
**Auditor**: Antigravity Automated Verification Agent  
**Final Governance Verdict**: **`BLOCKED — DATA ACQUISITION OR VALIDATION FAILED`**  

---

## 1. Governance Decision

Under the preregistered research protocol of Stage 3.17, the evaluation gate verdict is:

```
================================================================================
FINAL VERDICT: BLOCKED — DATA ACQUISITION OR VALIDATION FAILED
================================================================================
```

---

## 2. Decision Rationale & Supporting Evidence

### 2.1 Missing Benchmark Artifacts
The prerequisite dataset files for independent external validation are:
- `research/external_data/contextbench/full.parquet` (1,136 tasks, SHA-256: `2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8`, 26,102,607 bytes)
- `research/external_data/contextbench/contextbench_verified.parquet` (500 tasks, SHA-256: `e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791`, 9,558,250 bytes)

Neither file exists in [`research/external_data/contextbench/`](file:///F:/RepoNeedle/research/external_data/contextbench). Execution of [`research/external_data/contextbench/validate_contextbench.py`](file:///F:/RepoNeedle/research/external_data/contextbench/validate_contextbench.py) terminated with exit code `2` (`[STATUS: BLOCKED - DATA ACCESS]`).

### 2.2 Rejection of Synthetic Substitutes
In accordance with research integrity standards:
- The unofficial mirror `Schwerli/ContextBench` is strictly prohibited due to altered task distributions.
- Synthetically fabricated mock Parquet files are strictly prohibited.
- Generating fabricated benchmark metrics without live, authentic datasets is forbidden.

### 2.3 Strict Fail-Closed Protocol
Stage 3.17 governance explicitly mandates:
> *"If either file is missing or validation fails, stop and report `BLOCKED`. Do not proceed with evaluation."*

Therefore, the only valid decision under the research charter is **`BLOCKED — DATA ACQUISITION OR VALIDATION FAILED`**.

---

## 3. Alternative Options Ruled Out

1. **`PROCEED TO PRODUCTION INTEGRATION`**: **RULED OUT**. Production code integration requires prior independent validation on an external benchmark (ContextBench). ARB v2 internal development metrics alone are insufficient to rule out overfitting or verify multi-language generalization.
2. **`ITERATE — RETRIEVAL DEFICIT`**: **RULED OUT**. On internal ARB v2 data, the candidate champion `ARM-101-BASE` outperforms `BASE-BM25` ($0.2078$ vs $0.1752$ MRR, $p < 0.001$) and exhibits competitive performance with RepoMap ($0.2078$ vs $0.2293$, $p = 0.0559$). No retrieval deficit has been demonstrated on external data because external data has not yet been executed.
3. **`ITERATE — RESOURCE DEFICIT`**: **RULED OUT**. Query latency ($12.92\text{ ms}$ P50) satisfies the $<20\text{ ms}$ budget by a wide margin ($13.9\times$ faster than RepoMap). Memory consumption on Python/Go repositories is well within the 200 MB budget.

---

## 4. Current State of Evidence & Candidate Standing

### 4.1 Internal ARB v2 Benchmark (Frozen Evidence)
- **Candidate Champion (`ARM-101-BASE`)**:
  - MRR: **0.2078**
  - Recall@20: **0.5648**
  - Token BCY@8k: **0.2822**
  - P50 Latency: **12.92 ms**
  - Architecture: Soft Lexical Damping ($\tau=0.25$) + Level 1 Verified Function Call Edges
- **Lexical Baseline (`BASE-BM25`)**:
  - MRR: **0.1752**
  - Recall@20: **0.4535**
  - P50 Latency: **10.24 ms**
- **External Leader Reference (`BASE-REPOMAP`)**:
  - MRR: **0.2293**
  - Recall@20: **0.6599**
  - P50 Latency: **180.20 ms**
- **Candidate F (Invalidated)**:
  - MRR: **0.1351** on unconstrained corpus ($p = 0.0122$ worse than BM25).

### 4.2 Independent Validation Standing
- Official ContextBench evaluation: **0 / 1,136 tasks evaluated** (Blocked by dataset availability).
- External generalization claim: **UNPROVEN**.

---

## 5. Required Actions to Unblock Independent Validation

To unblock the evaluation gate, an operator with external internet access outside the sandbox must perform the following single-step download:

```bash
# 1. Download official ContextBench artifacts (commit c285579)
curl -L -o F:/RepoNeedle/research/external_data/contextbench/full.parquet \
  https://huggingface.co/datasets/Contextbench/ContextBench/resolve/c285579/data/full.parquet

curl -L -o F:/RepoNeedle/research/external_data/contextbench/contextbench_verified.parquet \
  https://huggingface.co/datasets/Contextbench/ContextBench/resolve/c285579/data/contextbench_verified.parquet

# 2. Verify file checksums
python F:/RepoNeedle/research/external_data/contextbench/validate_contextbench.py
# (Must output [PASS] for both files and exit with code 0)

# 3. Resume Stage 3.17 evaluation
python F:/RepoNeedle/research/contextbench_evaluation/adapter.py --run-evaluation
```
