---
title: RepoNeedle Playground
emoji: 🪡
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 4.29.0
app_file: app.py
pinned: false
license: mit
---

# 🪡 RepoNeedle Playground

Interactive demonstration of **RepoNeedle**: Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents.

### Features
- **Live Retrieval**: Execute real-time retrieval across repository snapshots.
- **Workflow-Adaptive Routing**: Automatic intent detection for `trace2code`, `code2test`, `edit2ripple`, and `comment2context`.
- **Experimental Selective Abstention**: Inspect selective retrieval heuristics (Note: experimental; achieved 0.0% on official ARB v2 no-gold benchmarks).
- **Baseline Comparison**: Compare RepoNeedle against classical BM25 and RepoMap PageRank under identical constraints.
- **Token Budget Packing**: Inspect full files vs. structural skeletons packed under strict token budgets.

