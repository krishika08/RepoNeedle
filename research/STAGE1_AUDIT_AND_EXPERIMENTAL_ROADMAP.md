# STAGE 1 AUDIT REPORT AND EXPERIMENTAL ROADMAP

**Document ID**: `STAGE1-AUDIT-2026-001`  
**Date**: 2026-10-28  
**Author**: Principal Retrieval Researcher & Lead Systems Engineer  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Baseline Commit**: `2deb015a4c20bc9ddaebefcdd32608232e502dc0` (Tagged: `v0.1.0-baseline`)  
**Status**: APPROVED & ACTIVE  

---

## 1. Executive Summary

This report establishes the foundation for the long-term research program to build the best repository-context retrieval system for AI coding agents.

Rather than optimizing blindly against a single public score, this program establishes a dual-track strategy:
- **Track A: Best Practical System**: Maximizes retrieval precision, context efficiency, and token density on commodity CPU with sub-200ms latency, zero heavy dependencies, and instant cold start.
- **Track B: Maximum-Quality System**: Explores deep neural code embeddings, cross-encoder rerankers, and multi-hop graph diffusion for complex architectural bug localization.

Every claim is backed by reproducible empirical data. The baseline v0.1.0 system has been audited from raw prediction records across all 427 samples of the official Agent Retrieval Bench v2. All failure modes have been cataloged into an actionable error taxonomy, and rigorous leakage controls have been preregistered before launching new tuning experiments.

---

## 2. Full Audit of Current Implementation & Baseline Performance

### A. Codebase & Test Suite Health
- Core modules audited: `reponeedle.core.lexical`, `semantic`, `graph`, `router`, `abstention`, `budget`, `tokenizer`.
- All 34 automated unit and quality robustness tests are passing (`pytest -v` passing in 2.80s).
- Package builds cleanly into sdist and wheel (`twine check dist/*` verified PASSED).
- Command-line interface (`reponeedle --help`) verified functional with sub-5ms query latency on local code.

