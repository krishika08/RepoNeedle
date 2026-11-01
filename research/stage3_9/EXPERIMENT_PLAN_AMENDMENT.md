# Stage 3.9.3: Experiment Plan Governance Amendment
## Resolution of Experimental Confounding & Strictly Decoupled Factorial Ablation Matrix

**Document ID**: `STAGE3-9-AMENDMENT-001`  
**Stage**: Stage 3.9.3 — Python-First LFCG Implementation and Validation  
**Date**: November 1, 2026  
**Workspace**: `F:\RepoNeedle`  
**Active Branch**: `research/stage3_9`  
**Governing Status**: **FORMAL EXPERIMENT PLAN AMENDMENT TO STAGE3-9-PLAN-002 & STAGE3-9-PLAN-003**  
**Governing Rule**: Do not combine ambiguity penalties and provenance confidence into a single step if claiming individual attribution. Keep the projection rule fixed across graph experiments or isolate it in dedicated ablations. Preserve experiment history and map all sub-experiment IDs.

---

## 1. Audit of Experimental Confounding in Prior Plans

In Stage 3.9.1 and Stage 3.9.2, two critical experimental confoundings remained unresolved:
1. **Ambiguity Penalty vs. Provenance Weighting Confounding**:
   `EXP-392b` was specified as $W(e) = \phi(e) \cdot \frac{1}{\sqrt{A(e)}}$, introducing both the **heuristic provenance weight $\phi(e)$** and the **single candidate ambiguity penalty $\Omega(e)$** simultaneously. If an improvement or regression occurred, it was mathematically impossible to determine whether the effect stemmed from candidate ambiguity penalization or from tier weighting.
2. **Graph Structure vs. Symbol-to-File Projection Confounding**:
   The transition from function-level scores to file-level scores (Max-Pooling vs. Sum-Pooling vs. Softmax) was mixed into the composite evaluation (`EXP-394` / `EXP-395`). Because the downstream benchmark evaluates file retrieval, the pooling operator exerts a major confounding influence on final MRR.

---

## 2. Decoupled One-Variable-at-a-Time Evaluation Architecture

To enforce scientific rigor, every transition in Stage 3.9 will change **exactly one identifiable independent variable**. The projection rule is **strictly held constant** at Max-Pooling ($\lambda = 0.20$) for all topological experiments (`EXP-391` through `EXP-394`), and evaluated in its own dedicated ablation suite (`EXP-395a/b/c`):

```mermaid
graph TD
    EXP391["EXP-391 (Control Baseline)<br>Exact EXP-386 File-Level Graph<br>MRR: 0.2062"]
    
    EXP391 -->|Var 1: Raw function edges W=1.0| EXP392a["EXP-392a (Raw Invocation Edges)<br>Isolates fine granularity"]
    
    EXP392a -->|Var 2A: Ambiguity Penalty Only| EXP392b["EXP-392b (Ambiguity Penalty Only)<br>W = 1/sqrt(A), phi = 1.0"]
    EXP392a -->|Var 2B: Provenance Weighting Only| EXP392c["EXP-392c (Provenance Weighting Only)<br>W = phi(e), Omega = 1.0"]
    
    EXP392b & EXP392c -->|Var 2C: Joint Ambiguity + Provenance| EXP392d["EXP-392d (Joint Calibrated Edges)<br>W = phi(e) * 1/sqrt(A)"]
    
    EXP392d -->|Var 3A: Symbol Frequency Only| EXP393a["EXP-393a (sIDF Dampened Only)<br>Isolates sIDF hub attenuation"]
    EXP392d -->|Var 3B: In-Degree Normalization Only| EXP393b["EXP-393b (Degree Normalized Only)<br>Isolates topological degree attenuation"]
    
    EXP393a & EXP393b -->|Var 4: Joint Dampening Composite| EXP394["EXP-394 (Joint Composite LFCG)<br>Combines sIDF + Degree (Fixed Max-Pool)"]
    
    EXP394 -->|Var 5A: Max-Pooling (Fixed)| EXP395a["EXP-395a (Max-Pooling Projection)"]
    EXP394 -->|Var 5B: Sum-Pooling| EXP395b["EXP-395b (Sum-Pooling Projection)"]
    EXP394 -->|Var 5C: Softmax Pooling| EXP395c["EXP-395c (Softmax Top-K Projection)"]
    
    EXP395a -->|Var 6: Query Conditioning| EXP396["EXP-396 (Query-Conditioned LFCG)<br>Dynamic Lexical Edge Gating"]
```

---

## 3. Comprehensive Experiment Registry Mapping

