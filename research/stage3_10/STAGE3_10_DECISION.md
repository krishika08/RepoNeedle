# RepoNeedle Stage 3.10 — Decision Gate Report

## 1. Official Stage Verdict

**VERDICT: PASS**

The pre-registered empirical evidence supports the adoption of the class-to-test invocation graph enhancement. The feature achieves statistically significant, reproducible improvements on both MRR and Recall@20 across the canonical 345 positive ARB v2 queries, without introducing regressions at early ranks, incurring latency overhead, or altering memory constraints.

---

## 2. Gate Evaluation Matrix

| Decision Criterion | Pre-Registered Standard | Empirical Result | Status |
|---|---|---|:---:|
| **1. MRR Improvement** | $\Delta \text{MRR} > 0$ | $+0.0015$ ($0.1883 \to 0.1898$) | **MET** |
| **2. Statistical Significance** | $p < 0.05$ (Wilcoxon), 95% Bootstrap CI excludes 0 | $p = 1.009 \times 10^{-3}$, CI $[+0.0005, +0.0027]$, Clustered CI $[+0.0001, +0.0028]$ | **MET** |
| **3. Fractional Recall@20** | $\Delta \text{Recall@20} > 0$ | $+0.0087$ ($0.5518 \to 0.5605$) | **MET** |
| **4. Binary Hit@20** | $\Delta \text{Hit@20} > 0$ | $+0.0087$ ($0.6348 \to 0.6435$) | **MET** |
| **5. Semantic Mechanism Control** | Arm B strictly outperforms Arm C | $\text{MRR}: 0.1898 > 0.1885$, $\text{R@20}: 0.5605 > 0.5474$ | **MET** |
| **6. Graph Ablation Invariant** | Arm D bitwise identical to Arm A | Identical on 345/345 queries ($0$ diffs) | **MET** |
| **7. Rank 1–3 BM25 Freeze** | Zero early-rank modifications | 0 violations across 1,035 rank positions | **MET** |
| **8. Query Latency Overhead** | Overhead $\le +20\%$ | p50 latency $8.30$ ms vs $8.33$ ms ($-0.3\%$) | **MET** |
| **9. Process RSS Footprint** | Process RSS $\le 2.0$ GB delta | Final RSS $937.9$ MB | **MET** |

---

## 3. Honest Scientific Appraisal & Comparison to Baselines

While Stage 3.10 delivers a validated, statistically sound advancement over the Stage 3.9 cascaded control, scientific rigor requires explicitly placing RepoNeedle in context with the competing baselines:

```
                  MRR     Recall@20   Hit@20    Median Latency
BASE-BM25        0.1752    0.4535     0.5275        5.54 ms
CONTROL-CASCADE  0.1883    0.5518     0.6348        8.33 ms
TEST-GRAPH       0.1898    0.5605     0.6435        8.30 ms   <-- RepoNeedle Stage 3.10
BASE-REPOMAP     0.2293    0.6599     0.7478      180.20 ms
```

### Key Scientific Findings
1. **RepoNeedle does NOT outperform RepoMap overall**:
   - `BASE-REPOMAP` achieves $0.2293$ MRR and $0.6599$ Recall@20. RepoNeedle `TEST-GRAPH` achieves $0.1898$ MRR and $0.5605$ Recall@20.
   - Any claim that RepoNeedle currently exceeds RepoMap on Agent Retrieval Bench v2 is scientifically false and contradicted by the canonical data.
   - RepoMap gains its advantage through an extensive global ctags/tree-sitter call graph coupled with iterative PageRank over the full repository structure.
2. **Efficiency & Latency Advantage**:
   - RepoNeedle `TEST-GRAPH` runs in **8.30 ms** at median latency, compared to **180.20 ms** for RepoMap ($21.7\times$ faster).
   - RepoNeedle is designed for interactive real-time agent loops where sub-10ms response times are critical.
3. **Causal Mechanism Confirmed**:
   - The degree-matched control (Arm C) proved that random connectivity harms Recall@20 ($0.5474 < 0.5518$). Only evidence-backed static invocation links elevate Recall@20 to $0.5605$.

---

## 4. Next Stage Recommendations (Stage 3.11)

With the class-to-test invocation feature validated and merged into the canonical pipeline:
1. **Preserve Frozen Baselines**:
   - `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`)
   - `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`)
2. **Explore Call-Graph Densification**:
   - The primary gap between RepoNeedle ($0.1898$) and RepoMap ($0.2293$) is function-level call graph resolution in production code (outside tests). Extending high-precision static resolution to inter-module function calls should be the primary research focus of Stage 3.11.
3. **ContextBench Evaluation Gate**:
   - ARB v2 is a development and regression corpus. Independent generalization to ContextBench remains the unfulfilled requirement before any public release claims can be made.
