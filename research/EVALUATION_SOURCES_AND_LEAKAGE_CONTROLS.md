# EVALUATION SOURCES, BENCHMARK HARNESSES, AND LEAKAGE CONTROLS

**Document ID**: `ESLC-2026-001`  
**Version**: 1.0.0  
**Date**: 2026-10-28  
**Author**: Principal Retrieval Researcher & Lead Systems Engineer  

---

## 1. Overview of Evaluation Sources

To avoid overfitting to a single benchmark and to ensure that improvements reflect genuine repository-retrieval capabilities, RepoNeedle establishes four complementary evaluation tiers:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      RepoNeedle Evaluation Ecosystem                    │
├──────────────────────────┬─────────────────────────────────────────────┤
│ 1. ARB v2 (Development)  │ 427 samples, 25 repos. Regression baseline. │
│ 2. ContextBench (Harness)│ 1,136 tasks, 66 repos. Agent-context audit. │
│ 3. Independent Holdout   │ Fresh repos & commits, zero-leakage split.  │
│ 4. Fresh No-Gold Suite   │ 4-tier realistic abstention benchmark.      │
└──────────────────────────┴─────────────────────────────────────────────┘
```

---

## 2. Source 1: Agent Retrieval Bench v2 (Development / Regression Baseline)

### Canonical Specifications:
- **Repository**: `eyuansu62/agent-retrieval-bench` (`eyuansu71/agent_retrieval_bench`)
- **Pinned Commit**: `9e4d68937f29d5967afd62f4f6a24c1478298133`
- **Evaluator Version**: `agent_retrieval_bench` v0.2.1
- **Total Samples**: $N=427$ ($345$ positive retrieval + $82$ selective abstention)
- **Repositories**: 25 open-source codebases (Gin, Tokio, Etcd, Transformers, Click, Vite, etc.)
- **Unique Snapshots**: 271 frozen repository states.
- **Candidate Pool**: Whole-repository candidate pools (all files in the frozen commit).

### Methodological Role:
ARB v2 has actively guided v0.1.0 development, router weight calibration, and bugfixes. Consequently, **ARB v2 is formally designated as the development and regression test suite**. It serves to verify that new changes do not break existing capabilities, but cannot serve as the sole evidence of generalized superiority.

---

## 3. Source 2: ContextBench (Agent-Process Evaluation Harness)

### Canonical Specifications:
- **Repository**: `EuniAI/ContextBench`
- **License**: Apache License 2.0 (Permissive open source)
- **Dataset**: `Contextbench/ContextBench` (Hugging Face)
- **Scope**: 1,136 real-world issue-resolution tasks across 66 repositories in 8 programming languages.
- **Ground Truth**: Human-annotated "gold contexts" mapped at file, block, and line granularities.

### Harness & Evaluation Protocol:
Unlike SWE-bench (which only evaluates whether a final patch passes unit tests, treating retrieval as a black box), ContextBench explicitly evaluates intermediate context retrieval:
1. **Context Recall**: Percentage of required gold code regions retrieved.
2. **Context Precision**: Ratio of useful code to irrelevant distractor code pulled into the prompt.
3. **Efficiency**: Step and token overhead incurred during context acquisition.

### Valid Integration Protocol for RepoNeedle:
To ensure fair scientific comparison without confounding retrieval quality with agent LLM capability:
- **Fixed Agent & LLM**: Keep the agent scaffold (e.g. SWE-agent or Agentless) and base model (e.g. Claude 3.5 Sonnet or GPT-4o) strictly fixed.
- **Controlled Retrieval Intervention**: Swap out default agent exploration tools (`grep`, `find`, `view_file`) with RepoNeedle context retrieval under identical token budgets (4k, 8k, 16k tokens).
- **Direct Retrieval Comparison**: Measure whether RepoNeedle's retrieved context improves downstream patch success rate while reducing agent exploration tool calls and token cost.

---

## 4. Source 3: Independent Held-Out Evaluation Suite

### Benchmark Objectives:
To measure true out-of-sample generalization, an independent benchmark collection is constructed adhering to strict isolation principles.

### Curated Target Specifications:
- **Repository Breadth**: Target $\ge 50$ distinct open-source repositories across multiple languages:
  - Python (Django, FastAPI, Pydantic, Celery, Black)
  - Go (Hugo, Kubernetes client-go, Fiber, Cobra)
  - Rust (Serde, Syn, Ripgrep, Hyper, Actix-web)
  - TypeScript / JavaScript (Next.js, Jest, Express, Prettier)
  - Java (Spring Framework, Micronaut, Guava)
  - C / C++ (Redis, SQLite, CMake)
- **Temporal & Version Splitting**: Repositories must be sampled at commits chronologically separated from any training or tuning data.
- **Task Typology**: Replicate the four practical agent retrieval workflows:
  1. `trace2code` (Exception trace to implementation)
  2. `code2test` (Implementation change to regression test)
  3. `edit2ripple` (API change to downstream callers)
  4. `comment2context` (Issue comment to target module)

### Data Quarantine & Licensing Protocol:
- Only permissively licensed repositories (MIT, Apache-2.0, BSD, ISC) may be included.
- **Strict Quarantine of Restricted Data**: Datasets with non-commercial or share-alike clauses (e.g. CORE-Bench CC BY-NC-SA 4.0) must never be incorporated into the open-source distribution or benchmark package.

---

## 5. Source 4: Fresh No-Gold Abstention Benchmark

### Why Existing Benchmarks Failed:
As demonstrated by the 0/82 failure on ARB v2, simple heuristic abstention fails on real repositories because:
1. Natural issue queries filed against a repo inherently contain real repo vocabulary.
2. Counterfactual queries contain standard programming terms that trigger false-positive matches.

### Four-Tier Typology for Realistic Abstention Evaluation:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Fresh No-Gold Evaluation Typology                    │
├────────────────────────────────┬───────────────────────────────────────┤
│ Tier 1: External Bug Negatives │ Bug resides in third-party dependency │
│ Tier 2: Real Wrong-Repo Tasks  │ Plausible task from a sibling repo    │
│ Tier 3: Hard Ambiguous Positives│ Tricky queries that DO have gold code │
│ Tier 4: Unfamiliar Domain Repos│ Exotic frameworks and languages       │
└────────────────────────────────┴───────────────────────────────────────┘
```

