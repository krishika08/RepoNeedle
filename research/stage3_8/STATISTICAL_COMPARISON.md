# RepoNeedle Stage 3.8: Statistical Validation & Significance Analysis
**Benchmark**: Agent Retrieval Bench v2 Unconstrained (345 positive queries, 25 repositories)
**Baseline Reference**: `EXP-384` (Exact EXP-378 reproduction)
**Bootstrap Methodology**: 10,000 cluster-level bootstrap resamples over 25 repository clusters (`seed=42`)
**Hypothesis Tests**: Cluster-level paired $t$-test and Wilcoxon signed-rank test on cluster means ($K=25$, $\text{df}=24$)

## 1. Candidate Comparison Summary vs Reference EXP-384

| Candidate | Description | Metric | EXP-384 | Candidate | Mean Delta | 95% Clustered CI | p-val (t-test) | p-val (Wilcoxon) | W / T / L | Verdict |
|---|---|---|---:|---:|---:|:---:|---:|---:|:---:|:---:|
| `EXP-385` (Query-Affinity) | Query-Affinity | **MRR** | 0.2052 | 0.2040 | **-0.0012** | `[-0.0028, +0.0003]` | 0.1926 | 0.2940 | 59/243/43 | Regression / Neutral |
| `EXP-385` (Query-Affinity) | Query-Affinity | **Recall@20** | 0.5508 | 0.5566 | **+0.0058** | `[-0.0094, +0.0201]` | 0.4953 | 0.6939 | 5/335/5 | Neutral |
| `EXP-385` (Query-Affinity) | Query-Affinity | **Hit@20** | 0.6406 | 0.6464 | **+0.0058** | `[-0.0183, +0.0271]` | 0.6901 | 0.6553 | 4/339/2 | Neutral |
| `EXP-385` (Query-Affinity) | Query-Affinity | **BCY@8k** | 0.0527 | 0.0527 | **+0.0000** | `[-0.0010, +0.0011]` | 0.9585 | 0.9770 | 1/343/1 | Neutral |
| `EXP-386` (Edge-Type Gating) | Edge-Type Gating | **MRR** | 0.2052 | 0.2062 | **+0.0010** | `[-0.0017, +0.0027]` | 0.6021 | 0.2330 | 63/252/30 | Inconclusive (CI spans 0) |
| `EXP-386` (Edge-Type Gating) | Edge-Type Gating | **Recall@20** | 0.5508 | 0.5566 | **+0.0058** | `[-0.0094, +0.0201]` | 0.4953 | 0.6939 | 5/335/5 | Neutral |
| `EXP-386` (Edge-Type Gating) | Edge-Type Gating | **Hit@20** | 0.6406 | 0.6464 | **+0.0058** | `[-0.0183, +0.0271]` | 0.6901 | 0.6553 | 4/339/2 | Neutral |
| `EXP-386` (Edge-Type Gating) | Edge-Type Gating | **BCY@8k** | 0.0527 | 0.0556 | **+0.0029** | `[-0.0010, +0.0042]` | 0.4655 | 0.9770 | 2/342/1 | Neutral |
| `EXP-387` (Degree Dampened) | Degree Dampened | **MRR** | 0.2052 | 0.2036 | **-0.0016** | `[-0.0025, +0.0005]` | 0.3914 | 0.7669 | 53/262/30 | Regression / Neutral |
| `EXP-387` (Degree Dampened) | Degree Dampened | **Recall@20** | 0.5508 | 0.5566 | **+0.0058** | `[-0.0094, +0.0201]` | 0.4953 | 0.6939 | 5/335/5 | Neutral |
| `EXP-387` (Degree Dampened) | Degree Dampened | **Hit@20** | 0.6406 | 0.6464 | **+0.0058** | `[-0.0183, +0.0271]` | 0.6901 | 0.6553 | 4/339/2 | Neutral |
| `EXP-387` (Degree Dampened) | Degree Dampened | **BCY@8k** | 0.0527 | 0.0517 | **-0.0010** | `[-0.0010, +0.0000]` | 0.3273 | 0.3173 | 0/344/1 | Neutral |
| `EXP-388` (Combined QC) | Combined QC | **MRR** | 0.2052 | 0.2040 | **-0.0012** | `[-0.0025, +0.0003]` | 0.2079 | 0.5764 | 62/245/38 | Regression / Neutral |
| `EXP-388` (Combined QC) | Combined QC | **Recall@20** | 0.5508 | 0.5566 | **+0.0058** | `[-0.0094, +0.0201]` | 0.4953 | 0.6939 | 5/335/5 | Neutral |
| `EXP-388` (Combined QC) | Combined QC | **Hit@20** | 0.6406 | 0.6464 | **+0.0058** | `[-0.0183, +0.0271]` | 0.6901 | 0.6553 | 4/339/2 | Neutral |
| `EXP-388` (Combined QC) | Combined QC | **BCY@8k** | 0.0527 | 0.0517 | **-0.0010** | `[-0.0010, +0.0000]` | 0.3273 | 0.3173 | 0/344/1 | Neutral |

