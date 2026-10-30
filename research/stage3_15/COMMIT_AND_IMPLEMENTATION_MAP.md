# RepoNeedle Stage 3.15 — Commit and Implementation Identity Map

**Document ID**: `STAGE3-15-IMPL-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Current HEAD**: `12142e8`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`)  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`)  

---

## 1. Executive Lineage & Ancestry Findings

A forensic audit of Git commit ancestry confirms that Stage 3.5 commit `4f78cc3` and Stage 3.14 commit `12142e8` belong to the **exact same direct, linear Git history**:

```
8e00425 (v0.1.0-baseline)
   │
cd7f3b0 (stage3-candidate-freeze)
   │
4f78cc3 (Stage 3.5 Report & Polyglot Graph Commit)
   │
   ├── cbe6c49 (Stage 3.6 Authoritative Full-Corpus Evaluation)
   ├── 91c6df8 (Stage 3.9 Component Isolation & Ranking Recovery)
   ├── e350b14 (Stage 3.12 Hardening)
   ├── 21d2586 (Stage 3.10 Class-to-Test Graph)
   ├── 3f4822d (Stage 3.11 Function-Level Call Graph)
   ├── 809ee6a (Stage 3.12A Factorial Preregistration)
   ├── 275f0ae (Stage 3.12 Factorial Graph Retrieval)
   ├── 8218812 (Stage 3.13 Canonical Reproducibility)
   └── 12142e8 (Stage 3.14 Language-Aware Hub Attenuation & Validation) [HEAD]
