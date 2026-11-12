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

# 🪡 RepoNeedle Playground (V1.2.0)

Interactive demonstration of **RepoNeedle**: Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents.

> ⚠️ **Methodological Disclosure**: This Playground uses embedded demonstration repository snapshots. It is an interactive demonstration, not a reproduction of the complete ARB v2 evaluation. The embedded corpora are lightweight demonstration slices, not full upstream repository checkouts.

### What this Playground demonstrates (bundled RepoNeedle 1.2.0 engine):
- **Modular Ranking Engine Selection**: Choose between the default `legacy` ranker (V1.0 backwards-compatible multi-signal routing) and the opt-in `change_impact` ranking engine.
- **Change-Impact Graph Propagation**: When seed / anchor files are provided, the engine computes seed-relative relationship scoring across static imports, symbols, and calls with Seed File Suppression (SFS).
- **Seedless Change-Impact Mode**: When run without seed files, the interface clarifies that lexical/semantic scoring and Test Intent Priors remain active while seed-relative relationship boosts and suppression are inactive.
- **Workflow-Adaptive Routing**: Automatic intent classification for `trace2code`, `code2test`, `edit2ripple`, and `comment2context`.
- **CUD-Pack Context Optimization**: Deterministic budget enforcement ($C_{\text{actual}} \le B_{\text{configured}}$) across representation tiers (`FULL`, `FOCUS_SPAN`, `SKELETON`).
- **Multi-System Baseline Comparison**: Side-by-side comparison with classical BM25 and RepoMap PageRank under identical context constraints.
- **Experimental Abstention (opt-in, off by default)**: In 1.2.0 the out-of-scope abstention heuristic is disabled by default, so ranked context is returned for every query. An unchecked **Enable experimental abstention** box lets you opt in. The heuristic is experimental and uncalibrated: on the ARB v2 selective split it correctly abstained on 0 of 82 out-of-scope queries.

### Scope of the demonstration

- The Playground ranks small embedded document snapshots held in memory. It does not index a directory, so it does not exercise 1.2.0's filesystem-level indexing safeguards (link containment, directory-link traversal limits) or report indexing diagnostics.
- The CLI JSON output, `--anchors` validation and the MCP server added in 1.2.0 are not part of this Space. See the [RepoNeedle repository](https://github.com/krishika08/RepoNeedle) for those features and for the documented benchmark results and limitations.