| New Experiment ID | Historical ID | Configuration Name | Independent Variable Isolated | Control Baseline | Mathematical Edge Weight $W(e)$ & Projection | Primary Attribution Target |
|---|---|---|---|---|---|---|
| **`EXP-391`** | `EXP-391` | **`CONTROL-EXP386-REPRO`** | **None (Exact File Baseline)** | Historical `EXP-386` | $W_{\text{file}}(e)$ (coarse file graph) | Exact baseline reproduction (MRR **0.2062** $\pm 0.0001$). |
| **`EXP-392a`** | `EXP-392` | **`LFCG-RAW-EDGES`** | **Invocation Edge Granularity** | `EXP-391` | $W(e) = 1.0$, Max-Pool ($\lambda = 0.20$) | Isolates the structural connectivity effect of function call sites without weighting. |
| **`EXP-392b`** | *New* | **`LFCG-AMBIGUITY-ONLY`** | **Ambiguity Penalty ($\Omega$)** | `EXP-392a` | $W(e) = \frac{1}{\sqrt{A(e)}}$, $\phi = 1.0$, Max-Pool | Isolates whether candidate ambiguity dampening alone prevents multi-target dilution. |
| **`EXP-392c`** | *New* | **`LFCG-PROVENANCE-ONLY`**| **Provenance Confidence ($\phi$)** | `EXP-392a` | $W(e) = \phi(e)$, $\Omega = 1.0$, Max-Pool | Isolates whether provenance tier weighting alone prevents heuristic edge noise. |
| **`EXP-392d`** | `EXP-392b` | **`LFCG-JOINT-WEIGHTED`** | **Joint Ambiguity + Provenance** | Best of `392b`/`392c`| $W(e) = \phi(e) \cdot \frac{1}{\sqrt{A(e)}}$, Max-Pool | Tests interaction effect between ambiguity penalty and provenance tiers. |
| **`EXP-393a`** | `EXP-393a` | **`LFCG-SIDF-ONLY`** | **Symbol Frequency Dampening** | `EXP-392d` | $W(e) = W_{\text{base}}(e) \cdot \text{sIDF}_{\text{norm}}(\text{callee})$ | Isolates whether lexical symbol frequency attenuation suppresses utility hubs. |
| **`EXP-393b`** | `EXP-393b` | **`LFCG-DEGREE-ONLY`** | **Graph In-Degree Normalization** | `EXP-392d` | $W(e) = W_{\text{base}}(e) \cdot \frac{1}{\sqrt{1 + \text{in\_deg}}}$ | Isolates whether topological in-degree attenuation suppresses structural hubs. |
| **`EXP-394`** | `EXP-394` | **`LFCG-JOINT-COMPOSITE`** | **Joint Hub Dampening** | Best of `393a`/`393b`| $W(e) = W_{\text{base}}(e) \cdot \text{sIDF} \cdot \Delta_{\text{deg}}$ | Tests synergistic superiority of combined symbol and degree dampening. |
| **`EXP-395a`** | *New* | **`PROJECTION-MAX-POOL`** | **Max-Pooling Projection (Control)** | `EXP-394` | $S_{\text{file}} = S_{\text{lex}} + \lambda \max S_{\text{func}}$ | Canonical control projection baseline. |
| **`EXP-395b`** | *New* | **`PROJECTION-SUM-POOL`** | **Sum-Pooling Projection** | `EXP-395a` | $S_{\text{file}} = S_{\text{lex}} + \lambda \sum S_{\text{func}}$ | Tests whether cumulative function score mass helps or causes hub leakage. |
| **`EXP-395c`** | *New* | **`PROJECTION-SOFTMAX`** | **Softmax / Top-K Pooling** | `EXP-395a` | $S_{\text{file}} = S_{\text{lex}} + \lambda \sum_{k=1}^K w_k S_{\text{func}}^{(k)}$ | Tests whether multi-peak bounded pooling outperforms pure max-pooling. |
| **`EXP-396`** | `EXP-395` | **`LFCG-QUERY-CONDITIONED`** | **Dynamic Query Gating** | `EXP-394` | $W_{\text{qc}}(e) = W(e) \cdot \text{Overlap}(Q, e)$ | Evaluates query token dynamic conditioning on the function call graph. |

---

## 4. Binding Governance Rules for Pilot Authorization

1. **Strictly Sequential Execution**: No sub-experiment may be skipped. `EXP-392b` and `EXP-392c` must be evaluated prior to `EXP-392d`.
2. **Fixed Projection Invariant**: For all experiments prior to `EXP-395`, the projection function is frozen at Max-Pooling with $\lambda = 0.20$.
3. **Exploratory Constraint**: All subset observations on `pallets/click` and `clap-rs/clap` remain strictly exploratory.
4. **Pre-Registered Minimum Meaningful Effect**: $\Delta \text{MRR} \ge +0.0050$ under 10,000-cluster bootstrap testing.

