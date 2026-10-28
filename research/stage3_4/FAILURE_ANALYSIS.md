# REPONEEDLE STAGE 3.4: TECHNICAL WEAKNESSES AND ARCHITECTURAL FAILURE ANALYSIS

**Document ID**: `STAGE3.4-FAIL-001`  
**Date**: 2026-10-28  
**Scope**: In-Depth Controlled Diagnostics of Documentation Filtering, Polyglot Dependency Graphs, Budget Saturation, and Memory Ceilings  

---

## 1. Executive Summary

This report analyzes the four core architectural bottlenecks identified during Stage 3 full-corpus research:
1. **Documentation Filtering Trade-offs**: Balancing distractor removal against the risk of suppressing genuinely useful documentation.
2. **Cross-File and Inter-Crate Dependency Gaps**: Structural graph limitations on decoupled Rust workspaces (`BurntSushi/ripgrep`).
3. **Skeleton Compression Dynamics Under Budget Saturation**: Empirical verification of how skeletons rescue recall under genuine token constraints.
4. **Process Working Set (RSS) vs Heap Discrepancy**: Accounting for why total process memory exceeds the literal 100 MB ceiling on real codebases.

---

## 2. Weakness 1: Documentation Distractor Filtering vs Useful Documentation

### The Fundamental Tension:
In repository context retrieval, documentation files (`.rst`, `.md`, `/docs/`, `/examples/`) exhibit dual character:
- **Distractor Mode**: On bug-fixing tasks (`trace2code`, `code2test`), tutorial and walkthrough documentation frequently shares high lexical overlap with query keywords (e.g. CLI argument flags, error messages) and crowds out the core source code files that actually contain the bug.
- **Signal Mode**: On API specification or configuration tasks (`comment2context`), documentation files define the canonical behavioral contracts and are the direct target of the query.

### Controlled Empirical Comparison on ARB v2 ($N=345$):

| Configuration | Penalty Factor | `comment2context` MRR | `code2test` MRR | `trace2code` MRR | Overall Benchmark MRR | Distractor Reduction |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **No Filter (Candidate B)** | $1.0\times$ | 0.1868 | 0.0760 | 0.2608 | 0.1842 | 0.0% |
| **Mild Filter (Candidate C)** | $0.5\times$ | **0.2036** | **0.1073** | **0.2787** | **0.2040** | **-71.4%** |
| **Aggressive Filter** | $0.2\times$ | 0.1912 | 0.1073 | 0.2787 | 0.2015 | -88.5% |

### Key Diagnostic Findings:
1. **Mild Penalty ($0.5\times$) Is Optimal**: Downweighting doc files by $0.5\times$ allows core code files with moderate match scores to rise above verbose documentation without completely evicting documentation when it is the primary target.
2. **Aggressive Penalty ($0.2\times$) Causes False Exclusions**: On queries explicitly querying API usage contracts, an aggressive $0.2\times$ penalty suppresses gold documentation files below the top-20 boundary, reducing `comment2context` MRR from 0.2036 to 0.1912.
3. **Intent-Conditioned Filtering**: Filtering should remain mild ($0.5\times$) or be selectively modulated based on query intent (suppressing docs only when query contains stack traces or unit test assertions).

---

## 3. Weakness 2: Inter-Crate Graph Gaps in Modular Polyglot Repositories

### The `BurntSushi/ripgrep` Retrieval Failure Case:
In the held-out evaluation on `BurntSushi/ripgrep`, Candidate C achieved **0.00 Context Recall**, while RepoMap achieved **1.00 Context Recall**.

### Root Cause Analysis:
1. **Workspace Decoupling**: Ripgrep is partitioned into modular Rust crates:
   - `crates/core`: Front-end CLI parser, flag handling, and process dispatch.
   - `crates/printer`: Output formatting and color terminal rendering (`termcolor.rs`).
   - `crates/searcher`: Search algorithms.
2. **Vocabulary Mismatch**:
   - The query described terminal escape sequence buffering (`--color=always`).
   - Lexical BM25 and subword n-grams matched heavily with CLI argument parsing definitions in `crates/core/flags.rs` and `crates/core/main.rs`.
   - The gold bug-fix target was `crates/printer/src/termcolor.rs`, which had zero lexical overlap with CLI flag names.
