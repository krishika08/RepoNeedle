# RepoNeedle — Phase R5: Formal Promotion Decision

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R5 — Function-Level, Change-Aware Code Retrieval  
**Date**: November 2, 2026  
**Auditor**: Principal ML Systems Engineer & Information Retrieval Research Auditor  
**Status**: Formal Architectural & Promotion Verdict  

---

## 1. Executive Summary & Audit Conclusion

Following a comprehensive audit across data provenance, statistical inference, feature leakage, computational performance, and Git publication status, the formal decision on Phase R5 is:

```
========================================================================================
                          FORMAL PROMOTION AUDIT DECISION
========================================================================================

    [ DECISION B: RETAIN AS RESEARCH CHAMPION ]

    Treatment F (Change-Impact Retrieval with Typed Dependency Graphs) is retained
    as the AUTHORITATIVE RESEARCH CHAMPION of Phase R5 under the research track.

    Automatic promotion to the production default ranker is DEFERRED until
    independent validation is demonstrated on virgin, unexamined code repositories.

========================================================================================
```

---

## 2. Rationale for Decision B

### 2.1 Why Not Decision A (REJECT)?
Rejection is wholly unwarranted:
1. **Flawless Code Quality & Integrity**: The implementation passes all **291 unit, integration, and regression tests** in 19.41s with zero errors.
2. **Zero Feature Leakage**: Audited line-by-line; all typed graph edges are inferred strictly from observable source code structures and query text. Ground truth target paths are never referenced.
3. **Statistically Significant Validation Superiority**: On the primary validation split, Treatment F delivers a **+8.88% relative MRR boost** ($0.2971 \to 0.3235$), with a repository-clustered 95% CI strictly bounded above zero (`[+0.0040, +0.1250]`, $p = 0.0001$).
4. **Sub-Millisecond Speed**: Runs at **0.541 ms mean query latency** with only **3.96 MB peak RAM**.

### 2.2 Why Not Decision C (APPROVE FOR CONTROLLED INTEGRATION)?
Direct promotion to production integration cannot be justified under strict IR research governance:
1. **100% Repository Overlap**: The 5 repositories in the "held-out" split (`transformers`, `vite`, `pytest`, `ruff`, `mypy`) have 100% overlap with previously evaluated R2–R4 datasets. There are zero unexamined repositories on disk.
2. **Held-Out Clustered CI Crosses Zero**: On the 5 held-out clusters alone, the 95% bootstrap CI spans zero: `[-0.0088, +0.0637]` ($p = 0.0843$). While the empirical delta is positive ($\Delta = +0.0218$), it does not achieve statistical significance at $\alpha = 0.05$ on held-out clusters alone.
3. Per the audit mandate: *"Do not use an overall confidence interval as evidence of held-out significance."* Therefore, claiming held-out significance would be scientifically dishonest.

---

## 3. Preserved Baselines & State of the Codebase

- **Production Package**: `reponeedle/` remains 100% untouched and clean.
- **Frozen Reference**: **R2 Treatment E** remains the authoritative production reference baseline.
- **Research Champion**: **R5 Treatment F** is archived under `research/v1_accuracy/ranking_0_80/r5/` as the reigning champion for next-generation research.
- **Candidate Pool Recall**: Preserved at **100.0%** (514/514 gold files).
- **CUD-Pack Safety**: Token budget invariants remain 100% intact.

---

## 4. Path to Production Promotion (Phase R6 Requirements)

To graduate Treatment F from **Decision B (Research Champion)** to **Decision C (Controlled Production Integration)**:
1. **External Benchmark Acquisition**: Ingest a new, independently annotated benchmark (such as SWE-bench instances) covering at least 15 unexamined repositories.
2. **Zero-Shot External Evaluation**: Evaluate Treatment F against Treatment E on the external benchmark without retraining or hyperparameter tuning.
3. **Clustered Significance Gate**: If Treatment F achieves $p < 0.05$ on the external clustered bootstrap, promote Treatment F as the production default ranker in RepoNeedle V1.1.

