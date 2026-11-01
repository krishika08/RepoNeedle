# Stage 3.9.1: Failure Modes, Calibration Protocols & Hub Dampening
## Heuristic Calibration, Manually Annotated Validation Set & Mathematical Hub Formulations

**Document ID**: `STAGE3-9-FAILURES-002`  
**Stage**: Stage 3.9.1 — Architecture Design Refinement and Research Governance  
**Date**: November 1, 2026  
**Workspace**: `F:\RepoNeedle`  
**Active Branch**: `research/stage3_8`  
**Development Baseline Reference**: `EXP-386` (Edge-Type-Aware Directional Gating: MRR **0.2062**, Recall@20 **0.5566**, Hit@20 **0.6464**, BCY@8k **0.0556**)  
**Governing Rule**: Treat proposed provenance values as initial heuristic weights, not true Bayesian probabilities. Do not add arbitrary multipliers without an ablation plan. Empirically measure resolution precision against a manually labeled edge validation set.

---

## 1. Provenance Scores as Initial Heuristics vs. Calibrated Probabilities

In initial drafts, provenance confidence scores ($\phi \in [0.30, 1.00]$) were proposed as intuitive weights. In accordance with Stage 3.9.1 governance:
- **Heuristic Nature**: The initial $\phi$ values represent heuristic ranking prior weights, **not empirical probabilities** ($P(\text{ValidEdge} \mid \text{Heuristic})$).
- **Calibration Requirement**: Before these weights can be treated as calibrated probabilities, their true positive predictive values (precision) must be measured against an annotated ground-truth edge validation set.

---

## 2. Design of the Manually Labeled Edge Validation Dataset

To establish empirical validity, an annotated benchmark dataset of $N = 250$ sampled candidate invocation edges will be constructed across the 25 repositories:

### 2.1 Sampling & Stratification Protocol
The sample is stratified across the 5 primary programming language ecosystems ($50$ edges per ecosystem):

| Language Ecosystem | Sampled Repositories | Target Edge Count | Sampled Resolution Methods |
|---|---|:---:|---|
| **Python** | `pallets/click`, `transformers` | 50 | 20 `AST_EXACT_QUALIFIED`, 15 `AST_IMPORT_BOUND`, 10 `AST_LOCAL_CALL`, 5 `STRUCTURAL_METHOD` |
| **Go** | `gin-gonic/gin`, `etcd-io/etcd` | 50 | 20 Package-local, 15 `func (c *Context)` receiver calls, 15 exported `pkg.Func()` |
| **Rust** | `clap-rs/clap`, `tokio-rs/tokio` | 50 | 20 `Type::method()`, 15 `impl Struct` calls, 15 `use crate::*` calls |
| **TypeScript / JS**| `playwright`, `eslint` | 50 | 20 Named export calls, 15 class method calls, 15 relative import calls |
| **Java** | `mockito`, `spring-boot` | 50 | 20 Class method calls, 15 package calls, 15 overloaded calls |

### 2.2 Annotation Criteria
Every sampled edge $e = (u, v)$ is manually inspected by an engineer and labeled:
- **`VALID_CALL` ($1.0$)**: Function $u$ genuinely invokes function $v$ during normal execution.
- **`FALSE_POSITIVE` ($0.0$)**: Function $u$ does not invoke $v$ (e.g. matching an unrelated method of the same name, or regex matching an identifier inside a comment/string).

### 2.3 Empirical Precision Measurement
For each resolution tier $T$, empirical precision is computed as:
$$\text{Precision}(T) = \frac{\sum_{e \in T} \mathbb{I}(\text{Label}(e) = \text{VALID\_CALL})}{|T|}$$
These measured precisions will be compared against the initial heuristic $\phi$ values. If a heuristic deviates from empirical precision by $> 0.15$, the weight is recalibrated to match the observed precision.

---

## 3. Mathematical Hub-Attenuation Formulations & Ablation Plan

In graph-based retrieval, highly connected nodes dump score mass into irrelevant neighborhoods. Stage 3.9 compares five distinct mathematical formulations for symbol hub attenuation:

### 3.1 Five Competing Hub Formulas