3. **Graph Resolution Failure**:
   - RepoNeedle's dependency graph resolved file-relative module imports (`mod termcolor;`), but did not parse inter-crate workspace dependency manifests (`Cargo.toml`).
   - Consequently, the dependency link from `core` $\to$ `printer` was missing in the graph, preventing PageRank diffusion from propagating score from CLI flags to `termcolor.rs`.
4. **How RepoMap Succeeded**:
   - RepoMap builds an AST call graph using Tree-sitter, connecting function call sites directly to their symbol definitions across crate boundaries.
5. **Architectural Recommendation**: For Rust workspaces and Go multi-module repositories, RepoNeedle's graph must parse `Cargo.toml` and `go.mod` dependency manifests to link inter-crate packages.

---

## 4. Weakness 3: Skeleton Compression Under Saturated Context Budgets

### The Mechanism of Action Under Genuine Saturation:
On tiny micro-corpora (<450 tokens), skeleton compression never activated because all candidate files fit into the 8,000-token budget in full content.

On real repositories (`pallets/click`, 133 files, 108,257 tokens, $13.5\times$ over budget), budget saturation forces hard context trade-offs:

| Candidate Configuration | Files Packed | Full Files | Skeleton Files | Doc Files | Tokens Used | Recall@8k | Key Diagnostic Finding |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **CAND-A (Full Files Only)** | 9 | 9 | 0 | 7 | 7,970 | 0.0000 | 7 documentation files fill budget; gold target evicted! |
| **CAND-B (With Skeletons)** | 11 | 6 | 5 | 5 | 7,971 | **0.5000** | **Compressing 5 files saves >4,000 tokens**, admitting gold target! |
| **CAND-C (B + Doc Filter)** | 8 | 7 | 1 | **2** | 7,970 | **0.5000** | Doc distractors drop from 5 to 2, raising precision from 0.09 to 0.125. |

### ARB v2 Full Corpus Validation ($N=345$):
- Across all 345 positive ARB v2 queries on full repository snapshots, skeleton compression (`EXP-003`) boosted BCY@8k from **0.2261** (`EXP-004`) to **0.2804**, representing a **+24.0% relative gain in budgeted token yield** ($t=3.765, p=0.0002$).
- Skeletons preserve class/method signatures and type annotations while trimming implementation bodies, allowing an average of $+65\%$ more relevant files to fit within the prompt window.

---

## 5. Weakness 4: Process Working Set (RSS) vs Incremental Heap

The preregistered Stage 3 constraint states:
$$\text{Memory Overhead} \le 100\text{ MB}$$

### Multi-Scale Empirical Profiling:

| Repository Scale | Files | Lines of Code | Traced Python Heap | Process Working Set (RSS) | Literal $\le 100$ MB Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Synthetic Micro (`django`)** | 5 | 70 | 0.48 MB | 80.7 MB | **PASSED** |
| **Medium Repo (`pallets/click`)** | 133 | 14,670 | 34.09 MB | **103.1 MB** | **FAILED (by 3.1 MB)** |
| **Large Repo (`caddyserver/caddy`)** | 250 | 22,995 | 45.10 MB | **110.3 MB** | **FAILED (by 10.3 MB)** |

### Accounting Breakdown:
1. **Base Runtime Overhead**: On 64-bit Windows, CPython 3.12 with imported packages (`pydantic`, `numpy`, `yaml`) has a baseline working set of **~40–45 MB** before any repository is indexed.
2. **Index Heap Footprint**: The actual in-memory inverted index, subword vector table, and AST graph require only **1.5 to 5.2 MB** of heap above base data structures.
3. **OS Paging & Fragmentation**: Windows memory manager commits memory in 4KB/64KB pages; heap allocation churn during tokenization expands the working set beyond the raw Python heap.
4. **Scientific Honesty**: If the constraint is interpreted literally as **Total Process Memory**, RepoNeedle violates the 100 MB ceiling on medium/large repositories. This violation is documented explicitly without redefining the metric.
