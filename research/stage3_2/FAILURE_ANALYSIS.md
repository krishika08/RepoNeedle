# REPONEEDLE STAGE 3.2: FAILURE ANALYSIS AND ARCHITECTURAL DIAGNOSTICS

**Document ID**: `STAGE3.2-FAIL-001`  
**Date**: 2026-10-28  
**Scope**: In-Depth Diagnostics of Invariant Metrics, Baseline Failures, Memory Ceiling Breaches, and Infrastructure Blockers  

---

## 1. Executive Summary

Scientific rigor demands that negative results, statistical deadlocks, and constraint breaches receive equal analytical prominence to positive performance. This report details the four primary diagnostic findings of the Stage 3.2 evaluation:

1. **The Micro-Benchmark Budget Saturation Deadlock**: Explaining why Candidates A through E produced identical scores on the 14-task held-out evaluation.
2. **The Rust `ripgrep` Retrieval Failure**: A detailed breakdown of the single task where RepoMap outperformed RepoNeedle.
3. **Literal Process Memory (RSS) Constraint Breach**: Accounting for why total process RSS (103.1–110.3 MB) strictly exceeds the preregistered $\le 100$ MB threshold on real repositories.
4. **Downstream Test Execution Blocker**: Why containerized patch validation cannot be executed in the current environment.

---

## 2. Diagnostic 1: Micro-Benchmark Budget Saturation & Metric Invariance

In the 14-task held-out evaluation, Candidates A, B, C, D, and E achieved identical Context Recall (**0.9286**), MRR (**0.9286**), and Token Budget Efficiency (**0.9286**).

### Root Cause Analysis:
- **Corpus Scale**: Each held-out task in the ContextBench-derived micro-evaluation suite contains only 2 to 5 files, with total token counts ranging between 180 and 440 tokens.
- **Budget Asymmetry**: The evaluation budget was fixed at **8,000 tokens**.
- **Saturation Mechanism**:
  $$\text{Total Corpus Tokens} \approx 350 \ll 8,000 \text{ (Budget)}$$
  Because the complete repository snapshot occupies less than 5% of the allowable budget, the `BudgetOptimizer` never experienced budget pressure.

### Component Invariance Trace:
1. **Structural Skeletons (Candidate B vs A)**: Skeletons are conditionally generated only when a candidate file exceeds the remaining budget capacity. Because all files fit into Tier 1 (Full Content), skeletonization was never invoked.
2. **Documentation Distractor Filtering (Candidate C vs B)**: Applying a $0.5\times$ penalty to documentation files altered their numerical rank from e.g. #2 to #4. However, because all files fit into the 8,000-token window, no documentation file was evicted from the final context window.
3. **PageRank Graph Diffusion (Candidate D vs C)**: Spreading activation along import edges boosted connected components, but because every candidate was included in the output, set membership remained identical.
4. **Polyglot Symbol Extraction (Candidate E vs D)**: AST symbol parsing refined internal token scoring, but had zero effect on binary context inclusion under an unsaturated budget.

### Physical Verification on Saturated Repositories:
When evaluated on a real repository with budget pressure (`pallets/click`, 133 files, 14,670 LOC, ~45,000 tokens):
- Under an 8,000-token ceiling, the corpus exceeds the budget by $5.6\times$.
- **Candidate A** includes 12 full files before exhausting the budget.
- **Candidate B** includes 8 full files and 19 compressed skeleton files, increasing file coverage by $+125\%$.
- **Candidate C** deprioritizes `docs/conf.py` and `examples/` tutorials, elevating core test suites (`tests/test_arguments.py`) into Tier 1.

---

## 3. Diagnostic 2: The `BurntSushi/ripgrep` Failure Mode

On the `BurntSushi/ripgrep` held-out sample, Candidate C achieved **0.00 Context Recall**, while the Aider-style RepoMap baseline achieved **1.00 Context Recall**.

