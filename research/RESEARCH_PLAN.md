# REPONEEDLE RESEARCH PROGRAM: COMPREHENSIVE RESEARCH PLAN

**Document ID**: `RP-2026-001`  
**Version**: 1.0.0  
**Date**: 2026-10-28  
**Author**: Principal Retrieval Researcher & Lead Systems Engineer  
**Status**: ACTIVE — PREREGISTERED  

---

## 1. Executive Mission & Philosophical Principles

RepoNeedle is an open-source repository-context retrieval system designed to equip autonomous AI coding agents (such as Claude Code, SWE-agent, OpenHands, Cline, Aider) with the exact code, tests, and structural definitions required to solve software engineering tasks under strict context-token budgets.

### Scientific Principles:
1. **Empirical Primacy**: No architectural design or model choice is presumed optimal without matched empirical evidence.
2. **Skepticism Toward Scale**: Larger neural foundation models are not assumed to be automatically superior. Speed, context density, structural fidelity, and predictability are co-equal first-class metrics.
3. **Strict Separation of Development and Test**: Benchmarks used to guide architectural choices (such as ARB v2) are classified as development/regression benchmarks. Final scientific claims require validation against untouched, independent held-out corpora.
4. **No Synthetic Shortcuts**: Selective abstention and error retrieval must be evaluated on natural, realistic tasks rather than trivial vocabulary-mismatched negatives.
5. **Reproducibility**: All experiments must be recorded with exact commit hashes, data splits, seeds, candidate pools, raw sample predictions, and resource profiles.

---

## 2. Product Objectives: Dual-Track Architecture

To prevent conflicting design constraints from crippling either deployment agility or peak retrieval quality, RepoNeedle establishes two distinct, concurrent research tracks:

```
                          ┌───────────────────────────────┐
                          │    RepoNeedle Research Core   │
                          │   Shared Protocol & Models    │
                          └──────────────┬────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
   ┌───────────────────────────┐                   ┌───────────────────────────┐
   │ Track A: BEST PRACTICAL   │                   │ Track B: MAXIMUM QUALITY  │
   │      (Production/CPU)     │                   │     (Server/Agentic RAG)  │
   ├───────────────────────────┤                   ├───────────────────────────┤
   │ • Commodity CPU native    │                   │ • Dense code embeddings   │
   │ • Zero heavy dependencies │                   │ • Cross-encoder rerankers │
   │ • Sub-200ms query latency │                   │ • Learned task routers    │
   │ • Minimal RAM (<100MB)    │                   │ • Deep graph diffusion    │
   │ • Offline / CLI / Local   │                   │ • Learned abstention      │
   │ • Instant cold-start      │                   │ • Server / GPU cluster    │
   └───────────────────────────┘                   └───────────────────────────┘
```

### Track A: The Best Practical System (Production / CPU / Local)
- **Target Use Case**: Local IDE extensions, developer CLI tools, edge agent loops, fast automated test selection.
- **Constraints**:
  - Pure Python + NumPy / SciPy / NetworkX (zero PyTorch, zero CUDA, zero remote network calls).
  - Sub-200ms median query latency on repositories up to 5,000 files.
  - One-time indexing time under 10 seconds per repository snapshot.
  - Deterministic execution across all major platforms (Linux, macOS, Windows).
- **Core Optimization Vectors**:
  - Optimized inverted index scans and sparse BM25 scoring.
  - Fast AST symbol extraction and static call/import graphs.
  - Heuristic test-to-target linkage and naming-convention indices.
  - Greedy knapsack context packing with structural skeleton compression.

### Track B: The Maximum-Quality System (High-Compute / Agentic RAG)
- **Target Use Case**: High-value autonomous software engineering agents, server-side CI/CD agents, complex architectural bug localization.
- **Capabilities & Scope**:
  - State-of-the-art code embedding models (e.g. Qwen3-Embedding-0.6B/4B/8B, voyage-code-3, jina-embeddings-v2-code).
  - Cross-encoder reranking models for top candidate refinement.
  - Learned workflow routing and dynamic score fusion.
  - Multi-hop graph diffusion for deep recall expansion.
  - Calibrated neural discriminators for safe selective abstention.
- **Constraints**:
  - Evaluated on equivalent frozen candidate sets with full resource accounting (FLOPs, latency, VRAM, API cost).

---

## 3. Preregistered Evaluation Scorecard

To ensure scientific rigor, metrics and decision criteria are preregistered before running new tuning experiments.

### A. Primary Diagnostic Metrics
1. **Mean Reciprocal Rank (MRR)**: Measures top-rank precision for the first relevant file.
2. **Recall@5, Recall@10, Recall@20**: Measures candidate pool coverage at standard retrieval depths.
3. **Budgeted Context Yield (BCY@4k, BCY@8k, BCY@16k)**: Measures the proportion of relevant files (and lines) successfully packed into the prompt under hard token constraints, penalizing wasted context.

### B. Selective Retrieval Metrics
1. **Selective Abstention Accuracy**: Proportion of no-gold queries correctly identified.
2. **False Return Rate**: Proportion of no-gold queries where the system hallucinates irrelevant files.
3. **False Abstention Rate**: Proportion of solvable positive queries incorrectly rejected.
4. **Risk-Coverage Curve**: Precision as a function of coverage when threshold is varied.

### C. Downstream Agent Task Utility (The Ultimate Practical Objective)
1. **Resolved Task Rate (Pass@1)**: End-to-end bug resolution rate with fixed agent scaffolding (e.g. SWE-agent or mini-agent harness) using retrieved context.
2. **Context Token Cost**: Total input tokens consumed by the agent during task execution.
3. **Exploration Steps / Tool Calls**: Number of additional file inspection calls the agent was forced to make due to missing context.

### D. Systems & Efficiency Metrics
1. **Index Build Time**: Seconds to parse and index a frozen repository snapshot.
2. **Query Latency Distribution**: Mean, median ($p_{50}$), $p_{95}$, and $p_{99}$ latency over 100+ warmed queries.
3. **Index Storage Footprint**: Disk and resident memory (RAM) usage per indexed codebase.

---

## 4. Predeclared Decision Rules

A new system candidate $C$ is deemed a **genuine empirical improvement** over baseline $B$ if and only if:

1. **Statistical Significance**: $\Delta_{\text{MRR}}(C - B) > 0$ with $p < 0.05$ under a matched, repository-clustered bootstrap test ($B = 10,000$ resamples).
2. **Non-Trivial Effect Size**: Mean relative improvement on primary metric $\ge +5.0\%$ on the target track.
3. **Bounded Secondary Regression**: No essential secondary track or task category degrades by more than $-10.0\%$ without explicit pre-declared justification.
4. **Generalization to Independent Holdouts**: Gains observed on development benchmarks (ARB v2) must replicate on the independent held-out evaluation suite ($N \ge 200$ samples).
5. **Cost & Latency Bounding**:
   - For Track A: Query latency $p_{95} \le 500\text{ ms}$, RAM $\le 250\text{ MB}$.
   - For Track B: Latency and VRAM must be reported, and the candidate must reside on the empirical Pareto frontier.
