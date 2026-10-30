# Stage 3.21 Formal Governance Decision & Verdict Report

**Date:** 2026-10-30  
**Stage:** 3.21  
**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Starting Commit:** `0b8ce84`  
**Decision Gate:** Final Evaluation & Benchmark Integrity Audit  

---

## 1. Formal Governance Decision & Selection

In accordance with the Stage 3.21 mandate, the three potential evaluation verdicts were evaluated strictly on empirical evidence:

- **Verdict A: Reconciled and independently validated**
  *Disqualified.* The independent external validation gate on official ContextBench (`EuniAI/ContextBench`, revision `c285579`) remains blocked by network boundary constraints. No official evaluation has occurred.
- **Verdict B: Internally reproducible; external validation still blocked**
  *SELECTED.* All internal benchmark accounting discrepancies (ARB v2 task distributions, the `0.000010` parity delta, and the `198 MB` vs `286.7 MB` RSS discrepancy) have been forensically resolved with bit-for-bit reproducibility. The production implementation has been hardened and verified across five languages. The external validation gate is documented and remains strictly blocked.
- **Verdict C: Material discrepancies remain unresolved**
  *Disqualified.* Zero unresolved numerical or architectural discrepancies remain.

### Formal Selected Verdict:
# **`B — INTERNALLY REPRODUCIBLE; EXTERNAL VALIDATION STILL BLOCKED`**

---

## 2. Binding Policy Decisions

1. **Default Production Ranker:**
   `RepoNeedleEngine.retrieve()` **must retain `"legacy"` as the default ranker**. Promotion of ARM-101 to default is strictly conditioned on external validation against ContextBench.
2. **ARB v2 Benchmark Role:**
   ARB v2 (345 positive instances) is formally designated as an internal development, regression, and unit verification corpus. It is **never** to be cited as independent evidence of cross-corpus generalizability.
3. **External Literature Baselines:**
   Upstream RepoMap's published `180.20 ms` latency scalar is classified as an external literature reference. It must never be used to claim an empirical speedup ratio against RepoNeedle's local Windows 11 `perf_counter` measurements.
4. **ContextBench Gate Policy:**
   Under no circumstances may synthetic queries, unverified mirrors, or mock data be substituted for official ContextBench Parquet files. The gate will remain `BLOCKED` until official artifacts are supplied out-of-band and validated via `research/stage3_21/ingest_contextbench.py`.

---

## 3. Summary of Resolved Discrepancies

| Discrepancy Audited | Prior Conflicting Reports | True Reconciled Finding | Status |
| :--- | :--- | :--- | :---: |
| **ARB v2 Task Counts** | 70/92/113/70 in Stage 3.20 report prose vs. 106/58/80/101 in historical data | Purely clerical narrative error in Stage 3.20 report. Underlying raw data and all result CSVs evaluate 106/80/101/58. | **RESOLVED** |
| **ARM-101 Parity Delta** | Stage 3.20 claimed $345/345$ exact match but reported delta $0.000010$ | Artifact of subtracting 4-decimal literal `0.2078` from unrounded float mean `0.2077904`. Per-query delta is `0.0000000000`. | **RESOLVED** |
| **RepoMap MRR Variance** | $0.2140$ vs. $0.2293$ vs. $0.6599$ | $0.2140$ was early hardcoded constant; $0.6599$ was Recall@20; $0.2293$ is the canonical unconstrained MRR. | **RESOLVED** |
| **Peak RSS Accounting** | 198.0 MB on leaderboard vs. 286.7 MB in etcd resource experiment | Leaderboard reported Caddy (605 files); etcd (1,431 files) requires 286–312 MB. Memory scales with repo size. | **RESOLVED** |
| **Syntax Error Swallowing** | Fallback regex swallowed functions after unclosed parenthesis | Fixed regex pattern in `function_graph.py` to `[^)\r\n]*`, tested with full suite passing. | **HARDENED** |
