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
- **Workflow-Adaptive Routing**: Automatic intent detection for `trace2code`, `code2test`, `edit2ripple`, `comment2context`, and `selective`.
- **Calibrated Abstention**: Inspect selective retrieval decisions on out-of-repo and counterfactual queries.
- **Baseline Comparison**: Compare RepoNeedle against classical BM25, RepoMap PageRank, and Dense Semantic search.
- **Token Budget Packing**: Inspect full files vs. structural skeletons packed under strict token budgets.
