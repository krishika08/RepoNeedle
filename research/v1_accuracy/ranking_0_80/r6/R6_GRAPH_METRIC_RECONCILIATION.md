# RepoNeedle — Phase R6: Graph Metric Reconciliation & Statistical Terminology Audit

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R6 — Controlled Production Integration  
**Author**: Principal ML Systems Engineer & Statistical Inference Auditor  
**Date**: November 2, 2026  
**Status**: Formal Arithmetic & Denominator Reconciliation  

---

## 1. Executive Summary & Audit Mandate

In Phase R6 documentation, two apparent discrepancies were noted in the reported graph metrics:
1. `427 confirmed edges` vs `380 classified candidate edges`.
2. `656 heuristic edges` vs `638 classified candidate edges`.

This audit reconciles the exact accounting arithmetic, defines the exact denominator for every reported metric, and aligns statistical terminology with standard information retrieval and classification conventions.

---

## 2. Arithmetic Reconciliation: Edges vs Candidates

The discrepancy arises from distinguishing between **total edge instances** and **unique candidate files carrying an edge**:

### 2.1 Confirmed Relationships Reconciliation
- **Total Confirmed Edge Instances Extracted**: **427 edges**
  - Static AST Imports (`confirmed_import`): **380**
  - Public Symbol Matches (`confirmed_symbol`): **40**
  - Call Invocation References (`confirmed_call`): **2**
  - Build Manifest Links (`confirmed_build`): **5**
  - **Sum**: $380 + 40 + 2 + 5 = \mathbf{427}$ (Exact Match).

- **Unique Candidate Files with $\ge 1$ Confirmed Edge**: **380 candidates**
  - True Positive Candidates (Gold Targets): **130**
  - False Positive Candidates (Distractors): **250**
  - **Sum**: $130 + 250 = \mathbf{380}$ (Exact Match).
  - *Note*: 47 candidate files carried multiple confirmed edges simultaneously (e.g. both an AST import and a public symbol match), explaining why $427 - 380 = 47$ multi-edge instances exist.

### 2.2 Heuristic Relationships Reconciliation
- **Total Heuristic Edge Instances Extracted**: **656 edges**
  - Hierarchical Ancestor Proximity (`heuristic_ancestor`): **455**
  - Sibling Directory Proximity (`heuristic_dir_proximity`): **157**
  - Test Stem Token Overlap (`heuristic_test_stem`): **44**
  - **Sum**: $455 + 157 + 44 = \mathbf{656}$ (Exact Match).

- **Unique Candidate Files with $\ge 1$ Heuristic Edge**: **638 candidates**
  - True Positive Candidates (Gold Targets): **66**
  - False Positive Candidates (Distractors): **572**
  - **Sum**: $66 + 572 = \mathbf{638}$ (Exact Match).
  - *Note*: 18 candidate files matched multiple heuristic criteria simultaneously (e.g. both sibling proximity and ancestor containment).

---

## 3. Denominators for Precision & False-Positive Metrics

### 3.1 Empirical Precision
In classification and IR, precision is defined as:
$$\text{Precision} = \frac{\text{True Positives (TP)}}{\text{Total Positive Predictions (TP + FP)}}$$

- **Confirmed Precision**:
  $$\text{Precision}_{\text{conf}} = \frac{130}{130 + 250} = \frac{130}{380} = \mathbf{34.21\%}$$
  *(Denominator: 380 unique candidate files flagged with confirmed edges).*

- **Heuristic Precision**:
  $$\text{Precision}_{\text{heur}} = \frac{66}{66 + 572} = \frac{66}{638} = \mathbf{10.34\%}$$
  *(Denominator: 638 unique candidate files flagged with heuristic edges).*

### 3.2 False Positive Rate (FPR) vs False Discovery Rate (FDR)
In conventional statistical classification:
$$\text{FPR} = \frac{\text{False Positives (FP)}}{\text{Actual Negatives (N)}} = \frac{\text{FP}}{\text{Total Non-Gold Candidates}}$$

Across all 180 queries in the benchmark:
- Total Candidate Files Examined: **9,683**
- Total Gold Target Occurrences: **216**
- Total Actual Negatives ($N$): $9,683 - 216 = \mathbf{9,467}$ non-gold candidates.

Using the exact denominator ($N = 9,467$):
- **Confirmed FPR**:
  $$\text{FPR}_{\text{conf}} = \frac{250}{9,467} = \mathbf{2.64\%} \quad (0.0264)$$

- **Heuristic FPR**:
  $$\text{FPR}_{\text{heur}} = \frac{572}{9,467} = \mathbf{6.03\%} \quad (0.0603)$$

- **Correction on Terminology**:
  In informal discussion, researchers sometimes erroneously refer to $1 - \text{Precision} = \frac{\text{FP}}{\text{TP} + \text{FP}}$ as the "false positive rate". In rigorous biostatistics and machine learning, $\frac{\text{FP}}{\text{TP} + \text{FP}}$ is the **False Discovery Rate (FDR)**:
  - Confirmed FDR: $250 / 380 = \mathbf{65.79\%}$
  - Heuristic FDR: $572 / 638 = \mathbf{89.66\%}$
  - True False Positive Rate ($\text{FP} / \text{Actual Negatives}$): Confirmed is **2.64%**, Heuristic is **6.03%**.

