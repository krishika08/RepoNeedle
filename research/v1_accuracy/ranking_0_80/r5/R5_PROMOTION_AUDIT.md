# RepoNeedle — Phase R5: Promotion Readiness and Independent Validation Audit

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R5 — Function-Level, Change-Aware Code Retrieval  
**Auditor**: Principal ML Systems Engineer & Information Retrieval Research Auditor  
**Date**: November 2, 2026  
**Status**: Formal Promotion Audit  

---

## 1. Executive Summary & Audit Mandate

Following the completion of Phase R5, **Treatment F (Change-Impact Retrieval using Typed Graphs)** emerged as the research champion, achieving:
- **Validation MRR**: **0.3235** vs Baseline **0.2971** ($\Delta = +0.0264$, +8.88% relative).
- **Held-Out MRR**: **0.3183** vs Baseline **0.2965** ($\Delta = +0.0218$, +7.35% relative).
- **Validation Recall@20**: **0.5958** vs Baseline **0.5875**.
- **Held-Out Recall@20**: **0.6244** vs Baseline **0.5800** (+4.44 percentage points).
- **Inference Latency**: **0.541 ms mean** CPU query latency.

This independent audit evaluates whether Treatment F is ready for production promotion or whether it must be retained under the research track.

---

## 2. Summary Audit Verdict

| Audit Dimension | Finding / Status | Compliance Verdict |
| :--- | :--- | :---: |
| **1. Frozen Baseline Reproduction** | R2 Baseline (0.2971 / 0.2965) and Treatment F (0.3235 / 0.3183) reproduced bit-for-bit | **VERIFIED** |
| **2. Repository & Query Provenance** | 100% overlap with previously evaluated R1–R4 repositories. Zero virgin external repos | **DISCLOSED / LIMITED** |
| **3. Statistical Validation** | Validation gain is significant ($p = 0.0007$); Held-out CI spans zero ($p = 0.0843$) | **PARTIALLY BOUNDED** |
| **4. Feature Leakage & Zero-Oracle** | Zero gold label, track, or answer leakage. Edges inferred purely from code & query | **VERIFIED CLEAN** |
| **5. Code & Production Performance** | 291/291 tests pass; CUD-Pack budget invariant preserved; 42 $\mu$s incremental reindex | **VERIFIED PRODUCTION-GRADE** |
| **6. Git & Publication Integrity** | Working tree clean; `reponeedle/` production untouched; v0.1.0 tag frozen | **VERIFIED CLEAN** |

### Formal Decision:
**DECISION B: RETAIN AS RESEARCH CHAMPION**  
*Treatment F is the definitive algorithmic champion of Phase R5, demonstrating remarkable architectural speed (0.54 ms) and consistent gains across tasks. However, because the held-out partition has 100% repository overlap with previous research phases and its isolated clustered CI spans zero ($p = 0.0843$), automatic production promotion is withheld until validation on a truly independent external benchmark.*

---

## 3. High-Level Findings by Audit Section

### 3.1 Provenance Reality
The 5 repositories assigned to the "held-out" split (`huggingface/transformers`, `vitejs/vite`, `pytest-dev/pytest`, `astral-sh/ruff`, `python/mypy`) are identical to those inspected in Phase R2 and R4. There are zero new repositories present on local storage. All held-out metrics must be honestly labeled as **internal diagnostic confirmation**.

### 3.2 Statistical Precision
- **Validation Cluster ($K=5$)**: Observed $\Delta = +0.0264$, 95% Clustered CI: `[+0.0040, +0.1250]` ($p = 0.0007$). Statistically significant.
- **Held-Out Cluster ($K=5$)**: Observed $\Delta = +0.0218$, 95% Clustered CI: `[-0.0088, +0.0637]` ($p = 0.0843$). While positive in expectation and improving Recall@20 by +4.44 percentage points, the confidence interval crosses zero on the 5 held-out clusters alone.
- **Jackknife Stability**: Leave-one-repository-out testing proves that no single repository is responsible for the observed gains; Treatment F remains positive across every 4-repository combination.

### 3.3 Zero Leakage Assurance
The `ChangeImpactEngine` was audited line-by-line. It derives seeds from `query_text` alone and constructs typed relationships (`TESTS_BEHAVIOR`, `CHANGED_CALLER`, `IMPORTS_DEPENDENCY`, `MODULE_BUILD_CONFIG`) using static token overlap and directory hierarchies. Ground truth gold file paths are completely absent from inference inputs.

### 3.4 Production Integration Boundaries
Production package `reponeedle/` and CUD-Pack context packing remain 100% decoupled from R5 research modules. All 10 CUD-Pack token budget regression tests pass without violation.

