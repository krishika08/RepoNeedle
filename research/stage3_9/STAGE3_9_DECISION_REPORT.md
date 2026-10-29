# RepoNeedle Stage 3.9: Canonical Decision Report & Architecture Governance

**Document ID**: `STAGE3.9-DEC-CANONICAL`  
**Date**: October 2026  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**Starting Commit**: `174c26048e31fff73d780f0528797485e352b860` (Stage 3.8 HEAD)  
**Historical Commit Reconciled**: `4f78cc3` (Stage 3.5 HEAD)  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`) — **VERIFIED UNCHANGED**  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`) — **VERIFIED UNCHANGED**  
**Gate A Verdict**: **`PASS — METRICS RECONCILED`**  
**Gate B Status**: **`AUTHORIZED AND COMPLETED`**  
**Independent Evaluation Gate**: **`BLOCKED — DATA ACCESS`** (ContextBench official dataset blocked by sandbox network boundary; ARB v2 treated strictly as development benchmark)  
**Authoritative Architectural Recommendation**: **`REVISE AND ADVANCE TO STAGE 3.10`** (Adoption of Cascaded Lexical-First Architecture)

---

## 1. Executive Summary & Authoritative Verdicts

RepoNeedle Stage 3.9 was conducted under a strict two-gate experimental protocol designed to reconcile conflicting historical claims, restore empirical reproducibility, and evaluate a principled ranking-recovery architecture.

1. **Gate A (Provenance & Metric Reconciliation)**: Reconciled the historical discrepancy between Stage 3.5 ($MRR = 0.2152$) and Stage 3.8 ($MRR = 0.1351$). Established that Stage 3.5's apparent win was caused by evaluating against restricted candidate pools (`tests_only` filter on `code2test`), ripgrep string-lookup bypasses in `graph.py`, mislabeling binary Hit@20 ($0.4928$) as Recall@20, and hardcoding a static paper constant ($0.2140$) for RepoMap. Stage 3.8's full unconstrained corpus evaluation ($MRR = 0.1351$, RepoMap $MRR = 0.2293$) is confirmed as the sole ground truth. **Gate A Verdict: `PASS — METRICS RECONCILED`.**
2. **Gate B (Cascaded Lexical-First Architecture)**: Implemented `CascadedRanker` in `reponeedle/core/cascade.py`. By freezing BM25's top-3 ranks ($0, 1, 2$) in exact relative order, the architecture completely prevents the 70 catastrophic early-rank demotions (`BM25_WIN_CAND_DEMOTED`) suffered by Candidate F. Applying degree-normalized graph expansion ($1/\sqrt{d_{\text{out}} \cdot d_{\text{in}}}$), package boundary fencing, and test discovery heuristics strictly to eligible ranks ($\ge 4$) expands deep recall while preserving early-rank precision.
3. **Verified Empirical Results ($N=345$ positive instances, $K=25$ repos)**:
   - `CAND-CASCADE` achieves **MRR = 0.1883** (+39.4% relative recovery over Candidate F's $0.1351$, and +7.5% over BM25's $0.1752$), **Recall@20 = 0.5518** (+21.7% over BM25), and **Hit@20 = 0.6348**.
   - Outperforms pinned RepoMap on **`comment2context`** ($0.1669 > 0.1590$) and **`edit2ripple`** ($0.2519 > 0.2344$), as well as across all **Go** repositories ($0.2865 > 0.2850$).
   - Achieves a median query latency of **$8.12\text{ ms}$**, which is **$22.2\times$ faster** than pinned RepoMap ($180.20\text{ ms}$).
4. **Engineering Rigor**: 126/126 regression tests passing in 5.5s (including 9 focused invariant tests in `tests/test_stage3_9_cascade.py`). Both frozen tags remained 100% immutable throughout the research programme.

---

## 2. Gate A: Provenance and Metric Discrepancy Reconciliation

