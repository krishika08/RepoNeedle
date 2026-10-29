# RepoNeedle Stage 3.10 — Research Plan: Class-to-Test Invocation Graph

## 1. Executive Summary

- **Stage**: 3.10
- **Workspace**: `F:\RepoNeedle`
- **Branch**: `research-program`
- **Starting Commit**: `110ff88d7f16c796fc24b55c569ceb2345d514ce` (Stage 3.9.2 completed and clean)
- **Primary Objective**: Determine whether a statically inferred, evidence-backed class-to-test invocation graph improves repository-level retrieval on Agent Retrieval Bench (ARB) v2 under the canonical evaluation contract (`research/stage3_9_2/CANONICAL_EVALUATION_CONTRACT.md`), without sacrificing lexical match precision, repository-scale performance, or reproducibility.

## 2. Research Problem & Architecture Motivation

In Stage 3.9, RepoNeedle established a cascaded lexical-first ranking architecture (`CAND-CASCADE`):
- Rank 1–3 BM25 freeze: Exact lexical matches at top ranks are preserved unconditionally to protect high-precision code queries.
- Bounded degree-normalized graph diffusion on ranks $\ge 4$: Graph connections propagate relevance from high-confidence seeds to adjacent files.
- Package fencing: Prevents graph diffusion across unrelated submodules or external crates.
- Filename-based test discovery: Maps `foo.py` to `test_foo.py` or `tests/test_foo.py`.

### The Filename-Matching Blindspot
Filename matching fails when test files do not follow exact stem-symmetry. In modern multi-module architectures:
- `src/transports/http.py` defining `HttpClient` is tested in `tests/test_client.py`.
- `gin.go` defining `Engine` and `Context` is exercised across `routes_test.go`, `context_test.go`, and `tree_test.go`.
- `fastapi/responses.py` defining `ORJSONResponse` is tested in `tests/test_orjson_response_class.py`.

Under pure filename matching, these critical cross-file test dependencies receive zero graph propagation.

### The Proposed Enhancement
Stage 3.10 introduces a language-aware, evidence-backed class-to-test invocation graph:
1. Production classes, structs, traits, and exported methods are cataloged across Python, Rust, Go, and TypeScript/JavaScript.
2. Test files are inspected for direct class construction, method calls, and imported module invocations.
3. Inferred edges are gated by strict disambiguation hierarchies and generic-name suppression to prevent high-degree hub explosion.
4. Edge weights are degree-normalized ($\frac{1}{\sqrt{d_{\text{out}} \cdot d_{\text{in}}}}$) during bidirectional score propagation.

## 3. Pre-Registered Evaluation Arms

To isolate the causal mechanism of the invocation graph and rule out connectivity artifacts, four arms are evaluated:

| Arm ID | Arm Name | Configuration | Purpose |
|---|---|---|---|
| **Arm A** | `CONTROL-CASCADE` | `enable_class_to_test=False`, `enable_degree_matched_control=False` | Authoritative control baseline (Stage 3.9 architecture) |
| **Arm B** | `TEST-GRAPH` | `enable_class_to_test=True`, `enable_degree_matched_control=False`, $w=0.35$ | Active treatment: class-to-test invocation edges enabled |
| **Arm C** | `DEGREE-CONTROL` | `enable_class_to_test=True`, `enable_degree_matched_control=True`, $w=0.35$ | Bipartite degree-matched random graph control |
| **Arm D** | `GRAPH-ABLATION` | `enable_class_to_test=False`, `enable_degree_matched_control=False` | Verifies exact bitwise equivalence with Arm A |

In addition, two reference baselines are tracked:
- `BASE-BM25`: Official Okapi BM25 ($k_1=1.5, b=0.75$) with decoupled length normalization.
- `BASE-REPOMAP`: Version-pinned official RepoMap reference (commit `9e4d689`).

## 4. Evaluation Universe & Protocol

- **Denominator**: Exactly 345 positive ARB v2 benchmark queries across 218 repository snapshots:
  - `v2_code2test`: 106 queries (primary mechanism target)
  - `v2_comment2context`: 80 queries
  - `v2_trace2code`: 101 queries
  - `v2_edit2ripple`: 58 queries
- **Candidate Pool**: Fully unconstrained repository candidate universe. Zero task-specific candidate filtering, oracle routing, or diagnostic shortcuts.
- **Tie-Breaking**: Deterministic lexicographical tie-breaking by ascending relative file path.
- **Metrics Tracked**:
  - MRR (Mean Reciprocal Rank) across the full unconstrained repository ranked list.
  - Fractional Multi-Target Recall: Recall@5, Recall@10, Recall@20 ($\frac{|\text{TopK} \cap \text{Gold}|}{|\text{Gold}|}$).
  - Hit@20: Binary hit indicator ($1$ if $|\text{Top20} \cap \text{Gold}| > 0$, else $0$).
  - Precision@5: ($\frac{|\text{Top5} \cap \text{Gold}|}{5}$).
  - Token-budgeted Context Coverage: BCY@8k tokens.
  - Latency: p50, p95, and mean query latency in milliseconds.
  - Process RSS: Physical working set size measured via native OS process APIs.
  - Graph Diagnostics: Node count, base edge count, invocation edge count, unresolved references, high-degree nodes.

## 5. Statistical Methodology

- **Paired Per-Query Analysis**: Difference $\Delta_i = \text{MRR}_{\text{TEST-GRAPH}, i} - \text{MRR}_{\text{CONTROL-CASCADE}, i}$.
- **Bootstrap Confidence Intervals**:
  - Query-level 95% paired bootstrap CI ($B = 10,000$ resamples, deterministic seed 42).
  - Repository-clustered 95% bootstrap CI ($B = 10,000$ resamples, clustering on unique repositories).
- **Hypothesis Testing**: Two-sided Wilcoxon signed-rank test on non-zero paired differences.
- **Mechanism Check**: Direct comparison of Arm B (`TEST-GRAPH`) against Arm C (`DEGREE-CONTROL`) to prove that performance gains stem from genuine invocation semantics rather than arbitrary graph connectivity.
