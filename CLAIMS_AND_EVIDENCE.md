# CLAIMS AND EVIDENCE: SCIENTIFIC RECONCILIATION FOR REPONEEDLE

**Version**: Evidence originally compiled for the 0.1.0 Research Preview. Claims C11–C13 and corrections to C2, C4 and C6 were added on 2026-11-09 and cover released 1.1.0 and the pre-release development branch that became 1.2.0 (upcoming; PyPI publication pending).  
**Benchmark Suite**: Official Agent Retrieval Bench (ARB v2, $N=427$ total samples, $N=345$ positive retrieval samples across 25 repositories and 271 unique repository snapshots)  
**Evaluator**: `agent_retrieval_bench` v0.2.1, Commit `9e4d68937f29`  
**Evaluation Date**: 2026-10-28  

This document provides a line-by-line verification of all scientific, empirical, and architectural claims made regarding the **RepoNeedle** repository retrieval system.

---

## 1. Summary of Claim Statuses

| # | Claim Description | Status | Empirical Verdict |
| :-: | :--- | :---: | :--- |
| **C1** | RepoNeedle significantly outperforms BM25 on positive retrieval MRR on ARB v2 | **SUPPORTED** | Statistically significant ($+50.5\%$ relative gain, $p = 2.65\times 10^{-6}$) |
| **C2** | RepoNeedle significantly outperforms Lexical baseline on positive retrieval MRR | **SUPPORTED (mean MRR; see caveat)** | Paired $t$-test significant ($+45.3\%$ relative gain, $p = 8.17\times 10^{-6}$), but Wilcoxon signed-rank is not ($p = 0.1215$) and RepoNeedle wins fewer queries than it loses (133 / 29 / 183) |
| **C3** | RepoNeedle outperforms RepoMap overall on ARB v2 | **REFUTED / NOT SUPPORTED** | Parity on MRR ($p = 0.4089$); RepoMap dominates deep recall (R@20 $+47.4\%$) |
| **C4** | RepoNeedle is superior for regression test discovery (`code2test`) | **SUPPORTED** | Strongest track ($+151.7\%$ vs BM25, $+37.0\%$ vs RepoMap on MRR) |
| **C5** | RepoNeedle outperforms classical baselines on issue comments (`comment2context`) | **REFUTED / NOT SUPPORTED** | BM25 achieves higher MRR ($0.1974$ vs $0.1708$, $-13.5\%$ deficit for RepoNeedle) |
| **C6** | Heuristic selective abstention reliably identifies no-gold tasks on ARB v2 | **REFUTED / NOT SUPPORTED** | Total failure ($0/82$ abstained, $0.0\%$ accuracy on full benchmark) |
| **C7** | Task-adaptive routing (`WorkflowRouter`) is essential to system performance | **SUPPORTED** | Removing router causes $-28.20\%$ collapse in aggregate MRR |
| **C8** | Budget knapsack packing maximizes context yield under strict token limits | **SUPPORTED** | $+20.4\%$ advantage over RepoMap at BCY@4k ($0.2436$ vs $0.2024$) |
| **C9** | Structural skeletons reduce token payload without sacrificing signatures | **SUPPORTED** | $52.8\%$ to $90.4\%$ measured BPE token compression across 4 languages |
| **C10**| System is lightweight and runs purely on commodity CPU without GPUs | **SUPPORTED** | $317.7\text{ ms}$ mean query latency; zero PyTorch or CUDA dependencies |
| **C11**| "100% selective abstention accuracy" (v0.1.0 announcement) | **RETRACTED** | Based on 3 synthetic samples from a stale result file; current code scores 2/3 on that set and 0/82 on ARB v2 |
| **C12**| "100% test coverage across core modules" (v0.1.0 roadmap) | **REFUTED** | Measured line coverage of the `reponeedle` package: 87% (2026-11-09) |
| **C13**| The MCP server works with Claude Code / Cursor | **NOT VERIFIED (protocol level only)** | Verified with the MCP Python SDK and a JSON-RPC STDIO handshake; no live client session recorded |

