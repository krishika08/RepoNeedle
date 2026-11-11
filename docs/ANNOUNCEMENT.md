# 🪡 Announcing RepoNeedle: Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents

> [!CAUTION]
> **Historical document with corrections (corrected 2026-11-09).** This announcement was written for the **v0.1.0 research preview** (October 2026). It is kept for the record, but several of its original claims were not supported by later evaluation and have been corrected in place below:
> - **Selective abstention**: The original text described a "calibrated" abstention mechanism with perfect accuracy. That figure came from a synthetic benchmark containing only **3** selective samples. On the official Agent Retrieval Bench v2 selective split (**N = 82** no-gold queries) the heuristic correctly abstained on **0 of 82 (0.0%)**. The heuristic is uncalibrated and experimental, and from 1.2.0 (upcoming) it is **disabled by default**.
> - **Benchmark table**: The table below reports the v0.1.0 synthetic **RepoNeedle-Bench** run (15 samples). The stored result file (`benchmarks/results/benchmark_results.json`) is **not reproducible** by any later code version (1.1.0 or the pre-release 1.2.0 development branch); current re-run values are shown alongside.
> - **Latency**: Sub-millisecond latency was measured on tiny synthetic corpora. On real repositories (ARB v2) mean query latency is ~318 ms (see README, Part D).
>
> For current, evidence-backed results see [README.md](../README.md), [CLAIMS_AND_EVIDENCE.md](../CLAIMS_AND_EVIDENCE.md), [KNOWN_LIMITATIONS.md](../KNOWN_LIMITATIONS.md) and [BENCHMARK_CONFIGURATION.md](BENCHMARK_CONFIGURATION.md).

Today we are releasing **RepoNeedle**: an open-source, reproducible repository-context retrieval system engineered specifically for AI coding agents operating under strict context-token budgets.

RepoNeedle is available under the permissive **MIT License**, with full reproducible benchmarks, dataset cards, and an interactive Playground on Hugging Face.

---

## The Upstream Problem in Coding Agents

Modern coding agents (e.g. Claude Code, Aider, OpenHands, Cline) face a severe upstream bottleneck: **Context Acquisition**.

When an agent tackles a bug report, adds regression tests, or refactors a component, it cannot pass the entire repository into its prompt. Existing retrieval approaches suffer from major failure modes:
1. **Generic Dense Embeddings**: Blind to file token lengths, blind to repository dependency graphs, and prone to retrieving massive files that exhaust the context budget.
2. **Structural PageRank (e.g., RepoMap)**: Excellent at architectural hubs, but completely blind to test files (which are leaf nodes in call graphs) and unable to route specialized tasks like error tracebacks.
3. **Context Waste & Bloat**: As recent studies (ContextBench, Agent Retrieval Bench) have shown, agents load massive amounts of irrelevant code, increasing latency and cost while causing lost-in-the-middle reasoning failures.
4. **Selective Hallucination**: When a query asks about something not in the codebase (or external libraries), existing retrievers still hallucinate top-k files instead of abstaining.

---

## What RepoNeedle Delivers

RepoNeedle solves these bottlenecks through four complementary innovations:

1. **Workflow-Adaptive Routing**: Automatically classifies task intent (`trace2code`, `code2test`, `edit2ripple`, `comment2context`, `selective`) and dynamically adjusts retrieval weights between AST symbols, inverted dependency graphs, dense subwords, and lexical matching.
2. **Inverted Test-to-Target Mapping**: Connects production code to its corresponding test suites via import reversal and naming conventions, achieving a **1.000 MRR on test discovery** on the synthetic benchmark (where RepoMap scores 0.122). *On real repositories (ARB v2 `code2test`, N=106) the measured MRR is 0.2660 vs RepoMap 0.1942; see README.*
3. **Selective Abstention (experimental heuristic, corrected)**: A heuristic combining repository vocabulary overlap, score peakiness ($Z$-score) and score margin was intended to abstain on out-of-scope queries. *Correction: it is not calibrated. It correctly abstained on 0 of 82 no-gold queries on ARB v2 and is disabled by default on the current development branch.*
4. **Token-Budget Knapsack Optimization**: Uses marginal utility density packing with multi-tier structural skeletons (extracting signatures, docstrings, and query matches) to fit more relevant context into fixed token budgets (2k, 4k, 8k tokens). *The original "3-4x more files" figure was not backed by a recorded measurement and has been removed.*

---

## Benchmark Results (v0.1.0 synthetic benchmark — historical)

