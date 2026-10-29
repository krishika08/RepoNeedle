# RepoNeedle Stage 3.8: Graph Damage Analysis & Structural Ranking Audit

**Document ID**: `STAGE3-8-GRAPH-001`  
**Date**: October 2026  
**Stage**: Stage 3.8 — Independent Metric Verification and Retrieval Root-Cause Investigation  
**Branch**: `research-program`  
**Starting Commit**: `fd45220`  
**Source Code References**: [`reponeedle/core/graph.py`](file:///F:/RepoNeedle/reponeedle/core/graph.py), `research/stage3_6/evaluate_systems.py:240-275`  
**Hypothesis Register**: [`research/stage3_8/HYPOTHESIS_REGISTER.csv`](file:///F:/RepoNeedle/research/stage3_8/HYPOTHESIS_REGISTER.csv)  

---

## 1. Executive Summary

Graph-augmented retrieval was introduced to bridge lexical gaps and surface structurally linked files. However, empirical evaluation across 345 positive instances shows that graph augmentation in Candidate C and Candidate F **damaged early retrieval precision**, reducing MRR from $0.1735 \to 0.1351$ while only marginally improving Recall@20 ($0.4549 \to 0.5078$).

This document audits the seven specific failure mechanisms that cause graph-induced ranking damage.

---

## 2. Hypothesis Audits & Empirical Evidence

### Hypothesis 1: Dense Utility Nodes & Large Import Hubs Dilute Relevance (`HYP-01`)
- **Status**: **HIGH CONFIDENCE (VERIFIED)**
- **Mechanism**: In large multi-package codebases (`etcd`, `caddy`, `eslint`, `gin`), common utility, error, and configuration files have in-degrees exceeding $50\text{–}120$. When static PageRank runs, these nodes accumulate up to $35\%$ of total stationary graph mass.
- **Empirical Evidence**:
  - In `caddyserver/caddy`, `caddyconfig/caddyfile/adapter.go` and `admin.go` appear in the top-5 retrieved files for $78\%$ of all queries, displacing query-specific modules like `modules/caddytls/acmeissuer.go`.
  - In 70 queries (`BM25_WIN_CAND_DEMOTED`), BM25 placed the exact target in ranks 1–5, but static graph mass promoted a central utility ahead of it, destroying MRR.

### Hypothesis 2: Cross-Package Edges Spoil Module Boundaries (`HYP-02`)
- **Status**: **HIGH CONFIDENCE (VERIFIED)**
- **Mechanism**: `reponeedle/core/graph.py:382-385` implements language-agnostic symbol resolution:
  ```python
  if not target_path and imp in self.symbol_to_paths:
      for def_path in self.symbol_to_paths[imp]:
          if def_path != doc.path:
              self.graph.add_edge(doc.path, def_path)
  ```
  This logic does not check package, crate, or directory boundaries. If an imported identifier matches a symbol named `Config`, `Parse`, `New`, or `Run`, directed edges are created between completely unrelated packages.
- **Empirical Evidence**: In Go monorepos, package-level imports created over $12,000$ cross-package edges. This caused MRR on Go codebases ($N=142$) to collapse from $0.2665 \to 0.1587$ ($\Delta = -0.1078$).

### Hypothesis 3: Graph Score Scale Overwhelms Lexical Relevance (`HYP-03`)
- **Status**: **HIGH CONFIDENCE (VERIFIED)**
- **Mechanism**: In Candidate C (`evaluate_systems.py:244`), static PageRank is combined with lexical and semantic scores via equal unweighted averaging:
  $$\text{score} = \frac{\text{lexical} + \text{semantic} + \text{pagerank}}{3.0}$$
  Because `pagerank_scores` is min-max normalized to $[0, 1]$, top graph hubs receive $+0.33$ points automatically on *every query*, even when their lexical query match is $0.0$.
- **Empirical Evidence**: A document with an exact lexical match of $0.30$ and $0.0$ PageRank is scored at $0.10$. A generic utility hub with $0.05$ lexical match and $1.0$ PageRank is scored at $0.35$, easily leapfrogging the true target file.

### Hypothesis 4: Bidirectional Diffusion Bleeds Relevance Across Unrelated Callers (`HYP-04`)
- **Status**: **HIGH CONFIDENCE (VERIFIED)**
- **Mechanism**: In Candidate F (`evaluate_systems.py:267-274`), graph diffusion runs over top-5 seeds:
  ```python
  for succ in g.graph.successors(seed_path):
      diffused_boost[n_idx] = max(diffused_boost[n_idx], float(seed_val * 0.25))
  for pred in g.graph.predecessors(seed_path):
      diffused_boost[n_idx] = max(diffused_boost[n_idx], float(seed_val * 0.20))
  ```
  Crucially, diffusion is **unnormalized by node out-degree** (standard PPR divides by $d_{\text{out}}$). Furthermore, predecessor diffusion (weight $0.20$) sends energy backward to all callers. If a seed imports `log` or `context`, backward diffusion boosts every caller of `log` across the repository.
- **Empirical Evidence**: On `edit2ripple` ($N=58$), where ripples should follow forward call chains, backward predecessor diffusion caused MRR to plummet from $0.2452 \to 0.1284$ (a $47.6\%$ drop).

### Hypothesis 5: Graph Edges Are Missing for Relevant Test Files (`HYP-05`)
- **Status**: **HIGH CONFIDENCE (VERIFIED)**
- **Mechanism**: On `code2test` tasks ($N=106$), the objective is to find corresponding tests. In Go and Rust, test files frequently reside in the same package (using package-internal access) or run via integration runners without explicit module import statements in the test file pointing to the source file.
- **Empirical Evidence**:
  - `reponeedle/core/graph.py` fails to construct edges between implementation files and test files in $68\%$ of Go/Rust samples.
  - As a result, Candidate F achieves an abysmal $0.0601$ MRR on `code2test`, while RepoMap (which uses tree-sitter symbol reference tagging) achieves **$0.2284$ MRR** ($3.8\times$ higher).

### Hypothesis 6: Manifest & Symbol Parsing Create Short-Name Collisions (`HYP-06`)
- **Status**: **MEDIUM CONFIDENCE (VERIFIED)**
- **Mechanism**: In `reponeedle/core/graph.py:346-349`:
  ```python
  if "." in mod_name:
      short_name = mod_name.split(".")[-1]
      if short_name not in self.module_to_path:
          self.module_to_path[short_name] = doc.path
  ```
  Binding single-word short names (e.g. `test`, `util`, `types`, `builder`) into `module_to_path` causes first-write-wins collisions, redirecting import resolutions to arbitrary, unrelated files across the repository.
- **Empirical Evidence**: Inspecting the graph for `etcd` showed that imports referencing `pkg/types` resolved to an unrelated documentation test helper due to short-name collision.

### Hypothesis 7: Early-Rank Demotion Mathematically Dominates Metric Outcomes (`HYP-07`)
- **Status**: **VERY HIGH CONFIDENCE (PROVEN)**
- **Mechanism**: The Reciprocal Rank function $RR = 1/r$ is convex and hyper-sensitive to ranks 1 and 2:
  - Demoting 1 query from Rank 1 to Rank 4 loses $1.0 - 0.25 = \mathbf{0.75}$ RR points.
  - Promoting 1 query from Rank 30 to Rank 15 gains only $1/15 = \mathbf{0.0667}$ RR points.
  - It requires **11.25 late-rank promotions** to compensate for a single early-rank demotion!
- **Empirical Evidence**:
  - Across all 345 queries, Candidate F lost 14 Rank-1 hits and 14 Rank-2 hits (losing $21.0$ RR points).
  - It picked up 25 new hits at ranks 11–20 (adding only $1.82$ RR points).
  - Net loss: $-19.18$ RR points $\implies -0.0556$ global MRR impact on those queries.

---

## 3. Structural Comparison: RepoNeedle Graph vs. RepoMap Tag Graph

Why does RepoMap achieve $0.2293$ MRR and $0.6599$ Recall@20 while RepoNeedle's graph collapses?

| Architectural Feature | RepoNeedle Graph (Candidate F) | Pinned Official RepoMap (`9e4d689`) |
| :--- | :--- | :--- |
| **Parsing Engine** | Heuristic regex + Python `ast` | Multi-language Tree-Sitter grammars |
| **Edge Precision** | Unfenced symbol name string matching | Def-Use call references via AST scope tables |
| **Node Granularity** | Entire file (`FileDoc`) | File-level definition tags + call signatures |
| **PageRank Weighting** | Static PageRank + flat 0.25/0.20 diffusion | Personalized PageRank seeded by query tokens |
| **Degree Normalization**| None ($max(\cdot, seed \times 0.25)$) | Normalized edge weights ($1 / \text{out\_degree}$) |
| **Early Rank Protection**| Unprotected equal fusion | Lexical seed relevance strictly gates graph expansion |

---

## 4. Remediation Blueprint for Future Stages

To resolve graph damage without discarding structural evidence:
1. **Cascaded Two-Stage Architecture**:
   - Stage 1: Preserve BM25 ranking for top-$K$ ($K=3$). Never permit graph reranking to demote a high-confidence lexical rank-1 candidate.
   - Stage 2: Apply graph reranking strictly as a candidate expansion filter for ranks $\ge 4$.
2. **Degree-Normalized Personalized PageRank (PPR)**:
   - Eliminate static query-independent PageRank.
   - Compute query-seeded PPR with edge weights $w_{uv} = 1 / d_{\text{out}}(u)$.
3. **Package & Visibility Fencing**:
   - Restrict symbol-to-path edges to files within the same package or files with explicit manifest dependency linkages.
4. **Bipartite Co-Change & Lexical Edges for Tests**:
   - Automatically link `foo.go` to `foo_test.go` and `src/bar.py` to `tests/test_bar.py` to resolve the $0.0601$ `code2test` blindspot.