### 2.1 Git Lineage and Environment Provenance
- Verified via `git merge-base --is-ancestor 4f78cc3 174c260` that Stage 3.5 commit `4f78cc3` is a direct linear ancestor of Stage 3.8 commit `174c260`.
- Environment: Python 3.12.10 (win32), NumPy 2.2.6, SciPy 1.15.2, NetworkX 3.4.2, pytest 9.1.1.
- Evaluated across all 345 positive ARB v2 instances across 25 repositories and 218 snapshots.

### 2.2 Forensic Explanation of Metric Divergence

| System | Stage 3.5 MRR | Stage 3.8 Full MRR | Stage 3.5 Recall@20 | Stage 3.8 Recall@20 | Root Cause of Divergence |
|---|---:|---:|---:|---:|---|
| **BASE-BM25** | 0.1705 | 0.1735 | 0.4928 | 0.4549 | Stage 3.5 reported binary Hit@20 ($170/345 = 0.4928$) mislabeled as recall; evaluated Stage 2 chunk lookups (`EXP-016`). Stage 3.8 evaluated live full files, yielding true fractional $Recall@20 = 0.4549$ and full-rank $MRR = 0.1735$ ($0.1649$ with rank-20 cutoff). |
| **CAND-C** | 0.2040 | 0.1399 | 0.5516 | 0.5105 | Stage 3.5 evaluated on restricted candidate pools (`tests_only` filter on `code2test`). On full unconstrained corpus, repository-wide distractors reduced MRR to $0.1399$. |
| **CAND-F** | 0.2152 | 0.1351 | 0.5652 | 0.5078 | Stage 3.5 bypassed full graph traversal via ripgrep hardcoded string searches and decoupled candidate evaluation. Full unconstrained execution caused unnormalized PageRank diffusion to demote 70 gold files out of top-3. |
| **BASE-REPOMAP** | 0.2140 | 0.2293 | 0.5681 | 0.6599 | Stage 3.5 hardcoded $0.2140$ from a static paper constant in `evaluate_graph_retrieval.py:278`. Live evaluation of pinned RepoMap (`9e4d689`) achieves $MRR = 0.2293$, fractional $Recall@20 = 0.6599$, and binary $Hit@20 = 0.7478$. |

Gate A confirmed that the previous claim that Candidate F beat RepoMap ($0.2152 > 0.2140$) was invalid. Under canonical evaluation, RepoMap ($0.2293$) decisively outperformed Candidate F ($0.1351$).

---

## 3. Gate B: Cascaded Lexical-First Retrieval Architecture

### 3.1 Mathematical Formulation
To eliminate the ranking collapse caused by unnormalized graph diffusion while still recovering deep recall, `CascadedRanker` implements a two-tier hybrid cascade:

1. **Top-3 Lexical Freeze Invariant**:
   For any document collection $\mathcal{D}$, let $\pi_{\text{BM25}}$ be the deterministic BM25 ranking. Ranks $0, 1, 2$ are permanently frozen:
   $$\pi_{\text{final}}[0:3] = \pi_{\text{BM25}}[0:3]$$
   This guarantees that no graph signal, regardless of magnitude, can demote high-confidence lexical matches.
2. **Eligible Pool Scoring ($\text{Rank} \ge 4$)**:
   Candidates outside the top-3 are rescored via linear fusion:
   $$S_i = 0.60 \cdot S_{\text{bm25}}(i) + 0.15 \cdot S_{\text{sem}}(i) + 0.25 \cdot S_{\text{graph}}(i)$$
   followed by a documentation penalty ($0.5\times$) for non-code assets.
3. **Degree-Normalized Graph Propagation**:
   Graph mass is diffused strictly from protected top-3 seeds to eligible neighbors with symmetric degree normalization:
   $$B(succ) = \max_{seed} \left( S_{\text{bm25}}(seed) \cdot 0.25 \cdot \frac{1}{\sqrt{d_{\text{out}}(seed) \cdot d_{\text{in}}(succ)}} \right)$$
   $$B(pred) = \max_{seed} \left( S_{\text{bm25}}(seed) \cdot 0.10 \cdot \frac{1}{\sqrt{d_{\text{in}}(seed) \cdot d_{\text{out}}(pred)}} \right)$$
   This prevents high in-degree hub files (e.g., `utils.py`, `errors.go`, `constants.rs`) from absorbing excessive diffusion mass.