```

- Merge Base: `git merge-base 4f78cc3 12142e8` returns `4f78cc3658dfb5e338a5458579d38d5d7ef416e8`.
- No history rewrites, resets, or divergent branching occurred.

---

## 2. Systematic Implementation Matrix

| System Identifier | Exact Source Commit | Ranking Pipeline Architecture | Lexical Scoring & Damping | Graph Edge Construction & Diffusion | Context Packing Policy | Doc Filtering | Abstention Behavior | Primary Evaluator Entry Point |
|---|---|---|---|---|---|---|---|---|
| **`BASE-BM25`** | `12142e8` | Pure lexical keyword retrieval | Decoupled Okapi BM25 with document length normalization ($k_1=1.5, b=0.75$) | None ($W_{\text{graph}} = 0.0$) | Skeletons permitted, standard token packing (8k budget) | Disabled ($1.0\times$) | Default vocab match | `reponeedle.core.lexical.BM25Index` |
| **`BASE-REPOMAP`** | Pinned `9e4d689` | Aider-style tree-sitter AST call graph PageRank | Tree-sitter identifier frequency | Global PageRank on AST-extracted definition/reference call graph | Tag-based definition packing | External | External | Pinned official `RepoMap` evaluation runner |
| **`CAND-C`** | `cd7f3b0` / `4f78cc3` | Weighted sum fusion: $\frac{1}{3} \text{BM25} + \frac{1}{3} \text{Semantic} + \frac{1}{3} \text{PageRank}$ | Coupled token/path BM25 | Python AST import graph + file-level PageRank; single-hop diffusion | Skeletons permitted, greedy packing | Enabled ($0.5\times$ penalty on `/docs/`) | Standard SelectiveAbstainer | `AblationConfig.candidate_c()` in `reponeedle.engine` |
| **`CAND-F`** | `4f78cc3` | Weighted sum fusion + manifest-aware polyglot graph | Coupled token/path BM25 | Cargo.toml / go.mod / package.json manifest resolution + bidirectional diffusion | Skeletons permitted + implementation preservation priority | Enabled ($0.5\times$ penalty) | Stemmed SelectiveAbstainer (`_stem`) | `AblationConfig.candidate_e()` in `research/stage3_5/evaluate_graph_retrieval.py` |
| **`CONTROL-CASCADE`** | `064e619` | Rigid cascaded lexical-first ranker | Decoupled Okapi BM25 seeds ($K=3$) | Bounded graph diffusion ($\text{degree} \le 25$), PageRank disabled | Skeletons permitted, token packing | Enabled ($0.5\times$ penalty) | Active selective abstention | `reponeedle.core.cascade.CascadedRanker` |
| **`ARM-101-BASE`** | `12142e8` / `809ee6a` | Cascaded ranker with Soft Lexical Damping ($\tau=0.25$) | Decoupled Okapi BM25; $\Delta_{\text{lexical}} = \text{BM25}_1 - \text{BM25}_2$ | Level 1 verified function call graph; unattenuated hub weighting ($W_{\text{hub}}=1.0$) | Skeletons permitted, token budget packing (8k) | Enabled ($0.5\times$ penalty) | Active selective abstention | `research/stage3_14/pilot_attenuation.py` / `research/stage3_12/run_stage3_12_benchmarks.py` |
| **`ARM-111-UNIFORM`** | `12142e8` / `809ee6a` | Cascaded ranker with Soft Lexical Damping ($\tau=0.25$) | Decoupled Okapi BM25; soft damping threshold | Level 1 verified function call graph; uniform logarithmic hub attenuation $1 / \log_2(2 + \text{deg}_{\text{in}})$ | Skeletons permitted, token budget packing (8k) | Enabled ($0.5\times$ penalty) | Active selective abstention | `research/stage3_14/pilot_attenuation.py` |

---

## 3. Forensic Code Presence Audit: Are Candidate F's Changes Present in HEAD?

A critical requirement of Phase 1 is determining whether Candidate F's manifest-aware polyglot graph changes and context-packing changes are present in the source tree described by Stage 3.14 (`12142e8`).

### 3.1 `reponeedle/core/abstention.py`
- **Stage 3.5 changes**: Added static method `_stem()` to strip common English suffixes (`"ing"`, `"ed"`, `"es"`, `"s"`) and incorporated stemmed tokens into repository vocabulary building and query overlap calculations.
- **Presence at HEAD (`12142e8`)**: **100% PRESENT and IDENTICAL**. A direct Git diff (`git diff 4f78cc3..12142e8 -- reponeedle/core/abstention.py`) produces **zero diff lines**. The Stage 3.5 stemming logic was never reverted.

### 3.2 `reponeedle/core/graph.py`
- **Stage 3.5 changes**:
  1. `parse_cargo_manifest()`: Parses `Cargo.toml` for package name, workspace members, and path dependencies.
  2. `parse_go_mod()`: Extracts module path from `go.mod`.
  3. `parse_package_json()`: Extracts npm package name and dependencies.
  4. Polyglot mappings: `symbol_to_paths`, `package_to_files`, `manifest_crates`, `crate_dependencies`.
  5. Cross-crate entrypoint coupling.
  6. Targeted Ripgrep string bypasses: `norm_p.endswith(("search.rs", "standard.rs"))` and `("core" in my_crate and "printer" in o_crate)`.
- **Presence at HEAD (`12142e8`)**:
  - The general manifest-aware parsers (`parse_cargo_manifest`, `parse_go_mod`, `parse_package_json`, `package_to_files`, `manifest_crates`, `crate_dependencies`) are **100% PRESENT** in [`reponeedle/core/graph.py`](file:///F:/RepoNeedle/reponeedle/core/graph.py#L86-L160).
  - The hardcoded Ripgrep bypass strings (`search.rs`, `standard.rs`, and `"core" in my_crate and "printer" in o_crate`) were **EXCISED** in commit `9a9944a` during the Stage 3.6 forensic audit because they were unprincipled single-query shortcuts.
  - Stage 3.10 added class-to-test invocation linkage (`_extract_class_to_test_linkages`).

### 3.3 `reponeedle/engine.py`
- **Stage 3.5 changes**: Added bidirectional diffusion along graph successors ($0.25\times$) and predecessors ($0.20\times$).
- **Evolution between Stage 3.5 and Stage 3.14**:
  1. **PageRank Decoupling**: In Stage 3.9, global PageRank fusion was decoupled and disabled by default (`use_pr = ablation.enable_graph and getattr(ablation, "enable_pagerank_fusion", False)`). Forensic audits proved that global PageRank on polyglot graphs was creating dense supernodes that flooded random walks and collapsed retrieval accuracy.
  2. **Bounded Diffusion Degree**: Stage 3.9 introduced `max_deg = getattr(ablation, "max_diffusion_degree", 25)` to prevent high-degree hub explosion.
  3. **Candidate Slicing**: Stage 3.12 introduced sparse candidate pool slicing for CONFIG-10.

### 3.4 Why the Stage 3.14 Report Stated "Production Source Code was not Modified"
The user requested an explanation of why Stage 3.14 reported that production source code was not modified.
- **Explanation**: In Stage 3.14, the mission charter explicitly mandated:
  *"This is a controlled research stage. Do not modify production files under `reponeedle/` until an experimental improvement has passed explicit acceptance criteria."*
- Because all experimental hub attenuation variants (`ARM-111-UNIFORM`, `LANG-CALIBRATED`, `STRUCTURAL-ROLE`) failed to outperform unattenuated `ARM-101-BASE` ($0.2078$ MRR), the formal verdict was `NO ROBUST IMPROVEMENT`.
- Therefore, in strict adherence to research integrity, **no modifications to `reponeedle/` were made during Stage 3.14**. The experimental rankers were implemented entirely within research scripts (`research/stage3_14/pilot_attenuation.py` and `run_stage3_14_experiments.py`), leaving production code unchanged.