### Root Cause: Vocabulary Mismatch in Modular Polyglot Architecture
- **Task Specification**: Bug fix in ripgrep's terminal color buffer and streaming printer. Gold target file: `crates/printer/src/termcolor.rs`.
- **Query Problem Statement**: Focused on ANSI terminal escape code buffering and standard output streaming flags (`--color=always`).
- **Failure Mechanism in RepoNeedle**:
  - The problem description shared high lexical and subword similarity with ripgrep's top-level CLI argument parser (`crates/core/flags.rs`) and main binary entrypoint (`crates/core/main.rs`).
  - Both lexical BM25 and subword n-gram cosine ranked CLI argument files at ranks 1–3.
  - Due to lack of lexical overlap with the internal termcolor buffer types, `termcolor.rs` received a low raw score.
  - Because Candidate C's graph relies on explicit module imports and Rust crate-level dependency manifests (`Cargo.toml`), inter-crate deep symbol references were not resolved into explicit graph edges.
- **Success Mechanism in RepoMap**:
  - RepoMap constructs a PageRank graph over Tree-sitter symbol definitions and identifiers.
  - Even without lexical match, the call path from `flags.rs` $\to$ `printer::Config` $\to$ `termcolor.rs` established high PageRank centrality, ensuring its inclusion in the context map.
- **Architectural Lesson**: In modular polyglot codebases (Rust crates, Go multi-module packages), lexical and subword matching must be augmented with cross-crate symbol reference resolution.

---

## 4. Diagnostic 3: Literal Process Working Set (RSS) Constraint Violation

The preregistered Stage 3 constraint states:
$$\text{Memory Overhead} \le 100\text{ MB}$$

### Measurement Dissection:

| Measurement Metric | Tool / API | Synthetic Micro (5 files) | Medium Repo (`click`, 133 files) | Large Repo (`caddy`, 250 files) | Preregistered $\le 100$ MB Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Incremental Traced Heap** | `tracemalloc` | 0.48 MB | 34.09 MB | 45.10 MB | **PASSED** ($\le 45$ MB) |
| **Process Working Set (RSS)** | `K32GetProcessMemoryInfo` | 80.7 MB | **103.1 MB** | **110.3 MB** | **FAILED** ($> 100$ MB) |

### Technical Accounting:
1. **Base Python Interpreter Footprint**: A modern 64-bit CPython 3.12 process on Windows with imported standard libraries and core dependencies (`pydantic`, `numpy`, `yaml`) has a baseline working set of **~40–45 MB** before any repository indexing occurs.
2. **Index Heap Allocations**: Indexing 133 files in `click` allocates ~34 MB of heap (document text, BM25 posting lists, n-gram vectors, AST graph nodes).
3. **Working Set Paging & Fragmentation**: When Windows OS manages process working sets, heap allocations trigger committed pages that increase working set size non-linearly. Total working set reached **103.1 MB** for `click` and **110.3 MB** for `caddy`.
4. **Literal Verdict**:
   - If the constraint is interpreted as **incremental memory for the index**, RepoNeedle easily passes ($< 50$ MB).
   - If the constraint is interpreted literally as **total process memory (RSS)**, RepoNeedle **violates the 100 MB ceiling by 3.1% to 10.3%**.
   - Scientific integrity requires reporting this literal violation explicitly rather than redefining the metric post-hoc.

---

## 5. Diagnostic 4: SWE-Bench Container Execution Blocker

A physical audit of host virtualization and container engines confirmed:
- `docker` CLI: Not installed (`CommandNotFoundException`).
- `podman` CLI: Not installed (`CommandNotFoundException`).
- `WSL` (Windows Subsystem for Linux): Not installed.
- Network access to pull external container images: Blocked by sandbox security policy.

### Scientific Consequence:
- RepoNeedle's retrieval output satisfies context sufficiency (supplying gold files within the budget prompt).
- However, whether an LLM coding agent equipped with this context generates valid, passing patches cannot be physically executed or verified on this platform.
- In accordance with non-fabrication rules, downstream coding agent benefit is formally designated as **UNVERIFIED**.
