# EXPERIMENTAL ROADMAP: STAGED RESEARCH EXECUTION PLAN

**Document ID**: `ER-2026-001`  
**Version**: 1.0.0  
**Date**: 2026-10-28  
**Author**: Principal Retrieval Researcher & Lead Systems Engineer  

---

## 1. Roadmap Architecture

The research program executes in four controlled, sequential stages. Broad tuning is forbidden until diagnostic evidence, leakage controls, and baseline baselines are fully established.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Four-Stage Research Roadmap                       │
├────────────────────────────────────────────────────────────────────────┤
│ STAGE 1: Error Profiling & Diagnostics        [COMPLETED]              │
│ STAGE 2: Systematic Component Ablations       [READY FOR EXECUTION]    │
│ STAGE 3: Targeted Architectural Innovations   [DESIGNED & STAGED]      │
│ STAGE 4: Frozen Independent Evaluation        [RESERVED TEST GATE]     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Stage 1: Diagnostic Error Profiling (Status: COMPLETED)

- [x] Baseline values audited from raw prediction files on disk.
- [x] Empirical analysis of the 197 RepoMap regressions and 179 BM25 regressions completed.
- [x] Detailed failure taxonomy published in [`research/FAILURE_TAXONOMY.md`](file:///F:/RepoNeedle/research/FAILURE_TAXONOMY.md).
- [x] Root causes pinpointed:
  1. *Documentation Distractor Pollution* in `comment2context` (causing BM25 to outperform RepoNeedle).
  2. *Centrality Graph Diffusion Deficit* in `trace2code` (causing RepoMap to beat RepoNeedle on tail recall).
  3. *Vocabulary & Z-Score Distribution Collapse* in selective abstention (causing 0/82 accuracy).
  4. *Multi-Crate Rust AST Deficiencies* in `clap-rs/clap` and `astral-sh/ruff`.

---

## 3. Stage 2: Systematic Component Ablation Matrix (Status: READY FOR EXECUTION)

To isolate the exact marginal contribution and cross-component interactions of each sub-system, a full factorial ablation is conducted on the development benchmark ($N=345$ positive samples):

| Exp ID | Configuration / Ablation | Hypothesis | Target Question |
| :-: | :--- | :--- | :--- |
| **EXP-001** | `Full RepoNeedle (v0.1.0 Baseline)` | Anchor baseline | Reference point |
| **EXP-002** | `w/o WorkflowRouter` | Static uniform weights | Does task-adaptive routing justify its complexity? |
| **EXP-003** | `w/o RepoGraph` | Pure Lexical + Semantic | What is the exact contribution of the AST graph outside `code2test`? |
| **EXP-004** | `w/o SubwordSemantic` | Pure BM25 + AST Graph | Does the character $n$-gram index help or introduce noise? |
| **EXP-005** | `w/o Structural Skeletons` | Full-file packing only | What is the exact token-compression yield benefit under 4k/8k budgets? |
| **EXP-006** | `w/o Inverted Test Linkage` | Standard PageRank only | Is explicit test-to-target mapping the sole driver of `code2test` performance? |

---

## 4. Stage 3: Targeted Architectural Innovations (Status: DESIGNED)

Guided directly by Stage 1 failure evidence, Stage 3 develops and evaluates targeted interventions:

### Track A Innovations (CPU Native / Practical):
1. **Experiment 3A.1: Content-Type & Path Prior Gating (Doc Filter)**:
   - *Hypothesis*: Penalizing non-code documentation files (`docs/`, `.rst`, `.md`, `.txt`) during code tasks will eliminate distractor pollution and restore RepoNeedle superiority over BM25 in `comment2context`.
   - *Target*: Reverse the $-13.5\%$ MRR deficit on `comment2context`.
2. **Experiment 3A.2: Fast Personalized PageRank Inward Diffusion**:
   - *Hypothesis*: Adding 2-hop inward graph diffusion from matched frame identifiers to core classes will close the gap with RepoMap on `trace2code` without heavy GPU dependencies.
   - *Target*: Increase Recall@20 from `0.4092` toward RepoMap's `0.8465` on `trace2code`.
3. **Experiment 3A.3: Calibrated Cross-Distribution Score Normalization**:
   - *Hypothesis*: Normalizing BM25 and graph scores with min-max sigmoid or reciprocal rank fusion (RRF) before summation prevents BM25 score magnitude from drowning out topological signals in large repositories.

### Track B Innovations (High-Compute / Neural / Maximum Quality):
1. **Experiment 3B.1: Learned Neural Discriminator for Selective Abstention**:
   - *Hypothesis*: A fine-tuned cross-encoder classifier operating on query and top retrieved snippets will discriminate real repository bugs from out-of-scope/dependency issues, solving the 0/82 failure mode.
   - *Target*: Achieve $\ge 85\%$ accuracy on the 4-tier no-gold benchmark.
2. **Experiment 3B.2: Dense Code Bi-Encoder Integration (Qwen3-Embedding / Jina-Code)**:
   - *Hypothesis*: Combining dense code vector representations with RepoNeedle's AST graph will outperform both standalone neural models and standalone graph retrievers.
   - *Target*: Exceed `Qwen3-Embedding-4B` MRR (`0.2379`) on ARB v2.
3. **Experiment 3B.3: ContextBench End-to-End Agent Verification**:
   - *Hypothesis*: High BCY@4k and BCY@8k context yields will translate to a higher Pass@1 rate in SWE-agent with lower token consumption compared to standard agent exploration.

---

## 5. Stage 4: Frozen Independent Evaluation (Status: RESERVED)

1. **Candidate Freeze**:
   - Select the single best Track A candidate and the single best Track B candidate based strictly on Stage 2 and Stage 3 development data.
   - Freeze all code, weights, prompt templates, and decision thresholds.
2. **Untouched Evaluation**:
   - Run the frozen candidates on the independent held-out repository benchmark ($N \ge 200$ samples across $\ge 50$ repositories).
   - Run the frozen candidates on the fresh 4-tier no-gold abstention benchmark.
3. **Formal Verification**:
   - Compute repository-clustered bootstrap confidence intervals.
   - Check against all pre-declared decision rules.
   - Publish complete, unhedged results.
