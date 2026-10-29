# RepoNeedle Stage 3.14 — Pre-Registered Hypotheses and Theoretical Framework

**Stage**: Stage 3.14 (Language-Aware Hub Attenuation and Generalization-Safe Validation)  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `8218812`  
**Anchor Reference**: `ARM-101-BASE` (Soft Lexical Damping $\tau=0.25$, Level 1 Verified Call Edges, unattenuated $W_{\text{hub}}=1.0$)

---

## 1. Problem Statement & Theoretical Motivation

In Stage 3.12, the factorial evaluation revealed that while graph connectivity (verified function call edges) boosts retrieval over lexical baselines (`ARM-101` MRR $0.2078$ vs `BASE-BM25` $0.1752$), uniform in-degree hub attenuation (`ARM-111-UNIFORM`) caused a measurable score degradation from $0.2078$ down to $0.2061$.

The Stage 3.14 investigation examines whether this degradation was caused by:
1. **Language Structural Heterogeneity**: Different programming languages exhibit distinct graph topology. In Go and Rust, package-level encapsulation produces flat, high-fan-in symbols (such as core context structs, interface dispatchers, and handler definitions) that are genuine retrieval targets. In contrast, in Python, high-fan-in symbols frequently correspond to generic utility modules (`helpers.py`, `utils.py`, `typing`) that act as false-positive attractors.
2. **Coarse In-Degree Metric**: Simple in-degree treats architectural hub interfaces (which both receive many calls and make many outgoing calls) identically to terminal utility sinks (which receive many calls but call nothing).
3. **Lexical Pre-Filtering Redundancy**: Soft lexical damping ($\tau = 0.25$) already dampens candidate elevation based on the gap between top lexical candidates:
   $$\text{Threshold} = \tau \cdot (\text{BM25}_1 - \text{BM25}_2)$$
   If an in-degree hub has poor lexical relevance, soft damping already prevents it from overtaking the lexical seed, rendering explicit hub attenuation redundant or counterproductive.

---

## 2. Pre-Registered Hypotheses

### Hypothesis 1 (Null / Reference Baseline: ARM-101-BASE)
- **Definition**: Soft lexical damping $\tau=0.25$, Level 1 verified call graph edges, unattenuated hub weighting ($W_{\text{hub}} = 1.0$).
- **Prediction**: Maintains established reference MRR $0.2078$, Recall@20 $0.5648$, Token BCY@8k $0.2822$.
- **Role**: Anchor against which all attenuation variants must demonstrate statistically superior performance.

### Hypothesis 2 (Uniform Logarithmic Attenuation: ARM-111-UNIFORM)
- **Definition**: Uniform logarithmic attenuation applied across all symbols regardless of language or structural role:
  $$W_{\text{hub}}(v) = \frac{1}{\log_2(2 + \text{deg}_{\text{in}}(v))}$$
- **Prediction**: Replicates the negative drag observed in Stage 3.12 ($\approx -0.0017$ MRR), driven by suppression of valid shared utilities in Go and Rust.

### Hypothesis 3 (Language-Calibrated Attenuation: LANG-CALIBRATED)
- **Definition**: Language-specific attenuation schedules based on language architectural topology:
  - **Go**: Unattenuated ($W_{\text{hub}} = 1.0$), recognizing that Go package exports have high fan-in with high target relevance.
  - **Python**: Full log2 attenuation ($W_{\text{hub}} = 1 / \log_2(2 + \text{deg}_{\text{in}})$), penalizing ubiquitous helper sinks.
  - **Rust**: Mild attenuation ($W_{\text{hub}} = 1 / \sqrt{1 + 0.2 \cdot \text{deg}_{\text{in}}}$), balancing trait implementations with dispatch utilities.
  - **TypeScript / Java**: Mild attenuation ($W_{\text{hub}} = 1 / \sqrt{1 + 0.2 \cdot \text{deg}_{\text{in}}}$).
- **Prediction**: Recovers Go retrieval performance ($0.3125$ MRR) while improving Python retrieval over `ARM-101-BASE` ($> 0.1515$ MRR), yielding an overall MRR $> 0.2085$.

### Hypothesis 4 (Structural Sink-Ratio Attenuation: STRUCTURAL-ROLE)
- **Definition**: Graph-structural role classification independent of language naming heuristics:
  - Compute Sink Ratio:
    $$\rho(v) = \frac{\text{deg}_{\text{in}}(v)}{\max(1, \text{deg}_{\text{in}}(v) + \text{deg}_{\text{out}}(v))}$$
  - True architectural hubs ($\text{deg}_{\text{in}} \ge 5$ AND $\text{deg}_{\text{out}} \ge 3$, $\rho < 0.8$) remain unattenuated ($W_{\text{hub}} = 1.0$).
  - Pure sinks ($\rho \ge 0.8$ or path matching `*/util*`, `*/common*`, `*/helper*`) receive logarithmic attenuation:
    $$W_{\text{hub}}(v) = \frac{1}{\log_2(2 + \text{deg}_{\text{in}}(v))}$$
- **Prediction**: Protects core architectural classes from penalty while suppressing trivial leaf helpers, improving precision on complex multi-hop queries.

### Hypothesis 5 (Combined Language + Role-Based Attenuation: COMBINED-LANG-ROLE)
- **Definition**: Evaluates the intersection of language-calibrated damping and structural sink-ratio classification.
- **Prediction**: Synergistic benefit on polyglot repositories where structural role and language conventions align.

### Hypothesis 6 (Degree Threshold Baseline: DEGREE-THRESHOLD-15)
- **Definition**: Hard threshold attenuation: $W_{\text{hub}} = 1.0$ for $\text{deg}_{\text{in}} < 15$; $W_{\text{hub}} = 1 / \log_2(2 + \text{deg}_{\text{in}} - 14)$ for $\text{deg}_{\text{in}} \ge 15$.
- **Prediction**: Prevents penalizing moderately connected utilities (degrees 2–14) while clipping extreme outlier hubs.

---

## 3. Pre-Registered Acceptance Criteria for Production Adoption

In accordance with Stage 3.14 governance, an experimental variant is accepted for production integration into `reponeedle/` **if and only if** all of the following conditions are met:

1. **Statistical Significance over ARM-101-BASE**:
   - Paired Wilcoxon signed-rank test achieves $p < 0.05$ after familywise error rate adjustment (Holm-Bonferroni across all candidate comparisons).
2. **Confidence Interval Lower Bound**:
   - 95% bootstrap confidence interval (10,000 resamples) on $\Delta \text{MRR}$ must strictly exclude zero ($\text{CI}_{95, \text{lower}} > 0.0$).
3. **Repository Cross-Validation Generalization**:
   - 5-fold repository-grouped cross-validation (GroupKFold over 25 repositories) must demonstrate consistent non-negative $\Delta \text{MRR}$ across at least 4 of 5 folds.
4. **No Regression on Secondary Metrics**:
   - Recall@20 must not decrease by more than $0.002$.
   - Token BCY@8k must not decrease.
5. **Efficiency & Operational Constraints**:
   - Query P50 latency increase must not exceed 10% relative to `ARM-101-BASE` ($< 14.2\text{ ms}$).
   - Peak process RSS must remain within established baselines.
6. **No Special-Casing**:
   - Zero repo-specific or query-specific manual overrides. All rules must be purely algorithmic.

If any criterion is not met, the official outcome is **`NO ROBUST IMPROVEMENT`**, and `ARM-101` remains the frozen research champion.
