# RepoNeedle Stage 3.14: Statistical Test Audit & Equivalence Verification

**Stage**: Stage 3.14 — Reproducibility, Historical Errata, and Independent Validation Gate  
**Date**: October 2026  
**Status**: Authoritative Statistical Verification Audit  
**Branch**: `research-program`  
**Base Commit**: `bf7f4c8`  
**Sample Scope**: $N = 345$ Paired Queries from ARB v2  

---

## 1. Executive Summary

This statistical audit re-evaluates and formally verifies all inferential claims in the RepoNeedle research programme, focusing specifically on:
1. **Multiplicity-Controlled Paired Comparisons**: CONFIG-09 versus BASE-BM25 across all primary retrieval metrics using the Wilcoxon signed-rank test and Holm's step-down adjustment.
2. **Formal Equivalence Testing**: CONFIG-10 versus CONFIG-09 using Two One-Sided Tests (TOST) under a predeclared equivalence margin $\Delta = \pm 0.015$ MRR.

The audit confirms that:
- **CONFIG-09 is statistically superior to BASE-BM25** across MRR ($p_{\text{adj}} = 1.58 \times 10^{-27}$), Recall@20 ($p_{\text{adj}} = 6.87 \times 10^{-8}$), and Token BCY@8k ($p_{\text{adj}} = 2.11 \times 10^{-5}$) after full Holm adjustment.
- **CONFIG-10 is statistically equivalent to CONFIG-09** on MRR ($p_{\text{TOST}} = 5.12 \times 10^{-12} \ll 0.05$). The 90% and 95% confidence intervals lie strictly inside $[-\Delta, +\Delta]$. This **proves statistical equivalence** within the predeclared margin rather than merely failing to reject the null hypothesis of equality.

---

## 2. Statistical Audit 1: CONFIG-09 vs BASE-BM25 Multiplicity-Controlled Tests

### 2.1 Methodology
- **Paired Sample**: $N = 345$ queries evaluated simultaneously under CONFIG-09 and BASE-BM25.
- **Hypothesis**: Two-sided Wilcoxon signed-rank test on nonzero paired differences $d_i = y_{\text{C09}, i} - y_{\text{BM25}, i}$.
- **Familywise Error Rate Control**: Holm's step-down procedure applied to $m = 5$ metric hypotheses at target $\alpha = 0.05$:
  $$\alpha_k = \frac{\alpha}{m - k + 1}$$
- **Effect Size**: Cohen's $d = \frac{\bar{d}}{s_d}$.

### 2.2 Recomputed Statistical Results

| Metric Tested | Mean Difference ($\bar{d}$) | Cohen's $d$ | Wins ($>0$) | Ties ($=0$) | Losses ($<0$) | Unadjusted $p$-value | Holm Step Threshold ($\alpha_k$) | Holm-Adjusted $p$-value | Statistically Significant? |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **MRR** | **+0.0302** | +0.476 | 245 | 66 | 34 | $3.16 \times 10^{-28}$ | 0.0100 ($0.05/5$) | **$1.58 \times 10^{-27}$** | **YES** |
| **Recall@20** | **+0.0954** | +0.334 | 47 | 294 | 4 | $1.72 \times 10^{-08}$ | 0.0125 ($0.05/4$) | **$6.87 \times 10^{-08}$** | **YES** |
| **BCY@8k** | **+0.0609** | +0.278 | 32 | 311 | 2 | $7.05 \times 10^{-06}$ | 0.0167 ($0.05/3$) | **$2.11 \times 10^{-05}$** | **YES** |
| **Recall@5** | **+0.0522** | +0.244 | 28 | 315 | 2 | $8.31 \times 10^{-05}$ | 0.0250 ($0.05/2$) | **$1.66 \times 10^{-04}$** | **YES** |
| **Recall@10** | **+0.0532** | +0.244 | 32 | 309 | 4 | $8.74 \times 10^{-05}$ | 0.0500 ($0.05/1$) | **$8.74 \times 10^{-05}$** | **YES** |

### 2.3 Interpretation
CONFIG-09 produces 245 wins versus only 34 losses against BASE-BM25 on MRR. All 5 metrics pass Holm step-down significance thresholds by multiple orders of magnitude. The advantage of decoupled lexical-subword hybrid retrieval over pure Okapi BM25 is conclusively verified.

---

## 3. Statistical Audit 2: CONFIG-10 vs CONFIG-09 Equivalence Verification (TOST)

### 3.1 Predeclaration of the Equivalence Margin
In retrieval systems engineering, failing to reject a difference ($p > 0.05$ on a standard $t$-test) is mathematically insufficient to claim equivalence, as it may merely reflect inadequate sample size or high variance.

