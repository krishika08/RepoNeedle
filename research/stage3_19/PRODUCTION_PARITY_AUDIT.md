# RepoNeedle Stage 3.19 — Production Parity & Architectural Provenance Audit

**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Starting HEAD SHA:** `c688516f974ddf61e5b15f49f083aa412376e64c` (Stage 3.18)  
**Date:** 2026-10-30  
**Audit Status:** COMPLETE  
**Production Integration Status:** NOT PRODUCTION-INTEGRATED (RESEARCH-HARNESS PROTOTYPE)

---

## 1. Protected Baseline & Git Integrity Verification

Before evaluating architectural parity, all repository invariants, immutable tags, and working tree states were cryptographically verified.

### 1.1 Git Status & Frozen Baseline Tags
| Tag / Reference | Expected Commit SHA | Verified Live SHA | Status |
| :--- | :--- | :--- | :--- |
| `v0.1.0-baseline^{commit}` | `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` | `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` | **IMMUTABLE — VERIFIED** |
| `stage3-candidate-freeze^{commit}` | `cd7f3b01e28695f9a9357e0815069e0eae85baca` | `cd7f3b01e28695f9a9357e0815069e0eae85baca` | **IMMUTABLE — VERIFIED** |
| `HEAD` (Stage 3.18) | `c688516f974ddf61e5b15f49f083aa412376e64c` | `c688516f974ddf61e5b15f49f083aa412376e64c` | **VERIFIED MATCH** |
| Working Tree | Clean | Clean (`git status --porcelain` empty) | **PRISTINE** |

### 1.2 Stage 3.18 Artifact SHA-256 Hashes
| Artifact Path | Size (Bytes) | SHA-256 Checksum | Verification Status |
| :--- | :---: | :--- | :--- |
| `research/stage3_18/CANDIDATE_QUERY_LEVEL_RESULTS.csv` | 55,846 | `4df89ee1b3022dbe6bc0a582d16f7e705cc57736d9d965c32d991e6c5e403b70` | **VERIFIED MATCH** |
| `research/stage3_18/CANDIDATE_LEADERBOARD.csv` | 1,152 | `e5e6e7e160ee3adcf8d92ee616a8aa98ffa56565cf78d39cd8be31a2d06b92dc` | **VERIFIED MATCH** |
| `research/stage3_18/METRIC_RECONCILIATION.csv` | 4,003 | `c846c114550901e925c34aed04e9d89843bf5501bca0255a7fa637ce4010c531` | **VERIFIED MATCH** |
| `research/stage3_18/EXPERIMENT_REGISTRY.jsonl` | 1,688 | `3fe2c5ef993aa8b26e31c6ffdd9b878cc3db5401e435c66a19e6bb7b2f08b082` | **VERIFIED MATCH** |

---

## 2. Production Code Modifications Since Baseline (`v0.1.0-baseline`)

Inspection of the Git tree between `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` and current `HEAD` reveals 8 production files modified (`+1289 / -99` lines total) under `reponeedle/`:

```
 reponeedle/core/abstention.py |  17 +++-
 reponeedle/core/budget.py     | 138 ++++++++++++++++++++++++++++++--
 reponeedle/core/cascade.py    | 295 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
 reponeedle/core/graph.py      | 152 +++++++++++++++++++++++++++++++---
 reponeedle/core/lexical.py    | 465 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++---------------------
 reponeedle/core/semantic.py   |  92 +++++++++++++++++++--
 reponeedle/engine.py          | 204 +++++++++++++++++++++++++++++++++++++++++++---
 reponeedle/models.py          |  25 +++++-
 8 files changed, 1289 insertions(+), 99 deletions(-)
```