4. **Package & Workspace Fencing**:
   Edges between files in different packages/crates are rejected unless verified by workspace manifest dependencies (`Cargo.toml`, `go.mod`, `package.json`).
5. **Test Discovery Heuristic**:
   Identifies naming conventions (`test_<stem>.py`, `<stem>_test.go`, `tests/<stem>.rs`) to recover test targets in `code2test` tasks without cross-repository symbol pollution.

---

## 4. Empirical Evaluation & Ablation Results

Full evaluation across all $N=345$ positive ARB v2 benchmark queries ($218$ repository snapshots):

| System / Configuration | MRR | Recall@5 | Recall@10 | Recall@20 (Frac) | Hit@20 (Bin) | Precision@5 | BCY@8k | Latency (p50) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **BASE-BM25** (Canonical Baseline) | 0.1752 | 0.2014 | 0.3152 | 0.4535 | 0.5275 | 0.0574 | 0.0488 | 5.67 ms |
| **BASE-REPOMAP** (Pinned Reference) | **0.2293** | **0.3337** | **0.5110** | **0.6599** | **0.7478** | 0.0186 | **0.0652** | 180.20 ms |
| **CAND-C** (Canonical Stage 3.7) | 0.1412 | 0.2053 | 0.3246 | 0.5143 | 0.6058 | 0.0545 | 0.0203 | 31.50 ms |
| **CAND-F** (Canonical Stage 3.7) | 0.1358 | 0.1780 | 0.3287 | 0.5078 | 0.6000 | 0.0499 | 0.0174 | 32.42 ms |
| **CAND-CASCADE** (Proposed Architecture) | **0.1883** | **0.2344** | **0.3665** | **0.5518** | **0.6348** | **0.0678** | 0.0488 | **8.12 ms** |
| **CASCADE-NO-GRAPH** (Ablation) | 0.1856 | 0.2285 | 0.3564 | 0.5416 | 0.6261 | 0.0661 | 0.0488 | 7.64 ms |
| **CASCADE-UNNORMALIZED** (Diagnostic) | 0.1864 | 0.2263 | 0.3581 | 0.5337 | 0.6319 | 0.0643 | 0.0488 | 7.64 ms |

### Paired Statistical Verification ($B=10,000$, Resampling Unit = Query Clustered by Repository):
- **CAND-CASCADE vs. BASE-BM25**:
  - Mean MRR Delta: $+0.0131$
  - 95% Bootstrap CI: $[+0.0102, +0.0162]$ (strictly positive)
  - Wilcoxon signed-rank test: $p = 1.19 \times 10^{-37}$ (statistically significant)
- **CAND-CASCADE vs. CAND-F**:
  - Mean MRR Delta: $+0.0525$
  - 95% Bootstrap CI: $[+0.0308, +0.0743]$ (strictly positive)
  - Wilcoxon signed-rank test: $p = 3.65 \times 10^{-14}$ (statistically significant)
- **CAND-CASCADE vs. BASE-REPOMAP**:
  - Mean MRR Delta: $-0.0410$
  - 95% Bootstrap CI: $[-0.0743, -0.0080]$
  - Wilcoxon signed-rank test: $p = 3.00 \times 10^{-4}$

---

## 5. Task and Language Breakdowns

### 5.1 Per-Task Breakdown (MRR Mean)

| Task Track | Sample Count ($N$) | BASE-BM25 | CAND-C | CAND-F | CAND-CASCADE | BASE-REPOMAP | Best System |
|---|---:|---:|---:|---:|---:|---:|---|
| **code2test** | 106 | 0.0784 | 0.0643 | 0.0605 | **0.0968** | 0.2284 | RepoMap (Call-tree advantage) |
| **comment2context** | 80 | 0.1550 | 0.1177 | 0.1235 | **0.1669** | 0.1590 | **CAND-CASCADE (+5.0% over RepoMap)** |
| **edit2ripple** | 58 | 0.2424 | 0.1350 | 0.1260 | **0.2519** | 0.2344 | **CAND-CASCADE (+7.5% over RepoMap)** |
| **trace2code** | 101 | 0.2542 | 0.2442 | 0.2301 | **0.2646** | 0.2829 | RepoMap |

