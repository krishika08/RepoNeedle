# RepoNeedle Stage 3.12: Preregistered Research Design Specification

**Document**: `research/stage3_12/DESIGN_AND_PREREGISTRATION.md`  
**Stage**: Stage 3.12 — Controlled Graph Retrieval Factorial Experiment  
**Date**: October 29, 2026  
**Status**: PREREGISTERED & FROZEN RESEARCH DESIGN  
**Parent Reconciliation**: Stage 3.12A (`research/stage3_12a/RECONCILIATION_DECISION.md`)  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Anchor Commit**: `809ee6a`  

---

## 1. Problem Statement and Motivation

Stage 3.11 and the Stage 3.12A canonical evaluation audit established two critical empirical realities:
1. **The Rank 1–3 Freeze Bottleneck**:
   Under the rigid Rank 1–3 freeze (`top_k_preserve=3`), `FUNCTION-GRAPH` achieved $0.1901$ MRR ($+1.00\%$ relative gain over `CONTROL-CASCADE` at $0.1882$). However, **82.0% of all queries (283 / 345) remained exact ties**. The rigid freeze capped maximum MRR gain per query at $\frac{1}{4} - \frac{1}{5} = +0.050$, preventing the ranker from promoting verified call targets to Rank 1.
2. **The Unconstrained Utility Sink Hazard**:
   Completely relaxing the freeze in `FUNCTION-GRAPH-NO-FREEZE` demonstrated the latent power of fine-grained call graphs, surging MRR to **$0.2082$** ($+10.6\%$ relative gain) with 139 wins. However, it introduced **23 regressions**, 11 of which (45.8%) were caused by high-degree utility sinks (`utils.py`, `helpers.py`, `compat.py`) absorbing excessive graph diffusion and displacing primary target files.

Stage 3.12 executes a controlled $2^3$ full factorial experiment to evaluate three orthogonal algorithmic remedies designed to capture graph retrieval gains while eliminating utility sink regressions and false positives.

---

## 2. Factor Definitions and Mathematical Formulations

The experiment evaluates three binary factors ($2^3 = 8$ configurations):

### Factor A: Soft Lexical Damping
- **Purpose**: Bridge the gap between the rigid Rank 1–3 freeze and unconstrained re-ranking by providing dynamic margin gating.
- **Level 0 (OFF)**: Rigid Rank 1–3 Freeze. Top 3 BM25 candidates are locked at ranks 1, 2, and 3, completely immutable to graph re-ranking.
- **Level 1 (ON)**: Dynamic Lexical Margin Gating.
  Let $s_1 = \text{bm25\_order}[0]$ be the Rank 1 lexical seed, and $s_2 = \text{bm25\_order}[1]$ be the Rank 2 lexical seed.
  The lexical margin is defined as:
  $$\Delta_{\text{BM25}} = \text{BM25}(s_1) - \text{BM25}(s_2)$$
  The dynamic displacement threshold is:
  $$\theta = \tau \cdot \Delta_{\text{BM25}} \quad (\text{calibrated default } \tau = 0.25)$$
  For all documents $i \in \{0, \dots, N-1\}$, the fused retrieval score is:
  $$S_{\text{fused}}(i) = 0.60 \cdot \text{BM25}(i) + 0.15 \cdot \text{Sem}(i) + 0.25 \cdot \text{Boost}(i)$$
  (scaled by $\text{penalty}_{\text{doc}} = 0.50$ for documentation files).
  Candidates are sorted by descending $S_{\text{fused}}$, with alphabetical tie-breaking on normalized file path: $R = [c_0, c_1, \dots, c_{N-1}]$.
  - If $c_0 == s_1$, $s_1$ retains Rank 1 naturally.
  - If $c_0 \ne s_1$, candidate $c_0$ displaces $s_1$ to take Rank 1 if and only if:
    $$S_{\text{fused}}(c_0) - S_{\text{fused}}(s_1) \ge \theta$$
  - If the margin condition fails ($S_{\text{fused}}(c_0) - S_{\text{fused}}(s_1) < \theta$), $s_1$ remains at Rank 1, and the remaining candidates are placed at ranks $2, 3, \dots, N$ in order of $S_{\text{fused}}$. Candidates at ranks 2 and 3 are freely re-ranked by fused score.

