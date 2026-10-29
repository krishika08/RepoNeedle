# RepoNeedle Stage 3.12A: Research Design Specification for Stage 3.12

**Document**: `research/stage3_12a/STAGE3_12_DESIGN_SPEC.md`  
**Stage**: Stage 3.12A — Canonical Evaluation Reconciliation and Graph Research Gate  
**Date**: October 29, 2026  
**Status**: APPROVED RESEARCH DESIGN SPECIFICATION  

---

## 1. Context and Problem Statement

Stage 3.11 and the Stage 3.12A reconciliation established two pivotal empirical facts:
1. **The Rank 1–3 Freeze Bottleneck**: Under the rigid Rank 1–3 freeze, `FUNCTION-GRAPH` achieved $0.1901$ MRR ($+1.00\%$ relative gain over `CONTROL-CASCADE`), but **82.0% of all queries (283/345) remained exact ties**. The freeze capped maximum MRR gain per query at $\frac{1}{4} - \frac{1}{5} = +0.050$, causing `FUNCTION-GRAPH` to fall short of the preregistered $+2.0\%$ gate.
2. **The Unconstrained Surge and Regression**: Removing the freeze in `FUNCTION-GRAPH-NO-FREEZE` unleashed a massive $+10.6\%$ relative MRR improvement ($0.2082$ MRR, $139$ wins vs $23$ losses). However, it introduced **23 regressions**, primarily where high in-degree utility modules (`utils.py`, `helpers.py`, `compat.py`) absorbed excess graph boost and displaced domain implementation files.

Stage 3.12 is therefore **fully justified** to evaluate four targeted, factorial algorithmic hypotheses designed to capture the $+10.6\%$ gain while suppressing utility hub regressions.

---

## 2. Research Hypotheses

### Hypothesis A: Soft Lexical Damping
- **Mechanism**: Replace the binary Rank 1–3 freeze with a dynamic lexical margin gate. A candidate at rank $\ge 2$ may displace a Rank 1 lexical seed if and only if its fused score exceeds the Rank 1 score by a calibrated margin $\delta_{\text{lex}} = \tau \cdot (\text{BM25}_1 - \text{BM25}_2)$.
- **Prediction**: Protects high-confidence lexical hits where BM25 has a dominant lead, while allowing candidates with overwhelming function-level graph evidence to promote to rank 1.

### Hypothesis B: In-Degree Hub Attenuation
- **Mechanism**: Scale incoming graph diffusion boost by an inverse logarithmic fan-in penalty:
  $$W_{\text{hub}}(v) = \frac{1}{\log_2(2 + \text{deg}_{\text{in}}(v))}$$
- **Prediction**: Suppresses the 11 hub-and-spoke utility sink regressions identified in `FAILURE_ANALYSIS.md` without diminishing genuine point-to-point caller-callee edges.

### Hypothesis C: Level-1 Verified Call Edges Only
- **Mechanism**: Exclude Level-2 structural method heuristic edges, restricting graph propagation strictly to Level-1 verified edges (`verified_call`, `unique_global_call`, `class_to_test`).
- **Prediction**: Eliminates the 1 net regression caused by ambiguous method names in Stage 3.11, maximizing precision.

### Hypothesis D: Factorial Interaction
- **Mechanism**: Simultaneously integrate Verified-Only Edges (C) + Hub Attenuation (B) + Soft Lexical Damping (A).
- **Prediction**: Achieves $\ge +5.0\%$ relative MRR gain over `CONTROL-CASCADE` ($\text{MRR} \ge 0.1975$) with $< 10$ query regressions across the entire benchmark.

---

## 3. Predefined Experimental Arms for Stage 3.12

To ensure clean factor attribution without confounding, Stage 3.12 will evaluate 7 controlled arms:

| Arm ID | Configuration Name | Graph Edges | Hub Attenuation | Lexical Safeguard Policy | Primary Research Role |
| :---: | :--- | :--- | :---: | :--- | :--- |
| **Arm 0** | `CONTROL-CASCADE` | Base Imports only | None | Rigid Rank 1–3 Freeze | Mandatory Control Baseline |
| **Arm 1** | `STAGE3_11-FROZEN` | Level 1 + Level 2 | None | Rigid Rank 1–3 Freeze | Stage 3.11 Primary Reference |
| **Arm 2** | `STAGE3_11-NO-FREEZE` | Level 1 + Level 2 | None | No Freeze (Unconstrained) | Stage 3.11 Exploratory Reference |
| **Arm 3** | `ABLATION-VERIFIED-ONLY` | Level 1 Verified only | None | No Freeze | Isolated Test of Hypothesis C |
| **Arm 4** | `ABLATION-HUB-ATTENUATED` | Level 1 Verified only | Logarithmic Fan-In | No Freeze | Isolated Test of Hypothesis B |
| **Arm 5** | `ABLATION-SOFT-DAMPED` | Level 1 + Level 2 | None | Soft Margin Gating ($\tau = 0.25$) | Isolated Test of Hypothesis A |
| **Arm 6** | `STAGE3_12-PROPOSED` | Level 1 Verified only | Logarithmic Fan-In | Soft Margin Gating ($\tau = 0.25$) | Full Factorial Test (Hypothesis D) |

---

## 4. Evaluation Protocol and Governance Gates

1. **Candidate Pool**: 100% unconstrained candidate pool across all 218 snapshots ($N = 345$ positive queries).
2. **Benchmark Nature**: Formal designation as an internal development/regression benchmark.
3. **Acceptance Thresholds for Arm 6 Promotion**:
   - $\ge +2.0\%$ relative MRR gain over `CONTROL-CASCADE` ($\text{MRR} \ge 0.1920$).
   - 95% repository-clustered bootstrap confidence interval strictly excluding zero ($10{,}000$ replicates).
   - Fractional Recall@20 non-inferior within $0.5\text{ pp}$ ($\Delta \ge -0.0050$).
   - Net win-to-loss ratio $\ge 3 : 1$.
   - Median warm query latency $< 25\text{ ms}$, process RSS scalable.