The equivalence margin was predeclared in Stage 3.10 and formalized in Stage 3.13 as:
$$\Delta = \pm 0.015 \text{ MRR}$$
This boundary corresponds to $\pm 7.3\%$ of hybrid MRR ($0.2061$). Any delta within $[-0.015, +0.015]$ represents operational parity for downstream context assembly where candidate ordering within top ranks is smoothed by budget-constrained packing.

### 3.2 Formal Hypothesis Construction
In TOST, the burden of proof is inverted. The null hypotheses represent **non-equivalence**, and the alternative hypotheses represent **equivalence**:

$$H_{01}: \mu_{\text{diff}} \le -\Delta \quad \text{vs.} \quad H_{11}: \mu_{\text{diff}} > -\Delta \quad (\text{Test for Lower Non-Inferiority})$$
$$H_{02}: \mu_{\text{diff}} \ge +\Delta \quad \text{vs.} \quad H_{12}: \mu_{\text{diff}} < +\Delta \quad (\text{Test for Upper Non-Superiority})$$

Where $\mu_{\text{diff}} = \mathbb{E}[y_{\text{C10}} - y_{\text{C09}}]$.

If and only if **both** null hypotheses $H_{01}$ and $H_{02}$ are rejected at significance level $\alpha = 0.05$, statistical equivalence is formally established. The overall TOST $p$-value is:
$$p_{\text{TOST}} = \max(p_1, p_2)$$

### 3.3 Empirical Audit & Exact Parameter Recomputation
Using the raw paired differences $d_i = y_{\text{C10}, i} - y_{\text{C09}, i}$ over all $N = 345$ queries:

- **Sample Size ($N$)**: $345$
- **Degrees of Freedom ($df = N - 1$)**: $344$
- **Mean Paired Difference ($\bar{d}$)**: $-0.004231$ MRR (CONFIG-10 is $0.0042$ lower than CONFIG-09)
- **Sample Standard Deviation ($s_d$)**: $0.028397$
- **Standard Error of the Mean ($SE = s_d / \sqrt{N}$)**: $0.001529$
- **Equivalence Margin ($\Delta$)**: $0.015000$

#### Lower Test ($H_{01}: \mu \le -0.015$):
$$t_1 = \frac{\bar{d} - (-\Delta)}{SE} = \frac{-0.004231 - (-0.015000)}{0.001529} = \frac{+0.010769}{0.001529} = \mathbf{+7.0440}$$
$$p_1 = 1 - F_{t, 344}(7.0440) = \mathbf{5.1165 \times 10^{-12}} \ll 0.05$$
*(Null hypothesis $H_{01}$ of meaningful inferiority is decisively rejected.)*

#### Upper Test ($H_{02}: \mu \ge +0.015$):
$$t_2 = \frac{\bar{d} - (+\Delta)}{SE} = \frac{-0.004231 - (+0.015000)}{0.001529} = \frac{-0.019231}{0.001529} = \mathbf{-12.5787}$$
$$p_2 = F_{t, 344}(-12.5787) = \mathbf{2.0617 \times 10^{-30}} \ll 0.05$$
*(Null hypothesis $H_{02}$ of meaningful superiority is decisively rejected.)*

#### Overall TOST Test Statistic:
$$p_{\text{TOST}} = \max(p_1, p_2) = \mathbf{5.12 \times 10^{-12}}$$

#### Confidence Intervals:
- **Two One-Sided Tests at $\alpha = 0.05$** corresponds to the **$90\%$ Confidence Interval ($1 - 2\alpha$)**:
  $$CI_{90\%} = \bar{d} \pm t_{0.95, 344} \times SE = -0.004231 \pm 1.6493 \times 0.001529 = \mathbf{[-0.006752, -0.001709]}$$
- **Conservative $95\%$ Confidence Interval**:
  $$CI_{95\%} = \bar{d} \pm t_{0.975, 344} \times SE = -0.004231 \pm 1.9669 \times 0.001529 = \mathbf{[-0.007238, -0.001224]}$$

### 3.4 Verification Findings
1. **Predeclared Margin Compliance**: The margin $\Delta = \pm 0.015$ was defined prior to evaluating equivalence.
2. **Bounds Containment**:
   $$[-0.015, +0.015] \supset [-0.007238, -0.001224] \supset [-0.006752, -0.001709]$$
   The entire confidence interval is completely contained within the equivalence boundary $[-\Delta, +\Delta]$.
3. **Formal Verification Statement**:
   > [!IMPORTANT]
   > The statistical test **proves equivalence** within the predeclared margin of $\Delta = \pm 0.015$ MRR ($p = 5.12 \times 10^{-12}$). This is not a "failure to detect a difference"; it is positive empirical proof that the performance difference between CONFIG-10 and CONFIG-09 is bounded within tight, operationally negligible limits.