### Factor B: In-Degree Hub Attenuation
- **Purpose**: Suppress the 11 hub-and-spoke utility sink regressions where general-purpose helper modules accumulate excessive graph boost.
- **Level 0 (OFF)**: Standard degree normalization without fan-in penalty:
  $$\text{norm}_{\text{fwd}} = \frac{1}{\sqrt{\text{deg}_{\text{out}}(\text{seed}) \cdot \text{deg}_{\text{in}}(\text{callee})}}$$
- **Level 1 (ON)**: Inverse logarithmic in-degree attenuation applied to any incoming graph diffusion boost targeting node $v$:
  $$W_{\text{hub}}(v) = \frac{1}{\log_2(2 + \text{deg}_{\text{in}}(v))}$$
  where $\text{deg}_{\text{in}}(v)$ is the in-degree (number of unique caller files) of node $v$ in the function call graph.
  Incoming boost from seed $s$ to candidate $v$ becomes:
  $$\text{Boost}_{\text{incoming}}(v) = \text{Score}(s) \cdot W_{\text{dir}} \cdot \text{conf} \cdot \text{norm} \cdot W_{\text{hub}}(v)$$

### Factor C: Verified Call Edges Only
- **Purpose**: Eliminate structural method name ambiguity and directory-local heuristic false positives.
- **Level 0 (OFF)**: Full edge set including Level 1 verified edges and Level 2 structural method dispatch and directory-local heuristics:
  $$\mathcal{E}_{\text{allowed}} = \{\text{verified\_call}, \text{unique\_global\_call}, \text{intra\_file\_call}, \text{structural\_method\_call}, \text{directory\_local\_call}\}$$
- **Level 1 (ON)**: Level 1 verified call edges only, completely excluding Level 2 structural method dispatch and heuristics:
  $$\mathcal{E}_{\text{allowed}} = \{\text{verified\_call}, \text{unique\_global\_call}, \text{intra\_file\_call}, \text{class\_to\_test}\}$$

---

## 3. The 8 Factorial Configurations and Reference Baselines

### The $2^3 = 8$ Factorial Arms

| Arm ID | Configuration Name | Factor A (Soft Damping) | Factor B (Hub Attenuation) | Factor C (Verified Only) | Description |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **Arm 0** | `ARM-000-CONTROL` | OFF (Rigid Freeze) | OFF (Uniform) | OFF (Full Edges) | Stage 3.11 Frozen Function Graph Reference |
| **Arm 1** | `ARM-100-DAMPED` | **ON** ($\tau = 0.25$) | OFF (Uniform) | OFF (Full Edges) | Isolated Factor A effect |
| **Arm 2** | `ARM-010-HUB-ATTEN` | OFF (Rigid Freeze) | **ON** ($\log_2$ fan-in) | OFF (Full Edges) | Isolated Factor B effect |
| **Arm 3** | `ARM-001-VERIFIED` | OFF (Rigid Freeze) | OFF (Uniform) | **ON** (Verified only) | Isolated Factor C effect (`FUNCTION-GRAPH-VERIFIED`) |
| **Arm 4** | `ARM-110-DAMP-HUB` | **ON** ($\tau = 0.25$) | **ON** ($\log_2$ fan-in) | OFF (Full Edges) | Factor A + B interaction |
| **Arm 5** | `ARM-101-DAMP-VERIF` | **ON** ($\tau = 0.25$) | OFF (Uniform) | **ON** (Verified only) | Factor A + C interaction |
| **Arm 6** | `ARM-011-HUB-VERIF` | OFF (Rigid Freeze) | **ON** ($\log_2$ fan-in) | **ON** (Verified only) | Factor B + C interaction |
| **Arm 7** | `ARM-111-PROPOSED` | **ON** ($\tau = 0.25$) | **ON** ($\log_2$ fan-in) | **ON** (Verified only) | Full Factorial Integration (`STAGE-3.12-PROPOSED`) |

### Mandatory Reference Baselines

