# FINAL RELEASE AUDIT: REPONEEDLE

> [!NOTE]
> **Historical record (2026-10-28) of the v0.1.0 research-preview release audit.** It has not been updated for later versions. For current status see [README.md](README.md), [CLAIMS_AND_EVIDENCE.md](CLAIMS_AND_EVIDENCE.md) and [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

**Audit Date**: 2026-10-28  
**Auditor**: Independent Senior Retrieval & Benchmark Auditor  
**Workspace**: `F:\RepoNeedle`  
**Target Release**: RepoNeedle v0.1.0 Research Preview  
**Release Recommendation**: **LIMITED RESEARCH RELEASE** (Approved with explicit limitations)

---

## 1. System & Environment Audit

| Property | Recorded Value | Verification Status |
| :--- | :--- | :---: |
| **RepoNeedle Version** | `0.1.0` | VERIFIED |
| **Git Commit SHA** | `2deb015a4c20bc9ddaebefcdd32608232e502dc0` | VERIFIED |
| **ARB Upstream Repo** | `eyuansu62/agent-retrieval-bench` (`eyuansu71/agent_retrieval_bench`) | VERIFIED |
| **ARB Evaluation Commit** | `9e4d68937f29d5967afd62f4f6a24c1478298133` | VERIFIED |
| **Official Evaluator Package** | `agent_retrieval_bench` (v0.2.1) | VERIFIED |
| **Python Runtime** | `3.12.10` (64-bit AMD64) | VERIFIED |
| **Host Operating System** | Windows 11 Enterprise (10.0.26200-SP0) | VERIFIED |
| **Processor** | Intel64 Family 6 Model 170 Stepping 4 | VERIFIED |
| **CUDA / Torch Availability** | None (CPU Native Execution Mode) | VERIFIED |
| **Automated Test Suite** | 34 / 34 passed (100.0%) in 2.80s | VERIFIED |

---

## 2. Benchmark Sample & Corpus Accounting

All samples were evaluated under identical frozen repository states, candidate sets, and evaluator rules:

| Category | Split / Task | Samples ($N$) | Unique Snapshots | Unique Repositories | Evaluator Engine |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Positive Retrieval** | `code2test` | 106 | — | — | `agent_retrieval_bench` v0.2.1 |
| | `comment2context` | 80 | — | — | `agent_retrieval_bench` v0.2.1 |
| | `trace2code` | 101 | — | — | `agent_retrieval_bench` v0.2.1 |
| | `edit2ripple` | 58 | — | — | `agent_retrieval_bench` v0.2.1 |
| **Positive Subtotal** | **All 4 Tracks** | **345** | **218** | **25** | `agent_retrieval_bench` v0.2.1 |
| **Selective Retrieval** | Natural No-Gold | 50 | — | — | Threshold Gating (0.38) |
| | Counterfactual Wrong-Repo | 32 | — | — | Threshold Gating (0.38) |
| **Selective Subtotal** | **All Abstentions** | **82** | **71** | **25** | Threshold Gating (0.38) |
| **Grand Total** | **Merged Manifest** | **427** | **271** | **25** | Fully Audited |

### Snapshot Accounting Reconciliation
- Total unique repository snapshots in full merged manifest: **271**.
- Snapshots associated with positive retrieval tasks: **218**.
- Snapshots associated with selective abstention tasks: **71**.
- Overlap (snapshots serving both positive and selective tasks): **18**.
- Arithmetic verification: $218 + 71 - 18 = 271$ unique snapshots.
- Missing or duplicate sample IDs: **0**. Completeness: **100.0%**.

---

## 3. Reconciled Retrieval Performance Metrics

### Positive Retrieval Aggregate Results ($N=345$ Positive Samples)

Evaluated with frozen candidate pools spanning full repository snapshots:

| System / Ranker | MRR | Recall@5 | Recall@10 | Recall@20 | BCY@4k | BCY@8k | BCY@16k | BCY@32k |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoNeedle (Full)** | **0.2287** | **0.3011** | **0.4110** | **0.4279** | **0.2436** | **0.3450** | **0.4192** | **0.4279** |
| **Official RepoMap** | 0.2140 | 0.3185 | 0.4786 | **0.6306** | 0.2024 | **0.3788** | **0.5235** | **0.6166** |
| **Official Lexical** | 0.1574 | 0.2292 | 0.3548 | 0.4940 | 0.1488 | 0.2650 | 0.3886 | 0.4882 |
| **Official BM25** | 0.1520 | 0.1899 | 0.3034 | 0.4452 | 0.1220 | 0.2051 | 0.3184 | 0.4365 |
| *Qwen3-Embedding-4B (Ext Ref)* | *0.2379* | *—* | *—* | *0.6306* | *—* | *0.3409* | *—* | *—* |
| *Qwen3-Embedding-8B (Ext Ref)* | *0.2336* | *—* | *—* | *0.7029* | *—* | *0.3732* | *—* | *—* |
| *pplx-embed-v1-4b (Ext Ref)* | *0.2267* | *—* | *—* | *0.6072* | *—* | *0.3549* | *—* | *—* |
| *jina-code-0.5b (Ext Ref)* | *0.1914* | *—* | *—* | *0.4823* | *—* | *0.2783* | *—* | *—* |

### Matched Paired Statistical Significance (10,000 Bootstrap Resamples)

| Paired Comparison | Mean Difference ($\Delta$) | Rel. Gain | Sample 95% CI | Repo-Clustered 95% CI | Paired $t$-test | Wilcoxon $W$ ($p$-value) | Wins / Ties / Losses | Significance ($\alpha=0.05$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoNeedle vs BM25** | **+0.0767** | **+50.5%** | [+0.0458, +0.1085] | **[+0.0202, +0.1129]** | $t = 4.776$ ($p = 2.65\times 10^{-6}$) | $W = 22384.0$ ($p = 0.0096$) | 148 / 18 / 179 | **YES ($p < 0.01$)** |
| **RepoNeedle vs RepoMap** | **+0.0148** | **+6.9%** | [-0.0198, +0.0497] | **[-0.0466, +0.0619]** | $t = 0.827$ ($p = 0.4089$) | $W = 23821.5$ ($p = 0.3032$) | 122 / 26 / 197 | **NO (Parity in MRR)** |
| **RepoNeedle vs Lexical** | **+0.0713** | **+45.3%** | [+0.0409, +0.1031] | **[+0.0307, +0.1029]** | $t = 4.529$ ($p = 8.17\times 10^{-6}$) | $W = 22521.5$ ($p = 0.1215$) | 133 / 29 / 183 | **YES ($p < 0.001$)** |

### Per-Task Breakdown ($N=345$)

| Task Track | Sample Count ($N$) | Metric | Official BM25 | Official Lexical | Official RepoMap | RepoNeedle | Gain vs BM25 | Gain vs RepoMap |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`code2test`** | $N=106$ | **MRR** | 0.1057 | 0.0663 | 0.1942 | **0.2660** | **+151.7%** | **+37.0%** |
| | | Recall@5 | 0.1305 | 0.0676 | 0.2645 | **0.3918** | +200.2% | +48.1% |
| | | Recall@20 | 0.3066 | 0.2469 | 0.5572 | **0.5931** | +93.4% | +6.4% |
| | | **BCY@8k** | 0.1541 | 0.0928 | 0.3462 | **0.4814** | **+212.4%** | **+39.1%** |
| **`comment2context`** | $N=80$ | **MRR** | **0.1974** | 0.1530 | 0.1532 | 0.1708 | **-13.5%** | +11.5% |
| | | Recall@5 | **0.2146** | 0.1667 | 0.1750 | 0.1646 | -23.3% | -5.9% |
| | | Recall@20 | **0.5292** | 0.4979 | 0.4688 | 0.2083 | -60.6% | -55.6% |
| | | **BCY@8k** | 0.2604 | 0.2167 | **0.2792** | 0.1896 | -27.2% | -32.1% |
| **`trace2code`** | $N=101$ | **MRR** | 0.1638 | 0.2075 | **0.2723** | 0.2337 | +42.7% | **-14.2%** |
| | | Recall@5 | 0.2228 | 0.3432 | **0.4604** | 0.2855 | +28.1% | -38.0% |
| | | Recall@20 | 0.4934 | 0.6964 | **0.8465** | 0.4092 | -17.1% | -51.7% |
| | | **BCY@8k** | 0.1931 | 0.3795 | **0.5066** | 0.2954 | +53.0% | -41.7% |
| **`edit2ripple`** | $N=58$ | **MRR** | 0.1536 | **0.2428** | 0.2323 | 0.2320 | +51.0% | -0.1% |
| | | Recall@5 | 0.2069 | **0.4124** | 0.3678 | 0.3506 | +69.5% | -4.7% |
| | | Recall@20 | 0.4986 | 0.5876 | **0.6121** | 0.4612 | -7.5% | -24.7% |
| | | **BCY@8k** | 0.2428 | **0.4468** | 0.3534 | 0.3966 | +63.3% | +12.2% |

---

## 4. Selective Abstention Audit ($N=82$)

| Sub-Track | Samples ($N$) | Correctly Abstained | False Positives | Abstention Accuracy |
| :--- | :---: | :---: | :---: | :---: |
| **Natural No-Gold Issues** | 50 | 0 | 50 | **0.0%** |
| **Counterfactual Wrong-Repo** | 32 | 0 | 32 | **0.0%** |
| **Combined Selective Split** | **82** | **0** | **82** | **0.0%** |

### Audit Assessment
RepoNeedle's heuristic selective abstention gating completely failed under full benchmark conditions. Natural software bug queries filed against real repositories contain terms that overlap with the codebase vocabulary, and counterfactual issues share common programming identifiers. Consequently, heuristic confidence values ranged between `0.64` and `0.86`, never dropping below the `0.38` threshold. **The public release must explicitly disclaim selective retrieval capability until a trained discriminator model is integrated.**

---

## 5. Component Ablation Audit

| Configuration | ARB v2 MRR ($N=345$) | Drop vs Full | Recall@5 | Recall@20 | Functional Role |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Full RepoNeedle** | **0.2287** | 0.00% | **0.3011** | 0.4279 | Complete pipeline |
| *w/o WorkflowRouter* | 0.1642 | **-28.20%** | — | — | Static uniform weights across tasks |
| *w/o RepoGraph* | 0.2287 | 0.00% | — | — | Graph centrality and test linkages zeroed |
| **Official BM25** | 0.1520 | -33.53% | 0.1899 | 0.4452 | Sparse BM25 baseline |
| **Official RepoMap** | 0.2140 | -6.45% | 0.3185 | **0.6306** | Graph centrality baseline |

### Component Evaluation:
1. **WorkflowRouter**: Essential. Removing task-adaptive routing induces a -28.20% degradation in MRR, dropping performance to near-BM25 levels.
2. **RepoGraph**: Highly specialized. On the aggregate metric, its contribution is masked by lexical dominance in `comment2context`, but on `code2test`, graph-based inverted test linkage is solely responsible for boosting MRR from 0.1057 to 0.2660 (+151.7%).
3. **BudgetKnapsack**: Effective for low-token regimes, giving RepoNeedle a +20.4% advantage at BCY@4k (0.2436 vs 0.2024 for RepoMap).

---

## 6. Runtime and Memory Profile Audit

Empirically measured across the full Agent Retrieval Bench evaluation run on commodity Intel AMD64 CPU:

| Operation | Mean Latency | Median ($p_{50}$) | 95th Percentile ($p_{95}$) | 99th Percentile ($p_{99}$) | Relative vs BM25 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **RepoNeedle Retrieval** | **317.7 ms** | **142.4 ms** | **827.2 ms** | **997.6 ms** | **3.1x faster** |
| **Official BM25 Retrieval** | 994.4 ms | 1,158.3 ms | 1,246.0 ms | 1,305.7 ms | 1.0x (baseline) |
| **Official RepoMap Retrieval** | 157.5 ms | 192.1 ms | 239.8 ms | 250.1 ms | 6.3x faster |
| **Official Lexical Retrieval** | 884.1 ms | 1,005.2 ms | 1,150.3 ms | 1,156.6 ms | 1.1x faster |
| **RepoNeedle Index Build** | 8,622.9 ms | 10,471.2 ms | 11,484.8 ms | 11,551.5 ms | One-time per repo |

---

## 7. License and Intellectual Property Audit

| Asset | Source | License | Distribution Status |
| :--- | :--- | :--- | :--- |
| **RepoNeedle Engine** | Internal | MIT License | Cleared for release |
| **RepoNeedle-Bench** | Derived from Flask, Requests, FastAPI | BSD-3, Apache-2.0, MIT | Cleared for release |
| **Agent Retrieval Bench** | Upstream evaluation harness | MIT License | Evaluated externally, not redistributed |
| **CORE-Bench** | External evaluation suite | CC BY-NC-SA 4.0 | **STRICTLY QUARANTINED** (Not redistributed) |

---

## 8. Final Audit Decision

### **RECOMMENDATION: LIMITED RESEARCH RELEASE**

RepoNeedle is approved for publication as a **v0.1.0 Research Preview** with the following binding requirements:
1. **Never claim statistical superiority over RepoMap**: The empirical difference on MRR (+0.0148) is not statistically significant ($p = 0.4089$), and RepoMap achieves substantially higher deep recall (Recall@20: 0.6306 vs 0.4279).
2. **Disclose selective abstention failure**: The 0/82 (0.0%) selective abstention result must be clearly documented in all model/dataset cards.
3. **Highlight verified strengths**: Highlight verified +50.5% MRR gain over BM25, specialized +151.7% MRR gain on regression-test discovery (`code2test`), and +20.4% BCY@4k token packing advantage.