### Detailed Functional Inventory of Production Changes:
1. [reponeedle/core/lexical.py](file:///F:/RepoNeedle/reponeedle/core/lexical.py): Refactored BM25 from coupled symbol scoring to decoupled Okapi BM25 (`k1=1.5`, `b=0.75`) with code tokenization, boosting, and path-aware indexing.
2. [reponeedle/core/graph.py](file:///F:/RepoNeedle/reponeedle/core/graph.py): Added polyglot symbol/import regex extraction (`extract_polyglot_symbols`), class-to-test edge tracking, and targeted test score propagation.
3. [reponeedle/core/cascade.py](file:///F:/RepoNeedle/reponeedle/core/cascade.py): Introduced `CascadedRanker` implementing `CONTROL-CASCADE` (top-3 hard lexical freeze, degree-normalized graph expansion on eligible ranks $\ge 4$).
4. [reponeedle/core/budget.py](file:///F:/RepoNeedle/reponeedle/core/budget.py): Implemented knapsack context packing, multi-tier allocation (seed, primary, skeleton), and token estimation.
5. [reponeedle/core/semantic.py](file:///F:/RepoNeedle/reponeedle/core/semantic.py): Added character n-gram hashing and subword TF-IDF embeddings with candidate shortlist filtering.
6. [reponeedle/engine.py](file:///F:/RepoNeedle/reponeedle/engine.py): Updated `RepoNeedleEngine.from_directory` to support polyglot symbol extraction, ignore rules, and configuration flags.

**Crucial Finding:** None of these modifications integrate the `ARM-101` algorithm.

---

## 3. The Implementation Boundary: Production Engine vs. ARM-101 Research Prototype

### 3.1 Where Does ARM-101 Actually Live?
`ARM-101` is implemented strictly within the research harness:
1. **Soft Lexical Damping & Reranking:** Implemented in [research/stage3_14/pilot_attenuation.py](file:///F:/RepoNeedle/research/stage3_14/pilot_attenuation.py) as `ExperimentalLanguageRanker(policy="unattenuated", soft_damping_tau=0.25)`.
2. **Function-Level Call Graph Engine:** Implemented in [research/stage3_11/function_graph_engine.py](file:///F:/RepoNeedle/research/stage3_11/function_graph_engine.py) as `FunctionGraphEngine(enable_verified_calls=True, enable_structural_edges=True)`.
3. **Execution Harness:** Implemented in [research/stage3_14/run_stage3_14_experiments.py](file:///F:/RepoNeedle/research/stage3_14/run_stage3_14_experiments.py).

### 3.2 Where Does the Production Engine Route?
The production engine entry points are:
- CLI Entry Point: [reponeedle/cli.py](file:///F:/RepoNeedle/reponeedle/cli.py)
- API Entry Point: [reponeedle/engine.py](file:///F:/RepoNeedle/reponeedle/engine.py) $\to$ `RepoNeedleEngine.retrieve(...)`

When `reponeedle <query>` or `RepoNeedleEngine.retrieve(...)` is called:
1. It queries `WorkflowRouter.classify_intent(...)` (or fixed linear weights).
2. It scores documents using `BM25Index.score(...)`, `SubwordSemanticIndex.score(...)`, and `RepoGraph.pagerank_scores`.
3. It performs linear score combination:
   $$\text{Score} = w_{\text{lex}} \cdot S_{\text{lex}} + w_{\text{sem}} \cdot S_{\text{sem}} + w_{\text{struct}} \cdot S_{\text{PR}} + \text{boost}_{\text{workflow}}$$
4. It passes results to `BudgetOptimizer.optimize(...)`.

**Neither `FunctionGraphEngine` nor `ExperimentalLanguageRanker` is ever invoked by the production pipeline.**

---

## 4. End-to-End Architectural Call Graph

```mermaid
flowchart TD
    subgraph Production Runtime (Installed Package)
        A1[User Query via CLI / API] --> B1[RepoNeedleEngine.retrieve]
        B1 --> C1[BM25Index.score]
        B1 --> C2[SubwordSemanticIndex.score]
        B1 --> C3[RepoGraph.pagerank_scores]
        B1 --> C4[WorkflowRouter.get_fusion_weights]
        C1 & C2 & C3 & C4 --> D1[Linear Weighted Sum Fusion]
        D1 --> E1[BudgetOptimizer.optimize]
        E1 --> F1[Retrieved Context Tokens]
        style D1 fill:#f9d5e5,stroke:#333,stroke-width:2px
    end

    subgraph Research Harness (ARM-101 Benchmark Pipeline)
        A2[ARB Benchmark Query] --> B2[run_stage3_14_experiments.py]
        B2 --> C5[RepoNeedleEngine.lexical_index.score]
        B2 --> C6[FunctionGraphEngine.build_graph]
        B2 --> C7[ExperimentalLanguageRanker.rank]
        C5 & C6 --> C7
        C7 --> D2["Soft Lexical Damping (tau = 0.25)"]
        D2 --> E2["Level-1 Verified Edge Propagation"]
        E2 --> F2["ARM-101 Ranked File List (MRR 0.2078)"]
        style D2 fill:#d5e8d4,stroke:#274e13,stroke-width:2px
        style F2 fill:#d5e8d4,stroke:#274e13,stroke-width:2px
    end
```

---

## 5. Architectural Comparison Matrix

| Architectural Feature | Production Package (`reponeedle`) | ARM-101 Research Prototype |
| :--- | :--- | :--- |
| **Lexical Engine** | Okapi BM25 (`reponeedle/core/lexical.py`) | Okapi BM25 (`reponeedle/core/lexical.py`) |
| **Semantic Engine** | Subword TF-IDF (`reponeedle/core/semantic.py`) | Subword TF-IDF (`reponeedle/core/semantic.py`) |
| **Graph Representation** | File-level import & symbol graph (`RepoGraph`) | Function-level call graph (`FunctionGraphEngine`) |
| **Call Edge Verification** | None (heuristic file imports only) | Intra-file, verified call, unique global call |
| **Ranking Policy** | Linear weighted sum fusion (Candidate C / legacy) | Soft Lexical Damping ($\tau=0.25$) on BM25 top seeds |
| **Package Fencing** | Available in unused `CascadedRanker` | Implemented in `ExperimentalLanguageRanker` |
| **Hub Attenuation** | None | Unattenuated reference (Policy: `unattenuated`) |
| **Token Context Packing** | `BudgetOptimizer` (Knapsack + Skeleton tiers) | Evaluated via `independent_metrics.py` |
| **Canonical ARB v2 MRR** | **0.1399** (Candidate C) / **0.1752** (pure BM25) | **0.2078** (ARM-101-BASE) |
| **Installed User Exposure** | **100% of user queries** | **0% of user queries** |

---

## 6. Audit Verdict on Production Parity

> [!IMPORTANT]
> **Definitive Finding:** `ARM-101-BASE` is an unintegrated research harness prototype. The code that achieved the $0.2078$ MRR development benchmark does not execute when a user installs and runs `reponeedle`.
> 
> The installed application currently executes either legacy linear fusion ($0.1399$ MRR) or decoupled BM25 ($0.1752$ MRR). While the production code contains `CascadedRanker` ($0.1897$ MRR), even `CascadedRanker` is disconnected from `RepoNeedleEngine.retrieve()`.

Therefore, the candidate cannot be certified as production-ready without an explicit production migration stage. The formal governance verdict is:
**`B. INTERNALLY REPRODUCIBLE BUT NOT PRODUCTION-INTEGRATED`**.