### B. Verified Baseline Metrics (Independent Re-computation from Disk)
Re-calculated directly from [`reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl`](file:///F:/RepoNeedle/reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl) ($N=345$) and [`checkpoint_selective.jsonl`](file:///F:/RepoNeedle/reports/full_arb_validation/checkpoint_selective.jsonl) ($N=82$):

| Metric / Track | RepoNeedle v0.1.0 | Official RepoMap | Official BM25 | Official Lexical | Status / Significance |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Overall MRR ($N=345$)** | **0.2287** | 0.2140 | 0.1520 | 0.1574 | $+50.5\%$ vs BM25 ($p < 0.001$); Parity vs RepoMap ($p = 0.41$) |
| **Recall@5** | **0.3011** | 0.3185 | 0.1899 | 0.2292 | RepoMap leads slightly |
| **Recall@20** | **0.4279** | **0.6306** | 0.4452 | 0.4940 | **RepoMap leads substantially (+47.4%)** |
| **BCY@4k** | **0.2436** | 0.2024 | 0.1220 | 0.1488 | **RepoNeedle leads (+20.4% over RepoMap)** |
| **BCY@8k** | **0.3450** | **0.3788** | 0.2051 | 0.2650 | RepoMap leads (+9.8%) |
| **`code2test` MRR ($N=106$)** | **0.2660** | 0.1942 | 0.1057 | 0.0663 | **RepoNeedle leads (+37.0% over RepoMap, +151.7% over BM25)** |
| **`comment2context` MRR ($N=80$)**| **0.1708** | 0.1532 | **0.1974** | 0.1530 | **BM25 leads (-13.5% deficit for RepoNeedle)** |
| **`trace2code` MRR ($N=101$)** | **0.2337** | **0.2723** | 0.1638 | 0.2075 | RepoMap leads (-14.2% deficit for RepoNeedle) |
| **`edit2ripple` MRR ($N=58$)** | **0.2320** | **0.2323** | 0.1536 | 0.2428 | Parity between RepoNeedle and RepoMap |
| **Selective Abstention ($N=82$)** | **0 / 82 (0.0%)** | 0 / 82 (0.0%) | 0 / 82 (0.0%) | 0 / 82 (0.0%) | **Complete failure across all systems** |

---

## 3. Key Findings from the Failure Taxonomy

Detailed analysis across tasks and repositories in [`research/FAILURE_TAXONOMY.md`](file:///F:/RepoNeedle/research/FAILURE_TAXONOMY.md) revealed four actionable bottlenecks:

1. **Documentation Distractor Pollution in `comment2context`**:
   - In `etcd-io/etcd`, `Documentation/contributor-guide/triage_issues.md` was ranked rank 1, crowding out gold implementation code.
   - *Fix*: Introduce path-prior penalties for non-code documentation files during code search tasks.
2. **Inward Centrality Diffusion Deficit in `trace2code`**:
   - In `pallets/click`, `src/click/core.py` was ranked at rank 99 by RepoNeedle (MRR `0.0101`), while RepoMap placed it at rank 2 (MRR `0.5000`) because RepoMap's PageRank spreads probability from outer test frames to central hub implementations.
   - *Fix*: Implement fast multi-hop personalized PageRank inward graph diffusion.
3. **Distribution Collapse in Heuristic Selective Abstention**:
   - Minimum observed confidence on any no-gold query was `0.5321`, while the threshold was `0.38`. Real bug reports naturally contain repository vocabulary, and counterfactual queries contain ubiquitous coding terms.
   - *Fix*: Heuristics are scientifically inadequate. A dedicated cross-encoder classifier is mandatory for safe selective retrieval.
4. **Rust Macro Parsing Deficiencies**:
   - Multi-crate workspaces like `clap-rs/clap` and `astral-sh/ruff` failed because regex symbol extraction does not parse complex macro derives (`proc_macro_derive`).
   - *Fix*: Implement structured AST parsers or crate-manifest dependency resolvers.

---

## 4. Evaluation Sources & Leakage Control Framework

Detailed in [`research/EVALUATION_SOURCES_AND_LEAKAGE_CONTROLS.md`](file:///F:/RepoNeedle/research/EVALUATION_SOURCES_AND_LEAKAGE_CONTROLS.md):

1. **ARB v2 ($N=427$)**: Designated as development and regression benchmark.
2. **ContextBench ($N=1,136$, Apache 2.0)**: Process-oriented evaluation harness measuring intermediate Context Recall, Precision, and downstream agent patch success. Adapter designed to swap in RepoNeedle under fixed agent and LLM conditions.
3. **Independent Held-Out Benchmark ($N \ge 200$)**: 50+ fresh open-source repositories (Django, Black, Hugo, Fiber, Serde, Next.js, etc.) sampled at post-2024 commits, completely isolated from any development data.
4. **Fresh No-Gold Abstention Benchmark ($N \ge 180$)**: 4-tier realistic dataset covering upstream external bugs, sibling-repo counterfactuals, ambiguous positives, and exotic domains.
5. **Leakage Controls**: All cross-validation grouped strictly by repository; code and parameters frozen before running holdout evaluations.

---

## 5. Preregistered Scorecard & Decision Rules

Detailed in [`research/SCORECARD_AND_DECISION_RULES.md`](file:///F:/RepoNeedle/research/SCORECARD_AND_DECISION_RULES.md):
- **Primary Metrics**: MRR and BCY@8k (positive retrieval); Selective F1 (abstention); Pass@1 and token cost (downstream utility).
- **Decision Rules**:
  - Matched repository-clustered bootstrap ($B=10,000$ resamples) with $95\%$ CI strictly $> 0$.
  - Minimum relative gain $\ge +5.0\%$.
  - Maximum allowable regression on any secondary track $\le -10.0\%$.
  - Verification along the Pareto frontier (Accuracy vs Latency vs RAM).

---

## 6. Next Steps: Stage 2 Systematic Component Ablations

With Stage 1 complete and all foundational governance documents established, the research program transitions to **Stage 2**:
1. Pre-register Experiment IDs `EXP-001` through `EXP-006` in `research/EXPERIMENT_REGISTRY.jsonl`.
2. Execute systematic component ablations:
   - Ablation of `WorkflowRouter` (quantifying router value).
   - Ablation of `RepoGraph` (quantifying graph value across tasks).
   - Ablation of `SubwordSemantic` (testing if character $n$-grams help or hurt).
   - Factorial combination of router and graph interactions.
3. Evaluate the exact impact on MRR, Recall@20, and BCY@8k to inform Stage 3 architectural changes.
