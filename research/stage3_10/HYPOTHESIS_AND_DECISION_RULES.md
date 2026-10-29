# RepoNeedle Stage 3.10 — Hypothesis and Pre-Registered Decision Rules

## 1. Formal Hypotheses

### Primary Hypothesis ($H_1$)
An evidence-backed repository graph modeling production class, struct, and method invocations from test files improves repository retrieval on queries requiring cross-file test discovery (`code2test`) and trace-to-code resolution (`trace2code`), while preserving top-rank lexical precision on other query types.

Specifically:
$$\mathbb{E}[\text{MRR}_{\text{TEST-GRAPH}}] > \mathbb{E}[\text{MRR}_{\text{CONTROL-CASCADE}}]$$
$$\mathbb{E}[\text{Recall@20}_{\text{TEST-GRAPH}}] > \mathbb{E}[\text{Recall@20}_{\text{CONTROL-CASCADE}}]$$

### Null Hypothesis ($H_0$)
Static class-to-test invocation edges provide no meaningful improvement, introduce noisy false-positive edges, distort degree distributions, or degrade ranking accuracy and computational efficiency:
$$\mathbb{E}[\text{MRR}_{\text{TEST-GRAPH}}] \le \mathbb{E}[\text{MRR}_{\text{CONTROL-CASCADE}}]$$

### Connectivity Artifact Control Hypothesis ($H_{\text{conn}}$)
If improvements from Arm B are driven merely by adding arbitrary graph density or degree expansion rather than semantic invocation linkages, then a bipartite degree-matched random graph (Arm C) will match or exceed Arm B:
$$\mathbb{E}[\text{MRR}_{\text{TEST-GRAPH}}] \approx \mathbb{E}[\text{MRR}_{\text{DEGREE-CONTROL}}]$$

Conversely, if the semantic hypothesis holds, Arm B must strictly outperform Arm C:
$$\mathbb{E}[\text{MRR}_{\text{TEST-GRAPH}}] > \mathbb{E}[\text{MRR}_{\text{DEGREE-CONTROL}}]$$

## 2. Invariant Engineering Constraints

1. **Rank 1–3 Lexical Freeze**:
   The top 3 files ranked by Okapi BM25 must remain strictly untouched. Graph propagation may only re-rank positions $\ge 4$.
   *Invariant Assertion*: For every query $q$, $\text{Ranked}_{\text{arm}}[0:3] \equiv \text{Ranked}_{\text{BM25}}[0:3]$.

2. **Unconstrained Candidate Universe**:
   All files present in each repository snapshot must be eligible for retrieval. Zero task-specific candidate filtering, oracle exclusion of test files on code tasks, or diagnostic query whitelists.

3. **Deterministic Execution**:
   Arm D (`GRAPH-ABLATION`) must produce 100% bitwise identical ranked indices and metrics to Arm A (`CONTROL-CASCADE`) across all 345 queries.

4. **Resource Bounds**:
   - Query latency overhead must not exceed $+20\%$ relative to `CONTROL-CASCADE`.
   - Incremental memory footprint (Process RSS) must not exceed 2.0 GB above baseline.

## 3. Pre-Registered Decision Gates

At the conclusion of Stage 3.10, exactly one verdict must be assigned:

### Verdict: PASS
Criteria (all must be satisfied):
1. **MRR Improvement**: Mean paired MRR delta between Arm B and Arm A is strictly positive ($\Delta \text{MRR} > 0$).
2. **Statistical Significance**: Wilcoxon signed-rank test yields $p < 0.05$, and both the query-level and repository-clustered 95% bootstrap confidence intervals exclude zero on the lower bound.
3. **Recall Improvement**: Aggregate fractional Recall@20 is strictly higher on Arm B than Arm A ($\Delta \text{R@20} > 0$).
4. **Mechanism Validation**: Arm B strictly outperforms Arm C (`DEGREE-CONTROL`) on both MRR and Recall@20, confirming semantic causation.
5. **Ablation Equivalence**: Arm D matches Arm A with zero discrepancies.
6. **Zero Early-Rank Violations**: Zero regressions at Ranks 1–3.

### Verdict: NO CLEAR WIN
Triggered if:
- $\Delta \text{MRR} > 0$, but the 95% bootstrap confidence interval includes zero or $p \ge 0.05$.
- Or Arm B does not outperform Arm C (`DEGREE-CONTROL`), indicating that improvements are non-semantic connectivity artifacts.
- Or gains on `code2test` are offset by equal or larger regressions on `comment2context` or `edit2ripple`.

### Verdict: FAIL
Triggered if:
- Mean paired MRR delta is negative ($\Delta \text{MRR} < 0$).
- Or Recall@20 degrades.
- Or Rank 1–3 preservation is violated.
- Or query latency exceeds the 20% overhead bound.

### Verdict: BLOCKED
Triggered if:
- Evaluation data cannot be loaded, execution fails, or environment restrictions prevent reproducible execution.
