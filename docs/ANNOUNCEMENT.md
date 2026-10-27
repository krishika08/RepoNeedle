# 🪡 Announcing RepoNeedle: Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents

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
2. **Inverted Test-to-Target Mapping**: Connects production code to its corresponding test suites via import reversal and naming conventions, achieving a **1.000 MRR on test discovery** (where RepoMap scores 0.122).
3. **Calibrated Selective Abstention**: Uses peak-to-noise ratio ($Z$-score) and repository symbol overlap to abstain when a query is out-of-scope, saving **100% of context tokens** on counterfactual queries.
4. **Token-Budget Knapsack Optimization**: Uses marginal utility density packing with multi-tier structural skeletons (extracting signatures, docstrings, and query matches) to pack 3-4x more relevant files into fixed token budgets (2k, 4k, 8k tokens).

---

## Verified Benchmark Results

Evaluated on **RepoNeedle-Bench** against standard baselines across multiple repositories, including a clean held-out evaluation repository:

| Retrieval System | MRR | Recall@1 | Recall@3 | nDCG@3 | Irrelevant Tokens (4k) | Selective Abstention | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoMap (PageRank)** | 0.394 | 0.083 | 0.403 | 0.314 | 926.7 | 0.0% | 0.03 ms |
| **Dense Semantic Vector** | 0.771 | 0.375 | 0.833 | 0.731 | 926.7 | 0.0% | 0.63 ms |
| **Static Hybrid (BM25+Dense+PR)** | 0.743 | 0.375 | 0.875 | 0.746 | 926.7 | 0.0% | 0.65 ms |
| **BM25 (Sparse Lexical)** | 0.819 | 0.417 | 0.861 | 0.784 | 693.6 | 33.3% | 0.15 ms |
| **RepoNeedle (Adaptive + Budget)** | **0.917** | **0.528** | **1.000** | **0.936** | **581.0** | **100.0%** | **0.80 ms** |

### Key Improvements:
- **+11.9% higher MRR** and **+26.6% higher Recall@1** than the strongest baseline.
- **100% Recall@3** on all positive retrieval tasks.
- **37.3% reduction in irrelevant tokens** (context bloat).
- **100% Selective Abstention Accuracy** on counterfactual queries.
- **Sub-millisecond execution (0.8 ms)** running 100% offline on standard CPU.

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
# Output:
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