| Baseline Name | Candidate Pool | Architecture | Role |
| :--- | :---: | :--- | :--- |
| `BASE-BM25` | 100% Unconstrained | Pure Okapi BM25 with length normalization | Foundation Lexical Anchor |
| `CONTROL-CASCADE` | 100% Unconstrained | Stage 3.10 Cascaded Control (RepoGraph file imports, Rank 1–3 freeze) | Primary Control Baseline for Relative Gains |
| `FUNCTION-GRAPH` | 100% Unconstrained | Stage 3.11 Full function graph with Rank 1–3 freeze | Stage 3.11 Frozen Reference |
| `FUNCTION-GRAPH-NO-FREEZE` | 100% Unconstrained | Stage 3.11 Full function graph with no freeze | Upper-Bound Exploratory Benchmark |
| `BASE-REPOMAP` | 100% Unconstrained | Official version-pinned RepoMap (`9e4d689`) | Competitive Quality Benchmark |

---

## 4. Evaluation Protocol and Clean-Room Rules

1. **Benchmark Universe**: Exactly 345 positive ARB v2 queries across 218 repository snapshots and 4 tasks (`code2test`, `comment2context`, `trace2code`, `edit2ripple`).
2. **Candidate Universe**: 100% unconstrained for every query (zero candidate filtering, zero diagnostic shortcuts).
3. **Metric Calculations**: Clean-room implementation via [`research/stage3_10_2/independent_metrics.py`](file:///F:/RepoNeedle/research/stage3_10_2/independent_metrics.py).
4. **Deterministic Tie-Breaking**: Strict sorting by $(-S(i), \text{doc.path})$.
5. **No Production Code Alterations**: All research code resides strictly within `research/stage3_12/`. Production defaults in `reponeedle/` remain untouched.
6. **External Data Designation**: ContextBench remains designated as `BLOCKED / PRELIMINARY` due to sandbox network isolation.

---

## 5. Statistical Analysis Plan and Acceptance Gates

### Statistical Methodology
- **Paired Query Differences**: $\Delta_i = \text{Metric}_{\text{arm}, i} - \text{Metric}_{\text{control}, i}$ for all 345 queries.
- **Bootstrap Confidence Intervals**: 10,000 bootstrap iterations per comparison arm to construct 95% percentile confidence intervals.
- **Non-Parametric Hypothesis Testing**: Two-sided Wilcoxon signed-rank tests for paired differences.
- **Multiple Testing Correction**: Holm-Bonferroni step-down adjustment applied across the 7 comparison arms to control Family-Wise Error Rate (FWER $\le 0.05$).
- **Factorial Effect Estimation**: 3-factor ANOVA / OLS regression model:
  $$\Delta_{\text{MRR}} = \beta_0 + \beta_A A + \beta_B B + \beta_C C + \beta_{AB} AB + \beta_{AC} AC + \beta_{BC} BC + \beta_{ABC} ABC + \epsilon$$

### Formal Decision Criteria

To recommend **`ADVANCE`** for `ARM-111-PROPOSED`:
1. **Relative MRR Gain**: $\ge +2.0\%$ over `CONTROL-CASCADE` ($\text{MRR} \ge 0.1920$).
2. **Statistical Significance**: 95% repository-clustered bootstrap confidence interval strictly strictly above zero, Holm-adjusted $p < 0.05$.
3. **Non-Inferior Recall**: Fractional Recall@20 $\ge \text{Recall@20}_{\text{CONTROL}} - 0.0050$.
4. **Win/Loss Ratio**: Net query win-to-loss ratio $\ge 3 : 1$ over `CONTROL-CASCADE`.
5. **Runtime and Memory Feasibility**: Median query latency $< 25\text{ ms}$, process memory demonstrably sub-linear with repository size.

If these criteria are partially met (e.g. positive MRR gain with $p < 0.05$ but gain $< +2.0\%$ or win/loss ratio between $1.5:1$ and $3:1$), the verdict shall be **`PROMISING BUT INCONCLUSIVE`**.  
If the configuration exhibits null or negative gain ($\Delta \le 0$) or severe regressions (win/loss $< 1.0$), the verdict shall be **`NO ADVANCE`**.

---

## 6. Preregistration Signature and Hash

This document serves as the formal immutable preregistration for Stage 3.12. Its SHA-256 digest is computed and locked prior to executing evaluation runs.

