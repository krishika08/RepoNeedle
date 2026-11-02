# RepoNeedle — Phase R4: Hybrid Retrieval Fusion Design

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R4 — Dense Semantic + Multi-Hop Structural Retrieval  
**Date**: November 2, 2026  
**Status**: System Architecture & Fusion Specification  

---

## 1. Architectural Challenge: The Dilemma of Multi-Modal Code Retrieval

Modern code search pipelines integrate three fundamentally distinct information signals:
1. **Lexical Matching (BM25 + SFS + TIP)**: High precision, exact identifier matching, highly vulnerable to vocabulary mismatch.
2. **Dense Semantic Matching (LSI / SVD Embeddings)**: Soft semantic matching, bridges conceptual synonyms, vulnerable to topological blurriness and seed distractors.
3. **Multi-Hop Structural Retrieval (Dependency Graph BFS)**: Traverses caller-callee and import topologies, captures ripple effects, vulnerable to hub accumulation and irrelevant structural siblings.

The central challenge in Phase R4 is designing a fusion strategy that synthesizes these disparate channels without permitting low-precision channels to degrade high-precision rankings.

---

## 2. Theoretical Analysis of Fusion Paradigms

### 2.1 Why Reciprocal Rank Fusion (RRF) Fails for Code Search
Reciprocal Rank Fusion is widely used in text search:
$$\text{RRF}(d) = \sum_{m \in \mathcal{M}} \frac{1}{k + \text{rank}_m(d)}$$

In code retrieval, RRF exhibits a fatal flaw: **Symmetric Trust**.
Because RRF considers only the ordinal ranks $\text{rank}_m(d)$ and discards score magnitudes, it treats an unanchored graph ranking or dense ranking with equal authority as an exact lexical match. When the dense model ranks a distractor utility file at Rank 1, RRF awards it $\frac{1}{60 + 1} = 0.0164$, artificially forcing it into the top-3 blended results even if its lexical score is zero.

### 2.2 Multiplicative Semantic Gating (Treatment D)
To overcome the symmetric trust problem, RepoNeedle introduces **Multiplicative Semantic Gating**:
$$\text{Score}_D(d) = \text{Score}_{\text{R2}}(d) \cdot \left(1.0 + \alpha_{\text{dense}} \cdot S_{\text{dense}}(q, d)\right) \quad (\alpha_{\text{dense}} = 0.3)$$

#### Mathematical Properties of Multiplicative Gating:
1. **Zero-Anchor Preservation**: If $\text{Score}_{\text{R2}}(d) = 0$, then $\text{Score}_D(d) \equiv 0$. Unrelated files with high dense similarity cannot jump into the candidate window.
2. **Lexical Candidate Disambiguation**: When multiple candidates share nearly identical lexical scores, dense semantic similarity acts as a decisive multiplier ($1.0 \le \text{Multiplier} \le 1.3$), prioritizing the true conceptual implementation file.
3. **Monotonicity**: The ranking preserves the established high-precision baseline order while performing local semantic refinement.

---

## 3. Calibrated Tri-Modal Hybrid Architecture (Treatment H)

Treatment H combines lexical, dense semantic, and multi-hop structural signals into a unified scoring function:
$$\text{Score}_H(d) = \text{Score}_{\text{R2}}(d) \cdot \left(1.0 + \alpha \cdot S_{\text{dense}}(q, d)\right) + \beta_{\text{intent}} \cdot S_{\text{graph}}(d)$$

### 3.1 Hyperparameter Calibration on Training Split ($N=210$)
Tuning on the 210 training queries established the following optimal coefficients:
- $\alpha = 0.25$: Semantic gating weight.
- $\beta_{\text{base}} = 0.05$: Base graph structural weight.
- Intent-Conditioned Graph Modulation:
  $$\beta_{\text{intent}} = \begin{cases} 
  0.10 & \text{if } \text{is\_test\_query} \land d \in \text{TestFiles} \\
  0.05 & \text{if } \neg\text{is\_test\_query} \land d \in \text{SourceFiles} \\
  0.01 & \text{otherwise (mismatched intent)}
  \end{cases}$$

---

## 4. Architectural Comparison of R4 Configurations

| Treatment Code | Method Name | Formulation | Operational Rationale |
| :---: | :--- | :--- | :--- |
| **A** | Frozen R2 Baseline | $\text{Score}_{\text{R2}}(d) = \text{BM25}(d) \cdot \text{SFS}(d) \cdot \text{TIP}(d)$ | Authoritative baseline reference |
| **B** | Dense Alone | $S_{\text{dense}}(q, d)$ | Pure semantic baseline |
| **C** | Graph Alone | $S_{\text{graph}}(d)$ | Pure structural baseline |
| **D** | R2 + Dense | $\text{Score}_{\text{R2}}(d) \cdot (1.0 + 0.30 \cdot S_{\text{dense}})$ | Multiplicative semantic gating |
| **E** | R2 + Graph | $\text{Score}_{\text{R2}}(d) + 0.10 \cdot S_{\text{graph}}$ | Lexical + structural combination |
| **F** | Dense + Graph | $S_{\text{dense}}(q, d) + 0.10 \cdot S_{\text{graph}}$ | Non-lexical hybrid baseline |
| **G** | R2 + Dense + Graph (Uncalibrated) | $\text{Score}_{\text{R2}}(d) + 0.20 \cdot S_{\text{dense}} + 0.10 \cdot S_{\text{graph}}$ | Additive linear combination |
| **H** | Calibrated Hybrid Fusion | $\text{Score}_{\text{R2}}(d) \cdot (1 + 0.25 \cdot S_{\text{dense}}) + \beta_{\text{intent}} \cdot S_{\text{graph}}$ | Calibrated tri-modal gated hybrid |

