# RepoNeedle Stage 3.16 — Executive Decision Report

**Document ID**: `STAGE3-16-DECISION-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `143e8bc`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`)  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`)  

---

## 1. Formal Governance Verdict

```
================================================================================
FINAL RESEARCH VERDICT: [BLOCKED — EXTERNAL DATA ACQUISITION REQUIRED]
================================================================================
```

### 1.1 Decision Rationale
1. **Network Sandbox Boundary Isolation**:
   - Automated attempts to acquire the official dataset `Contextbench/ContextBench` from Hugging Face Hub and GitHub endpoints returned `HTTP Error 403: Forbidden`.
   - In accordance with research safeguards, network isolation was not bypassed, TLS checks were not disabled, and unauthorized proxies were not used.
2. **Rejection of Unofficial Mirrors and Mock Artifacts**:
   - Third-party re-uploads such as `Schwerli/ContextBench` diverge in task row count and schema, and are strictly prohibited from being substituted for the official benchmark.
   - Fabricating synthetic mock Parquet files to manufacture a completion verdict was strictly rejected as a research integrity violation.
3. **Infrastructure Readiness**:
   - The dataset intake layer ([`research/external_data/contextbench/`](file:///F:/RepoNeedle/research/external_data/contextbench)) and evaluation adapter ([`research/contextbench_evaluation/`](file:///F:/RepoNeedle/research/contextbench_evaluation)) are fully implemented, verified, and operational with fail-closed validation and information leakage guards.
4. **Independent Validation Gate Remains Closed**:
   - A well-documented intake pipeline is valuable progress, but it is **not external validation**.
   - No independent evaluation on ContextBench has been performed or claimed.
   - Stage 3.17 algorithm tuning is **STRICTLY PROHIBITED** until this gate is unblocked and genuine external evaluation of `ARM-101-BASE` is completed.

---

## 2. Research Claims Boundary Ledger

In accordance with Section 6 of the Stage 3.16 charter, all research claims are partitioned across two unambiguous categories:

### 2.1 Established on ARB v2 Development Benchmark
- **`ARM-101-BASE` Retrieval Quality**: Achieves **$0.2078$ MRR**, **$0.5648$ Recall@20**, and **$0.2822$ Token BCY@8k** on the canonical 345 positive ARB v2 queries.
- **`ARM-101-BASE` Operational Latency**: Achieves **$12.92\text{ ms}$ P50 query latency** ($>13.9\times$ faster than RepoMap at $180.20\text{ ms}$).
- **`BASE-REPOMAP` Retrieval Quality**: Holds highest ARB v2 MRR point estimate (**0.2293**), but its advantage over `ARM-101-BASE` was not statistically significant at the 0.05 level ($p = 0.0559$).
- **Candidate F Collapse**: Achieves **$0.1351$ MRR** on unconstrained candidate pools (collapsing by $-37.2\%$, inferior to pure BM25 $0.1752$, $p = 0.0122$).
- **Disproof of 100 MB Process Ceiling**: Native Windows RSS on full Caddy (605 files) is $198.0\text{ MB}$ ($272.8\text{ MB}$ peak); etcd is $364.1\text{ MB}$.

### 2.2 NOT YET ESTABLISHED (Forbidden Claims)
- **Generalization to Independent Repositories**: Has not been demonstrated on held-out distributions.
- **Performance on Official ContextBench**: Unmeasured; zero tasks evaluated.
- **Downstream SWE-bench Issue Resolution**: Bounded strictly to file-level retrieval; downstream patch generation rates are unverified.
- **Superiority over RepoMap in Quality**: RepoNeedle does not beat RepoMap on global polyglot retrieval quality.

---

## 3. Next Single Step to Resolve Gate

Execute authorized external operator acquisition of `full.parquet` (1,136 tasks) and `contextbench_verified.parquet` (500 tasks) from `https://huggingface.co/datasets/Contextbench/ContextBench`, place them in `research/external_data/contextbench/`, and execute the adapter.