## 2. Preregistered Acceptance Criteria Evaluation

The Stage 3.8 protocol specifies the following strict conditions for advancing any new candidate to winner status:

1. **Valid unconstrained evaluation**: Evaluated over all 345 positive queries without oracle task filtering.
2. **MRR Improvement $\ge +0.0100$**: Absolute MRR improvement over EXP-378 must meet or exceed +0.0100.
3. **Statistical Significance**: 95% repository-clustered bootstrap CI lower bound strictly $> 0.0000$.
4. **No material Recall@20 loss**: Candidate must not regress Recall@20.
5. **No latency or memory regression**: Query latency and memory overhead must remain within acceptable bounds.

### Preregistered Gate Audit Table

| Candidate | Criterion 1 (Protocol) | Criterion 2 (Delta MRR $\ge +0.0100$) | Criterion 3 (CI Lower $> 0.0$) | Criterion 4 (No R@20 Loss) | Overall Decision |
|---|:---:|:---:|:---:|:---:|:---:|
| `EXP-385` (Query-Affinity) | PASS | FAIL (-0.0012 < +0.0100) | FAIL (CI low = -0.0028 $\le 0$) | PASS | **REJECTED (Inconclusive / Promising)** |
| `EXP-386` (Edge-Type Gating) | PASS | FAIL (+0.0010 < +0.0100) | FAIL (CI low = -0.0017 $\le 0$) | PASS | **REJECTED (Inconclusive / Promising)** |
| `EXP-387` (Degree Dampened) | PASS | FAIL (-0.0016 < +0.0100) | FAIL (CI low = -0.0025 $\le 0$) | PASS | **REJECTED (Inconclusive / Promising)** |
| `EXP-388` (Combined QC) | PASS | FAIL (-0.0012 < +0.0100) | FAIL (CI low = -0.0025 $\le 0$) | PASS | **REJECTED (Inconclusive / Promising)** |

## 3. Comparison with Candidate C and RepoMap Reference

All measurements below are on the identical 345-query unconstrained ARB v2 benchmark:

| Architecture | System Type | MRR | Recall@5 | Recall@10 | Recall@20 | Hit@20 | BCY@8k |
|---|---|---:|---:|---:|---:|---:|---:|
| **Candidate C** | Old Winner (Stage 3.5) | 0.1409 | — | — | 0.5143 | — | — |
| **EXP-384** | EXP-378 Repro Reference | 0.2052 | — | — | 0.5508 | 0.6406 | 0.0527 |
| **EXP-386** | Edge-Type Gated | 0.2062 | — | — | 0.5566 | 0.6464 | 0.0556 |
| **EXP-388** | Combined QC | 0.2040 | — | — | 0.5566 | 0.6464 | 0.0517 |
| **RepoMap** | External Reference (Aider) | 0.2293 | 0.2986 | 0.4578 | 0.6599 | 0.7478 | 0.0612 |