### Re-check on the Current Engine (2026-11-09)

The ARB-derived evidence for C1–C8 and C10 was measured on 2026-10-28 with the engine at commit `8e00425` (tag `v0.1.0-baseline`). Engine changes made before the 1.1.0 release altered the rankings, so the ARB v2 positive split was re-measured with the current engine (1.1.0, and the pre-release 1.2.0 development branch of 2026-11-09, which produced identical rankings). Method and full tables: [docs/BENCHMARK_CONFIGURATION.md §7](docs/BENCHMARK_CONFIGURATION.md#7-verification-performed-2026-11-09).

| # | Status on the current engine | Current evidence |
| :-: | :---: | :--- |
| C1 | **SUPPORTED** | MRR 0.2153 vs BM25 0.1520 (+41.6%); repository-clustered 95% CI of the difference [+0.0111, +0.0980] |
| C2 | **SUPPORTED (mean MRR; same caveat)** | +36.8% vs Lexical, clustered CI [+0.0180, +0.0933]; wins / ties / losses 118 / 24 / 203 |
| C3 | **REFUTED / NOT SUPPORTED** | Parity on MRR (+0.0013, clustered CI [−0.0597, +0.0517]); RepoMap Recall@20 0.6306 vs 0.3842 |
| C4 | **SUPPORTED** | `code2test` MRR 0.2546 vs BM25 0.1057 (+140.8%) and RepoMap 0.1942 (+31.0%) |
| C5 | **REFUTED / NOT SUPPORTED** | `comment2context` MRR 0.1658 vs BM25 0.1974 (−16.0%) |
| C6 | **REFUTED / NOT SUPPORTED** | 0/82 abstained with explicit opt-in (unchanged) |
| C7 | **NOT RE-MEASURED** | Router ablation was not re-run on the current engine |
| C8 | **SUPPORTED (no CI)** | BCY@4k 0.2400 vs RepoMap 0.2024 (+18.5%); no confidence interval computed for BCY |
| C10 | **SUPPORTED (latency not comparable)** | CPU-only dependencies unchanged; re-measurement latency was taken with three concurrent shards and is not comparable to the published figures |

---

## 2. Detailed Evidence & Arithmetic Verification

### Claim 1: "RepoNeedle significantly outperforms BM25 on positive retrieval MRR on ARB v2"
- **Status**: **SUPPORTED**
- **Evidence**:
  - Full ARB v2 Positive Retrieval Evaluation ($N=345$ samples across 25 repositories).
  - RepoNeedle MRR: `0.2287`
  - Official BM25 MRR: `0.1520`
  - Absolute Difference: $\Delta = 0.2287 - 0.1520 = +0.0767$
  - Relative Gain: $\frac{0.2287 - 0.1520}{0.1520} \times 100\% = +50.46\% \approx \mathbf{+50.5\%}$
  - Standard Error: `0.0161`
  - Sample-Level 95% Bootstrap CI: `[+0.0458, +0.1085]`
  - Repository-Clustered 95% Bootstrap CI: `[+0.0202, +0.1129]` (strictly positive lower bound)
  - Paired Student's $t$-test: $t = 4.776$, $p = 2.65 \times 10^{-6}$ ($p < 0.001$)
  - Paired Wilcoxon Signed-Rank Test: $W = 22384.0$, $p = 0.0096$ ($p < 0.01$)
  - Head-to-Head Win/Tie/Loss Record: 148 wins / 18 ties / 179 losses

### Claim 2: "RepoNeedle significantly outperforms Lexical baseline on positive retrieval MRR"
- **Status**: **SUPPORTED**
- **Evidence**:
  - RepoNeedle MRR: `0.2287`
  - Official Lexical MRR: `0.1574`
  - Absolute Difference: $\Delta = 0.2287 - 0.1574 = +0.0713$
  - Relative Gain: $\frac{0.2287 - 0.1574}{0.1574} \times 100\% = +45.30\% \approx \mathbf{+45.3\%}$
  - Standard Error: `0.0157`
  - Repository-Clustered 95% Bootstrap CI: `[+0.0307, +0.1029]`
  - Paired Student's $t$-test: $t = 4.529$, $p = 8.17 \times 10^{-6}$ ($p < 0.001$)
  - *Caveat (added 2026-11-09)*: the Wilcoxon signed-rank test is **not** significant ($W = 22521.5$, $p = 0.1215$), and per-query wins / ties / losses are 133 / 29 / 183. The mean gain comes from fewer, larger wins rather than consistent per-query improvement. The README's significance column reflects the $t$-test and repository-clustered bootstrap.

### Claim 3: "RepoNeedle outperforms RepoMap overall on ARB v2"
- **Status**: **REFUTED / NOT SUPPORTED**
- **Evidence**:
  - RepoNeedle MRR: `0.2287`
  - Official RepoMap MRR: `0.2140`
  - Absolute Difference: $\Delta = 0.2287 - 0.2140 = +0.0148$
  - Relative Difference: $\frac{0.2287 - 0.2140}{0.2140} \times 100\% = +6.87\% \approx +6.9\%$
  - Standard Error: `0.0179`
  - Sample-Level 95% Bootstrap CI: `[-0.0198, +0.0497]`
  - Repository-Clustered 95% Bootstrap CI: `[-0.0466, +0.0619]` (**includes zero**)
  - Paired Student's $t$-test: $t = 0.827$, $p = 0.4089$ (**not significant**)
  - Paired Wilcoxon Signed-Rank Test: $W = 23821.5$, $p = 0.3032$ (**not significant**)
  - Head-to-Head Win/Tie/Loss Record: 122 wins / 26 ties / 197 losses
  - **Deep Recall Deficit**:
    - RepoNeedle Recall@20: `0.4279`
    - RepoMap Recall@20: `0.6306`
    - RepoMap Advantage: $\frac{0.6306 - 0.4279}{0.4279} \times 100\% = \mathbf{+47.37\%}$ (RepoMap substantially leads)
  - **BCY@8k Deficit**:
    - RepoNeedle BCY@8k: `0.3450`
    - RepoMap BCY@8k: `0.3788`
    - RepoMap Advantage: $\frac{0.3788 - 0.3450}{0.3450} \times 100\% = \mathbf{+9.80\%}$
  - **Scientific Conclusion**: RepoNeedle and RepoMap exhibit statistical parity in MRR ($p = 0.41$). RepoMap provides vastly superior recall depth at $k=20$, while RepoNeedle provides higher context yield only under narrow token budgets (BCY@4k: `0.2436` vs `0.2024`, $+20.4\%$). Any public claim of overall superiority over RepoMap is factually false and disallowed.

### Claim 4: "RepoNeedle is superior for regression test discovery (`code2test`)"
- **Status**: **SUPPORTED**
- **Evidence**:
  - Sample size: $N=106$ positive samples in `code2test` track.
  - RepoNeedle MRR: `0.2660`
  - Official BM25 MRR: `0.1057` ($\Delta = +0.1603$, $\mathbf{+151.7\%}$ relative gain)
  - Official Lexical MRR: `0.0663` ($\Delta = +0.1997$, $\mathbf{+301.2\%}$ relative gain)
  - Official RepoMap MRR: `0.1942` ($\Delta = +0.0718$, $\mathbf{+37.0\%}$ relative gain)
  - Budgeted Yield at 8k Tokens (BCY@8k):
    - RepoNeedle: `0.4814`
    - RepoMap: `0.3462` ($\mathbf{+39.1\%}$ gain for RepoNeedle)
    - BM25: `0.1541` ($\mathbf{+212.4\%}$ gain for RepoNeedle)
  - Mechanism: Graph-based test linkage inverts the dependency graph and pairs test files with implementation targets via naming stem heuristics, directly resolving the disconnected leaf node problem.

### Claim 5: "RepoNeedle outperforms classical baselines on issue comments (`comment2context`)"
- **Status**: **REFUTED / NOT SUPPORTED**
- **Evidence**:
  - Sample size: $N=80$ positive samples in `comment2context` track.
  - Official BM25 MRR: `0.1974`
  - RepoNeedle MRR: `0.1708`
  - Deficit vs BM25: $\frac{0.1708 - 0.1974}{0.1974} \times 100\% = \mathbf{-13.48\%}$
  - Recall@20 Deficit: BM25 `0.5292` vs RepoNeedle `0.2083` ($-60.6\%$ deficit)
  - BCY@8k Deficit: BM25 `0.2604` vs RepoNeedle `0.1896` ($-27.2\%$ deficit)
  - Root Cause *(corrected 2026-11-10; the earlier explanation attributed the deficit to "colloquial issue text" and router weight dilution, which the later evidence does not support)*: the queries are structured JSON PR-review contexts, not colloquial issue text. Much of the official-harness gap is a measurement artifact: RepoNeedle receives file fragments and unpacked files are scored in corpus order. On matched whole-file input, MRR is level with BM25 while Recall@20 remains significantly lower. Development-only lexical forensics point to query-term-frequency handling as the strongest candidate cause; no lexical change has been validated. See `KNOWN_LIMITATIONS.md` §4 and `reports/experimental/`.

### Claim 6: "Heuristic selective abstention reliably identifies no-gold tasks on ARB v2"
- **Status**: **REFUTED / NOT SUPPORTED**
- **Evidence**:
  - Evaluated on $N=82$ total abstention samples across 71 frozen repository snapshots.
  - Natural No-Gold Issues ($N=50$): **0 / 50 correctly abstained (0.0% accuracy)**.
  - Counterfactual Wrong-Repo Queries ($N=32$): **0 / 32 correctly abstained (0.0% accuracy)**.
  - Combined Benchmark ($N=82$): **0 / 82 correctly abstained (0.0% accuracy)**.
  - Empirical Observations:
    - Engine default abstention threshold: $\tau = 0.12$ (`BudgetConfig.abstention_threshold`). *Corrected 2026-11-09: earlier text stated 0.38, which is only the standalone `SelectiveAbstainer` class default and is not used by the engine.*
    - Observed heuristic confidence on the 82 no-gold queries: range `[0.532, 0.891]`, 5th–95th percentile `[0.635, 0.851]`. *Corrected 2026-11-09: earlier text gave `[0.64, 0.86]`. Source: `reports/full_arb_validation/checkpoint_selective.jsonl`.*
    - Every single query exceeded the threshold, producing a 100% false return rate (zero abstention recall).
  - Diagnostic Explanation: Surface vocabulary overlap and score peakiness ($Z$-score) fail on full repositories because:
    1. Real GitHub issues filed against a repository naturally contain identifiers that exist within the repository.
    2. Counterfactual queries contain ubiquitous coding primitives (`parse`, `client`, `handler`, `config`) that match spurious functions in large codebases.

### Claim 7: "Task-adaptive routing (`WorkflowRouter`) is essential to system performance"
- **Status**: **SUPPORTED**
- **Evidence**:
  - Aggregate positive benchmark ($N=345$):
    - Full RepoNeedle MRR: `0.2287`
    - w/o WorkflowRouter MRR: `0.1642`
    - Relative Collapse: $\frac{0.1642 - 0.2287}{0.2287} \times 100\% = \mathbf{-28.20\%}$
  - Explanation: Fixed uniform scoring fails across heterogeneous query intents. Forcing uniform weights eliminates the specialized boost in `code2test` and over-weights graphs on lexical tasks.

### Claim 8: "Budget knapsack packing maximizes context yield under strict token limits"
- **Status**: **SUPPORTED**
- **Evidence**:
  - Measured Budgeted Context Yield (BCY) across all 345 positive samples:
    - BCY@4k: RepoNeedle `0.2436` vs RepoMap `0.2024` ($\mathbf{+20.36\%}$ advantage for RepoNeedle) vs BM25 `0.1220` ($\mathbf{+99.67\%}$ advantage).
    - BCY@8k: RepoNeedle `0.3450` vs BM25 `0.2051` ($\mathbf{+68.21\%}$ advantage).
  - Density knapsack packing ensures small, highly-relevant files and structural skeletons are prioritized over giant monolithic files that consume the context budget.

### Claim 9: "Structural skeletons reduce token payload without sacrificing signatures"
- **Status**: **SUPPORTED**
- **Evidence**:
  - Measured with exact BPE code subword regex (`re.compile(r"[A-Za-z0-9_]+|[^\s\w]|\s+")`):
    - Python Medium Adapter: `2,060` full BPE tokens $\to$ `305` skeleton tokens (**85.2% reduction**).
    - Python Long Session Manager: `4,061` full BPE tokens $\to$ `404` skeleton tokens (**90.1% reduction**).
    - Rust Async RingBuffer: `2,312` full BPE tokens $\to$ `222` skeleton tokens (**90.4% reduction**).
    - TypeScript EventDispatcher: `1,920` full BPE tokens $\to$ `455` skeleton tokens (**76.3% reduction**).
    - Go HTTP Router: `1,225` full BPE tokens $\to$ `578` skeleton tokens (**52.8% reduction**).
  - In all cases, class declarations, struct definitions, public method signatures, and docstrings are preserved.

### Claim 10: "System is lightweight and runs purely on commodity CPU without GPUs"
- **Status**: **SUPPORTED**
- **Evidence**:
  - Measured runtimes across $N=345$ positive samples on Windows AMD64 CPU:
    - Mean Query Latency: `317.7 ms` (Median: `142.4 ms`, $p_{95}$: `827.2 ms`).
    - BM25 Baseline Mean Query Latency: `994.4 ms`.
    - RepoNeedle is `3.1x faster` than the official BM25 inverted index scan.
  - Dependencies: `numpy`, `scipy`, `networkx`, `pydantic`, `pathspec`, `rich`. No PyTorch, no CUDA, no model weight downloads.

---

## 3. What RepoNeedle DOES Achieve vs What It DOES NOT Achieve

### What RepoNeedle DOES Achieve:
1. **Proven Superiority over Classical Lexical & BM25**: $+50.5\%$ relative gain on MRR ($p = 2.65 \times 10^{-6}$) and $+68.2\%$ relative gain on BCY@8k across 345 real-world repository samples.
2. **Strongest Regression Test Discovery Among the Evaluated Baselines (`code2test`)**: $+151.7\%$ MRR over BM25 and $+37.0\%$ over RepoMap via inverted dependency graph AST linkages.
3. **High Context Yield Under Strict Token Budgets**: $+20.4\%$ higher BCY@4k than RepoMap, packing multi-tier structural skeletons to prevent context overflow.
4. **Sub-Second CPU Execution**: $142.4\text{ ms}$ median retrieval latency across real open-source codebases without requiring GPU infrastructure.
5. **Zero Data Contamination**: Strict isolation of proprietary or copyleft non-permissive datasets; 100% permissively licensed MIT release.

### What RepoNeedle DOES NOT Achieve:
1. **Conclusive Statistical Superiority Over RepoMap**: Overall MRR difference ($+0.0148$) is statistically insignificant ($p = 0.4089$), and RepoMap achieves substantially higher deep recall (Recall@20: $0.6306$ vs $0.4279$).
2. **Reliable Selective Abstention on Full Codebases**: Heuristic confidence gating achieved 0.0% accuracy on ARB v2 no-gold benchmarks; a trained neural discriminator is mandatory.
3. **Parity with BM25 on PR-review comment queries (`comment2context`)**: In the official harness, BM25 achieves higher MRR ($0.1974$ vs $0.1708$) on these structured JSON PR-review contexts. On matched whole-file input (supplemental, not official), MRR is level, but RepoNeedle's Recall@20 remains significantly lower. These are not conversational queries; ARB v2 does not measure conversational retrieval.
4. **Span-Level Retrieval**: RepoNeedle selects file-level units and structural skeletons, not fine-grained line-level spans.
5. **Deep Neural Foundation Model Representations**: RepoNeedle is a structured CPU ranking engine, not a pre-trained dense transformer embedding model.

