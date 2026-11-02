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

# 🪡 RepoNeedle Playground (V1.1.0)

Interactive demonstration of **RepoNeedle**: Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents.

> ⚠️ **Methodological Disclosure**: This Playground uses embedded demonstration repository snapshots. It is an interactive demonstration, not a reproduction of the complete ARB v2 evaluation. The embedded corpora are lightweight demonstration slices, not full upstream repository checkouts.

### Key Capabilities in V1.1.0:
- **Modular Ranking Engine Selection**: Choose between the default `legacy` ranker (V1.0 backwards-compatible multi-signal routing) and the opt-in `change_impact` ranking engine.
- **Change-Impact Graph Propagation**: When seed / anchor files are provided, the engine computes seed-relative relationship scoring across static imports, symbols, and calls with Seed File Suppression (SFS).
- **Seedless Change-Impact Mode**: When run without seed files, the interface clarifies that lexical/semantic scoring and Test Intent Priors remain active while seed-relative relationship boosts and suppression are inactive.
- **Workflow-Adaptive Routing**: Automatic intent classification for `trace2code`, `code2test`, `edit2ripple`, and `comment2context`.
- **CUD-Pack Context Optimization**: Deterministic budget enforcement ($C_{\text{actual}} \le B_{\text{configured}}$) across representation tiers (`FULL`, `FOCUS_SPAN`, `SKELETON`).
- **Multi-System Baseline Comparison**: Side-by-side comparison with classical BM25 and RepoMap PageRank under identical context constraints.
