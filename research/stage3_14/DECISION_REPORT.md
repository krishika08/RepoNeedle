# RepoNeedle Stage 3.14 — Executive Decision Report

**Document ID**: `STAGE3-14-DECISION-001`  
**Stage**: Stage 3.14 (Language-Aware Hub Attenuation and Generalization-Safe Validation)  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `8218812`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`) — **VERIFIED UNCHANGED**  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`) — **VERIFIED UNCHANGED**  

---

## 1. Formal Decision Verdict

```
================================================================================
FINAL RESEARCH VERDICT: [NO ROBUST IMPROVEMENT]
================================================================================
```

### 1.1 Decision Rationale
1. **Zero Attenuation Variants Beat the Reference Champion**:
   - `ARM-101-BASE` (Soft Lexical Damping $\tau=0.25$, Level 1 Verified Edges, unattenuated $W_{\text{hub}}=1.0$) achieved an MRR of **$0.2078$**, Recall@20 of **$0.5648$**, and Token BCY@8k of **$0.2822$**.
   - `ARM-111-UNIFORM` produced a statistically significant degradation: MRR **$0.2061$** ($\Delta = -0.0017$, paired Wilcoxon $p = 0.00098$, Holm $p = 0.00587$).
   - `LANG-CALIBRATED` achieved MRR **$0.2073$** ($\Delta = -0.00054$, Holm $p = 1.0$), failing to demonstrate any statistically significant advantage.
   - `STRUCTURAL-ROLE` achieved MRR **$0.2078$** ($\Delta = -0.00002$, Holm $p = 1.0$, 334/345 ties), showing complete statistical equivalence with no improvement.
   - `COMBINED-LANG-ROLE` and `DEGREE-THRESHOLD-15` also failed to exceed `ARM-101-BASE` (MRR $0.2073$ and $0.2078$, both Holm $p = 1.0$).
2. **5-Fold Cross-Validation Confirms Absence of Generalization Advantage**:
   - In 5-fold repository-grouped CV across 25 independent repositories, `ARM-101-BASE` outperformed or matched all attenuation configurations in every fold.
3. **Production Source Code Preservation**:
   - In accordance with the Stage 3.14 research protocol, because the experimental configurations did not pass the pre-registered acceptance criteria, **zero lines of code in `reponeedle/` have been or will be modified**.
   - `ARM-101` remains the authoritative retrieval candidate.

---

## 2. Comprehensive System Ranking & Evidence Summary

All 9 systems evaluated over all 345 positive ARB v2 queries (218 repository snapshots) under identical full-repository candidate pools:

| System ID | Architecture Description | MRR | Recall@20 | Hit@20 | Token BCY@8k | P50 Latency (ms) | Wilcoxon vs ARM-101 (Holm p) | Decision Status |
|---|---|---|---|---|---|---|---|---|
| `BASE-REPOMAP` | Pinned official RepoMap (`9e4d689`) | **0.2293** | **0.6599** | **0.7478** | **0.3177** | 180.20 | $p = 0.280$ (NS) | External Reference Leader |
| **`ARM-101-BASE`** | **Soft Damping ($\tau=0.25$) + L1 Edges (Unattenuated)** | **0.2078** | **0.5648** | **0.6493** | **0.2822** | **12.92** | — | **CHAMPION CONFIGURATION** |
| `STRUCTURAL-ROLE` | Sink-ratio structural role attenuation | 0.2078 | 0.5648 | 0.6493 | 0.2822 | 13.64 | $p = 1.000$ | Rejected (Zero Delta) |
| `DEGREE-THRESHOLD-15` | Degree threshold ($\ge 15$) baseline | 0.2078 | 0.5648 | 0.6493 | 0.2822 | 12.68 | $p = 1.000$ | Rejected (Zero Delta) |
| `COMBINED-LANG-ROLE` | Combined language + role attenuation | 0.2073 | 0.5648 | 0.6493 | 0.2822 | 12.66 | $p = 1.000$ | Rejected (Negative Delta) |
| `LANG-CALIBRATED` | Language-calibrated schedule | 0.2073 | 0.5648 | 0.6493 | 0.2822 | 13.22 | $p = 1.000$ | Rejected (Negative Delta) |
| `ARM-111-UNIFORM` | Uniform log2 hub attenuation | 0.2061 | 0.5619 | 0.6464 | 0.2798 | 13.22 | $p = 0.00587$ (Sig Degr.) | Formally Rejected |
| `CONTROL-CASCADE` | Stage 3.10 rigid cascaded ranker | 0.1897 | 0.5605 | 0.6435 | 0.2562 | 13.11 | $p < 10^{-15}$ | Superseded Baseline |
| `BASE-BM25` | Decoupled Okapi BM25 | 0.1752 | 0.4535 | 0.5275 | 0.2114 | 10.24 | $p < 10^{-30}$ | Lexical Baseline |

---

## 3. Operational Comparison: RepoNeedle vs RepoMap

Scientific integrity requires stating facts without exaggeration:
1. **Retrieval Quality**: RepoMap achieves superior MRR ($0.2293$ vs $0.2078$) on the ARB v2 benchmark due to its global AST-based PageRank construction. RepoNeedle does not claim to outperform RepoMap on overall retrieval accuracy.
2. **Operational Throughput**: RepoNeedle provides a massive operational latency advantage:
   - RepoNeedle `ARM-101-BASE`: **$12.92\text{ ms}$ P50 query latency**.
   - RepoMap: **$180.20\text{ ms}$ P50 query latency**.
   - RepoNeedle is **$> 13.9\times$ faster**, enabling interactive, real-time code assistant completions without heavy background precomputation.
3. **Domain Strength in Go**: On Go repositories (142 queries), RepoNeedle `ARM-101-BASE` outperforms RepoMap: **$0.3125$ MRR** vs **$0.2866$ MRR**.

---

## 4. Benchmark Validity & Next Research Phase

- **ARB v2 Status**: Serves strictly as an internal development/regression testbed across 345 positive queries.
- **ContextBench Gate**: Designated **`BLOCKED / PRELIMINARY`** due to environment network sandbox restrictions.
- **Recommendation for Stage 3.15**: Proceed with official out-of-sandbox acquisition of ContextBench for true independent external validation of `ARM-101-BASE`.