1. **Formula 1: No Hub Penalty (Unconstrained Control)**:
   $$\psi_{\text{none}}(v) = 1.0$$
   *Behavior*: Raw unpenalized diffusion. High-degree symbols receive and transmit full score mass.
2. **Formula 2: Standard Inverse Document Frequency (sIDF)**:
   $$\text{sIDF}(s) = \log\left(1.0 + \frac{N_{\text{files}}}{|\{f \in \text{Files} \mid s \in \text{Symbols}(f)\}|}\right)$$
   $$\psi_{\text{sIDF}}(s) = \frac{\text{sIDF}(s)}{\max_{s'} \text{sIDF}(s')}$$
   *Behavior*: Linearly scales diffusion by document specificity. Symbols appearing in many files are penalized.
3. **Formula 3: Capped sIDF (Thresholded Specificity)**:
   $$\psi_{\text{capped}}(s) = \min\left(1.0, \frac{\text{sIDF}(s)}{\text{sIDF}_{\text{median}}}\right)$$
   *Behavior*: Specific symbols (above median sIDF) retain full 1.0 weight; generic utility symbols (below median sIDF) are smoothly attenuated.
4. **Formula 4: In-Degree Normalization ($1 / \sqrt{\text{deg}}$)**:
   $$\psi_{\text{deg}}(v) = \frac{1}{\sqrt{\max(1, \text{deg}_{\text{in}}(v))}}$$
   *Behavior*: Proven in Stage 3.7 (`EXP-377`). Normalizes score diffusion by the topological connectivity of the target node, preventing in-degree explosion.
5. **Formula 5: Combined Multiplicative Penalty (Composite)**:
   $$\psi_{\text{comb}}(v) = \psi_{\text{capped}}(v) \cdot \psi_{\text{deg}}(v) \cdot \frac{1}{\sqrt{A(e)}}$$
   *Behavior*: Simultaneously dampens lexical ubiquity (sIDF), topological connectivity (in-degree), and target ambiguity ($A(e)$).

### 3.2 Controlled Ablation Protocol
To prevent ad-hoc multiplier selection, `EXP-394` will execute a controlled parameter sweep comparing all 5 formulations across the canonical 345 queries:

| Formula Candidate | Notation | Hypothesis | Expected Failure if Omitted |
|---|---|---|---|
| Formula 1 | `No Penalty` | Graph connectivity is purely informative. | Catastrophic hub collapse on `transformers` and `click`. |
| Formula 2 | `Standard sIDF` | Lexical document count alone controls dilution. | Insufficient control over intra-file recursion hubs. |
| Formula 3 | `Capped sIDF` | Non-linear thresholding preserves specific functions. | Balances specificity without penalizing modular code. |
| Formula 4 | `Degree Normalization` | Topological in-degree is the primary dilution driver. | Proven file-level mitigation transferred to symbol level. |
| Formula 5 | `Combined Multiplicative`| Compound interactions between degree and sIDF provide optimal selectivity. | Best overall balance across large multi-crate repos. |

---

## 4. Deconstruction of Critical Topological Hazards

### 4.1 Test Caller Inversion in Trace2Code Queries
In `trace2code` queries (e.g. `pallets/click`), error tracebacks cite line numbers and files where tests failed.
- **Topological Hazard**: Test files import `core.py`. Backward diffusion from `core.py` flows along invocation edges back into test callers.
- **Controlled Invariant**: As established in `EXP-386`, test-to-code edges are strictly attenuated by **0.15x** for code-seeking queries, and test callers cannot leapfrog their seed files ($\Delta S_{\text{caller}} \le \max(0, S_{\text{seed}} - S_{\text{caller}})$).

### 4.2 Cross-Crate Hub Leakage in Multi-Crate Workspaces
In `clap-rs/clap`, utility crates (`clap_builder/src/util/`) export common formatting and string helpers.
- **Topological Hazard**: Generic utility functions (`sanitize_identifier`, `color_print`) are called by every subcrate, routing diffusion energy across crate boundaries into irrelevant CLI plugins.
- **Controlled Invariant**: Generic helper functions with $\text{sIDF} < \text{sIDF}_{15\%}$ receive a hard 0.10x multiplier, terminating cross-crate leakage.