1. **Tier 1: External Bug Negatives ($N \ge 50$)**:
   - Queries based on real issues where the root cause was verified to be in an upstream library, Python runtime bug, or external service failure.
   - The query text naturally contains the target repository's class and module names, but the fix required no changes within the repository.
2. **Tier 2: Real Wrong-Repo Cross-Evaluation ($N \ge 50$)**:
   - Issues sampled from closely related projects in the same ecosystem (e.g. submitting a Flask issue to Django, or a Tokio issue to Mio).
   - Both share similar terminology (`Request`, `Socket`, `Handler`), preventing trivial lexical mismatch detection.
3. **Tier 3: Hard Ambiguous Positives ($N \ge 50$)**:
   - Legitimate solvable tasks that use ambiguous phrasing or high-level questions.
   - Essential for measuring **False Abstention Rate** (ensuring the retriever does not become overly cowardly).
4. **Tier 4: Unfamiliar Domain & Language Negatives ($N \ge 30$)**:
   - Verifies whether abstention calibration holds across diverse programming languages and domains without manual re-tuning.

---

## 6. Strict Data Leakage Controls

To maintain uncompromising scientific integrity throughout the research program:

1. **Repository-Grouped Splits**:
   - In any cross-validation or parameter tuning, **data must be grouped by repository**.
   - No repository snapshot or query from repository $R$ may appear in both the training/tuning set and the validation set.
2. **Code & Configuration Freeze**:
   - Before executing an evaluation on the independent held-out set or fresh no-gold set, the codebase, routing heuristics, scoring formulas, neural weights, and thresholds must be committed and tagged in Git.
3. **Zero Contamination Verification**:
   - An automated script will verify that no held-out task IDs, repository names, or commit hashes appear in the training corpora or prompt routing caches.
4. **Historical Immutability**:
   - Once a held-out benchmark is evaluated, its results are permanently logged in the experiment registry. If results are unsatisfactory, the benchmark cannot be reused as a "fresh" test set for subsequent iterations.