Evaluated on the synthetic **RepoNeedle-Bench** (`benchmarks/runner.py`): **15 samples** (12 positive, 3 selective) across small hand-built corpora, including a held-out repository. These are small toy corpora, not real-world repositories.

**As originally published with v0.1.0** (stored in `benchmarks/results/benchmark_results.json`; *not reproducible by later code*):

| Retrieval System | MRR | Recall@1 | Recall@3 | nDCG@3 | Irrelevant Tokens (4k) | Selective (N=3) | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoMap (PageRank)** | 0.394 | 0.083 | 0.403 | 0.314 | 926.7 | 0/3 | 0.03 ms |
| **Dense Semantic Vector** | 0.771 | 0.375 | 0.833 | 0.731 | 926.7 | 0/3 | 0.63 ms |
| **Static Hybrid (BM25+Dense+PR)** | 0.743 | 0.375 | 0.875 | 0.746 | 926.7 | 0/3 | 0.65 ms |
| **BM25 (Sparse Lexical)** | 0.819 | 0.417 | 0.861 | 0.784 | 693.6 | 1/3 | 0.15 ms |
| **RepoNeedle (Adaptive + Budget)** | 0.917 | 0.528 | 1.000 | 0.936 | 581.0 | 3/3 | 0.80 ms |

**Re-run on 2026-11-09** with the same harness and data. Identical values from the released 1.1.0 code and from the pre-release 1.2.0 development branch (experimental abstention explicitly enabled for the 3 selective samples only):

| Retrieval System | MRR | Recall@1 | Recall@3 | nDCG@3 | Irrelevant Tokens (4k) | Selective (N=3) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoMap (PageRank)** | 0.394 | 0.083 | 0.403 | 0.314 | 926.7 | 0/3 |
| **Dense Semantic Vector** | 0.771 | 0.375 | 0.833 | 0.731 | 926.7 | 0/3 |
| **Static Hybrid (BM25+Dense+PR)** | 0.743 | 0.375 | 0.875 | 0.753 | 926.7 | 0/3 |
| **BM25 (Sparse Lexical)** | 0.806 | 0.417 | 0.861 | 0.779 | 693.6 | 1/3 |
| **RepoNeedle (Adaptive + Budget)** | **0.861** | **0.500** | **0.903** | **0.846** | 1042.5 | 2/3 |

### Observations (corrected)
- On this small synthetic benchmark RepoNeedle has the highest MRR, Recall@1, Recall@3 and nDCG@3 in both the original and the re-run results.
- In the re-run, RepoNeedle does **not** have the fewest irrelevant tokens (BM25 is lower), and Recall@3 is 0.903, not 100%.
- Selective accuracy on a 3-sample synthetic set is not evidence of reliable abstention. On the real ARB v2 selective split (N=82) the heuristic abstained on **0/82**.
- Synthetic-corpus latencies (sub-millisecond) do not transfer to real repositories (ARB v2 mean ~318 ms per query).

---

## Before and After Example

### Scenario: Finding tests for `SecureCookieSessionInterface` in Flask

```python
# Before (Standard RepoMap / Centrality):
# RepoMap ranks:
# 1. src/flask/app.py (hub)
# 2. src/flask/__init__.py (hub)
# 3. src/flask/ctx.py (hub)
# Result: Test files are completely missed because tests are leaf nodes!

# With RepoNeedle:
from reponeedle.engine import RepoNeedleEngine

engine = RepoNeedleEngine.from_directory("./flask")
result = engine.retrieve("Find unit tests for SecureCookieSessionInterface", budget_tokens=4000)

for f in result.selected_files:
    print(f"Rank {f.path} [{f.tier.value.upper()}] - Tokens: {f.token_count} - Score: {f.score:.3f}")
# Illustrative output (not a recorded run):
# Rank tests/test_sessions.py [FULL] - Tokens: 165 - Score: 1.000 (Inverted test linkage)
# Rank src/flask/sessions.py [FULL] - Tokens: 240 - Score: 0.875 (Target implementation)
```

---

## Community Outreach & Next Steps

We are sharing RepoNeedle with maintainers in the agent ecosystem:
- **Aider & OpenHands Maintainers**: Providing a lightweight PR or MCP tool to replace static RepoMap with workflow-adaptive budget packing.
- **SWE-bench Researchers**: Providing RepoNeedle-Bench as a clean, upstream context benchmark without CC-BY-NC licensing encumbrances.

Try the Hugging Face Space: `https://huggingface.co/spaces/RepoNeedle/RepoNeedle-Playground`
Explore the Benchmark Dataset: `https://huggingface.co/datasets/RepoNeedle/RepoNeedle-Bench`