**Critical Finding**: On `comment2context` and `edit2ripple`, `CAND-CASCADE` directly beats pinned RepoMap. RepoMap's overall macro advantage is concentrated in `code2test`, where full AST call graphs link implementation classes to test suites.

### 5.2 Per-Language Breakdown (MRR Mean)

| Language | Sample Count ($N$) | BASE-BM25 | CAND-F | CAND-CASCADE | BASE-REPOMAP |
|---|---:|---:|---:|---:|---:|
| **Go** | 142 (41%) | 0.2707 | 0.1587 | **0.2865** | 0.2850 |
| **Python** | 98 (28%) | 0.1266 | 0.1452 | **0.1378** | 0.1956 |
| **Rust** | 48 (14%) | 0.1226 | 0.1412 | **0.1308** | 0.2683 |
| **JavaScript** | 26 (8%) | 0.0201 | 0.0262 | **0.0359** | 0.0314 |
| **TypeScript** | 10 (3%) | 0.0578 | 0.0470 | **0.0664** | 0.0971 |

---

## 6. Failure Analysis & Remaining Gap to RepoMap

### 6.1 Win/Loss Dynamics Against BM25
- **Top-3 Rank Preservation Invariant**: **100.0%** compliance (0 violations across all 345 queries).
- **Wins**: 232 queries where cascade improved MRR or Recall@20 over BM25.
- **Ties**: 95 queries where ranking was unchanged.
- **Losses**: 18 queries where lower-rank graph promotions slightly displaced a gold target at rank $\ge 4$.
- **0 early-rank demotions**: The 70 catastrophic early-rank demotions suffered by Candidate F were completely eliminated.

### 6.2 Remaining Gap to RepoMap Baseline
While `CAND-CASCADE` closes **56.1% of the historical quality deficit** between Candidate F and RepoMap, RepoMap retains a lead in deep recall ($0.6599$ vs. $0.5518$ Recall@20) and MRR ($0.2293$ vs. $0.1883$).

The root causes are:
1. **Tree-Sitter Syntax Call Graphs**: RepoMap builds fine-grained call graphs across method calls within class scopes. RepoNeedle's regex-based import parser operates at the file level.
2. **Context-Window Prompt Tree Packing**: RepoMap packs definition signatures directly into the LLM prompt tree, achieving higher token efficiency than whole-file chunk packing.

---

## 7. Research Integrity & Safeguards Audit

1. **Tag Immutability**:
   - `v0.1.0-baseline` (`8e00425...`) has remained unmodified.
   - `stage3-candidate-freeze` (`cd7f3b0...`) has remained unmodified.
2. **Test Suite Verification**:
   - 126/126 automated tests passing in 5.53 seconds.
   - 9 new unit tests in `tests/test_stage3_9_cascade.py` explicitly protecting the cascaded ranking invariants.
3. **Independent Validation Blocker**:
   - ContextBench independent validation remains `BLOCKED — DATA ACCESS` due to sandbox network isolation (HTTP 403 Forbidden).
   - ARB v2 results are strictly reported as development benchmarks and are never claimed as independent generalization evidence.

---

## 8. Authoritative Stage 3.9 Decision & Roadmap

### Decision: **`REVISE AND ADVANCE (CAND-CASCADE APPROVED)`**

- **Candidate C and Candidate F**: Permanently retired as default rankers.
- **CascadedRanker**: Adopted as the new canonical retrieval architecture for RepoNeedle.
- **Stage 3.10 Directive**:
  1. Maintain the frozen BM25 top-3 invariant.
  2. Implement AST-backed call graph extraction (via built-in Python `ast` and tree-sitter if available) to close the remaining gap to RepoMap on `code2test`.
  3. Keep independent validation gated until official ContextBench data is authenticated and locally accessible.
