# RepoNeedle — Phase R5: Hierarchical Hybrid Architecture

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R5 — Function-Level, Change-Aware Code Retrieval  
**Date**: November 2, 2026  
**Status**: System Architecture Specification  

---

## 1. Architectural Overview

Phase R5 unifies five distinct layers of code intelligence into a cohesive, hierarchical retrieval pipeline:

```
                  ┌────────────────────────────────────────┐
                  │          Developer Text Query          │
                  └───────────────────┬────────────────────┘
                                      │
                   [ Query Context & Intent Extraction ]
                 (Regex / Lexical Patterns, Zero-Oracle)
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
   [ Definition ]             [ Trace / Error ]            [ Test Intent ]
          │                           │                           │
  ┌───────┴───────────────────────────┴───────────────────────────┴───────┐
  │                        Candidate Pool Filtering                       │
  │                     (M1 Full Candidate Pool: 100% Recall)             │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────┴───────────────────────────────────┐
  │ Tier 1: Lexical Anchor (BM25 + Seed File Suppression + Test Prior)     │
  │         Score_R2(d) = BM25(d) * SFS(d) * TIP(d)                       │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────┴───────────────────────────────────┐
  │ Tier 2: Fine-Grained Code-Unit Alignment                              │
  │         Score_unit(d) = max_{u in Units(d)} CodeUnitScorer(u, Q)      │
  │         Extracts exact Function, Method, and Line Spans (L_start-end) │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────┴───────────────────────────────────┐
  │ Tier 3: Typed Change-Impact Propagation                               │
  │         S_impact(d) = sum_{s in Seeds} EdgeWeight(type, Intent)       │
  │         (TESTS_BEHAVIOR, CHANGED_CALLER, IMPORTS, BUILD_CONFIG)       │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
  ┌───────────────────────────────────┴───────────────────────────────────┐
  │ Final Gated Fusion (Treatment F Formulation)                          │
  │ Score_final(d) = Score_R2(d) * (1.0 + alpha_impact * S_impact(d))     │
  └───────────────────────────────────┬───────────────────────────────────┘
                                      │
                  ┌───────────────────▼────────────────────┐
                  │ Ranked Candidates + Source Spans       │
                  │ (Passed to CUD-Pack Context Engine)   │
                  └────────────────────────────────────────┘
```

---

## 2. Mathematical Formulations of R5 Configurations

### 2.1 Treatment F: Change-Impact Retrieval (The Primary R5 Advance)
Treatment F injects typed structural change propagation as a multiplicative gate on top of the lexical baseline:
$$\text{Score}_F(d) = \text{Score}_{\text{R2}}(d) \cdot \left(1.0 + \alpha_{\text{impact}} \cdot S_{\text{impact}}(d)\right) \quad (\alpha_{\text{impact}} = 0.20)$$

#### Key Properties:
1. **Zero-Anchor Invariance**: If a file has zero lexical or relational relevance ($\text{Score}_{\text{R2}} = 0$), it cannot be promoted purely by graph adjacency.
2. **Intent-Conditioned Propagation**: When the query is categorized as `TEST`, test-verifying edges (`TESTS_BEHAVIOR`) receive a $1.6\times$ multiplier. When the query is `REFERENCE` or `ERROR`, reverse caller edges (`CHANGED_CALLER`) receive a $1.5\times$ multiplier.
3. **Hub Dampening**: Nodes with total degree $> 15$ are dampened by $\frac{1}{\sqrt{\text{deg}}}$, preventing utility files from monopolizing scores.

### 2.2 Treatment H: Combined Hierarchical Retrieval
Treatment H integrates code-unit scores, dense semantic scores, and typed impact scores:
$$\text{Score}_H(d) = \text{Score}_{\text{R2}}(d) \cdot \left(1.0 + 0.25 \cdot S_{\text{unit}}(d) + 0.15 \cdot S_{\text{dense}}(d) + 0.10 \cdot S_{\text{impact}}(d)\right)$$
Followed by Role-Aware MMR diversity selection for the top-20 ranks.

---

## 3. Architectural Verdict: Why Treatment F is Preferred over Treatment H

| Dimension | Treatment F (Change-Impact) | Treatment H (Combined Hierarchical) | Winner |
| :--- | :---: | :---: | :---: |
| **Validation MRR** | **0.3235** | 0.3023 | **Treatment F** (+7.0% relative) |
| **Held-Out MRR** | **0.3183** | 0.2851 | **Treatment F** (+11.6% relative) |
| **Validation Recall@20** | **0.5958** | 0.4944 | **Treatment F** (+20.5% relative) |
| **Held-Out Recall@20** | **0.6244** | 0.5644 | **Treatment F** (+10.6% relative) |
| **Complete Coverage** | **63.8%** | 56.8% | **Treatment F** (+12.3% relative) |
| **Query Latency** | **0.541 ms** | 49.76 ms | **Treatment F** (92x faster) |
| **Architectural Simplicity** | Clean typed edge propagation | Complex multi-modal MMR pipeline | **Treatment F** |

**Conclusion**: Treatment F represents the cleanest, fastest, and most accurate architectural evolution in Phase R5.

