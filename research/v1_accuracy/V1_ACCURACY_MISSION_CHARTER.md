# RepoNeedle V1.0.0 — Zero-Failure Accuracy Mission Charter
## Comprehensive Root-Cause Audit, 100% Acceptance Metric Contract, and Engineering Architecture

**Branch:** `v1.0-zero-failure` (created from canonical commit `9b301b0`)  
**Baseline Released Reference:** `v0.1.0` (Research Preview, Tag: `v0.1.0-release`)  
**Standard:** 100% Retrieval-Quality Acceptance Standard on Defined Evaluation Scope  
**Author:** Principal Software Engineer, Research Integrity Auditor & Software Architect  

---

## 1. Absolute Release Policy & Scope Definition

In accordance with strict research integrity and engineering governance:
1. **Preservation of v0.1.0**: The `v0.1.0` Research Preview is frozen at tag `v0.1.0-release` (commit `9b301b0`) on branch `research/stage3_9`.
2. **Dedicated Mission Branch**: All V1.0.0 architecture development is strictly isolated on branch `v1.0-zero-failure`.
3. **No Premature Release**: V1.0.0 will not be released, published, or tagged until every mandatory acceptance gate has been proven with reproducible empirical evidence. Passing unit tests, clean builds, and incremental metric improvements are insufficient.

---

## 2. Mathematical Definition of the 100% Acceptance Standard

For any defined, independently annotated, answerable evaluation scope $\mathcal{Q} = \{q_1, \dots, q_N\}$ with gold target file sets $\mathcal{G}(q)$:

$$\text{Candidate Recall} = \frac{1}{|\mathcal{Q}|} \sum_{q \in \mathcal{Q}} \mathbb{I}\left(\mathcal{G}(q) \subseteq \mathcal{C}(q)\right) = \mathbf{1.000}$$

$$\text{Hit@1} = \frac{1}{|\mathcal{Q}|} \sum_{q \in \mathcal{Q}} \mathbb{I}\left(r_1(q) \in \mathcal{G}(q)\right) = \mathbf{1.000}$$

$$\text{Recall@5} = \frac{1}{|\mathcal{Q}|} \sum_{q \in \mathcal{Q}} \frac{|\{r_1(q), \dots, r_5(q)\} \cap \mathcal{G}(q)|}{|\mathcal{G}(q)|} = \mathbf{1.000}$$

$$\text{Recall@10} = \frac{1}{|\mathcal{Q}|} \sum_{q \in \mathcal{Q}} \frac{|\{r_1(q), \dots, r_{10}(q)\} \cap \mathcal{G}(q)|}{|\mathcal{G}(q)|} = \mathbf{1.000}$$

$$\text{Recall@20} = \frac{1}{|\mathcal{Q}|} \sum_{q \in \mathcal{Q}} \frac{|\{r_1(q), \dots, r_{20}(q)\} \cap \mathcal{G}(q)|}{|\mathcal{G}(q)|} = \mathbf{1.000}$$

$$\text{Context Budget Yield (BCY@8k)} = \mathbf{1.000} \quad (\text{All gold files packed without truncation})$$

### Reporting Rules
- **Zero Aggregation Blending**: Metrics will be reported strictly independently as vectors; never combined into an invented single "accuracy" score.
- **Fail-Closed Accounting**: Unanswerable queries or queries with missing gold labels must be separately classified as `UNANSWERABLE_NO_GOLD`. They will never be silently removed from the denominator to artificially inflate metrics.

---

## 3. Empirical Root-Cause Audit of the Current Engine (v0.1.0)

An audit of all 345 positive benchmark queries across 25 open-source repositories was conducted on the v0.1.0 pipeline.

### 3.1 Overall Performance Baseline ($N=345$)
- **Hit@1 Rate**: **10.4%** (36 / 345 queries retrieved a gold target at Rank 1).
- **Rank 2**: **12.8%** (44 queries).
- **Rank 3–5**: **14.5%** (50 queries).
- **Rank 6–20**: **13.6%** (47 queries).
- **Rank 21–100+ (Severe Regression)**: **48.7%** (168 queries relegated to bottom ranks).
- **Total Rank > 1 Failures**: **309 / 345 (89.6%)**.

### 3.2 Top-1 Distractor Classification (What beat the gold file at Rank 1?)
When the gold file failed to reach Rank 1, the winning distractor belonged to one of six concrete failure classes:

| Distractor Category | Failure Count | Percentage of Failures | Primary Mechanism |
| :--- | :---: | :---: | :--- |
| **Test File Distractor** | **153** | **49.5%** | Uniform coarse test boost in `code2test` and traceback test frames leapfrogging implementation files |
| **Sibling Implementation Distractor**| **90** | **29.1%** | Subword semantic vector noise & lack of exact identifier-level symbol matching |
| **Documentation Distractor** | **24** | **7.8%** | Markdown/RST files (`docs/`, `.md`) matching natural-language query terms |
| **Build Manifest Distractor** | **24** | **7.8%** | High-degree manifests (`Cargo.toml`, `package.json`, `setup.py`) absorbing graph energy |
| **Generic Utility Hub Distractor** | **10** | **3.2%** | Broad helper files (`util.py`, `common.rs`) with massive in-degree |
| **Module Root / Index Hub Distractor**| **8** | **2.6%** | `__init__.py`, `mod.rs`, `index.ts` re-exporting symbols |

### 3.3 Root-Cause Decomposition Across Subsystems

#### 1. Candidate Generation Failure (Relegation to Rank > 20 in 48.7% of queries)
- **Root Cause**: The current candidate generation uses single-stage lexical + semantic addition. If a query uses natural synonyms that differ from source tokens, or if an identifier is split across camelCase boundaries without subword preservation, initial candidate generation assigns zero or near-zero scores. A downstream reranker cannot recover files that are missing from the top candidate pool.

#### 2. Test-to-Target Ambiguity in `code2test` (92 / 106 failed = 86.8%)
- **Root Cause**: In `code2test`, `workflow_boosts[idx] = max(0.4, float(test_scores[idx]))` applies a flat $+0.4$ boost to *every* test file in the repository. Because the test graph relies on coarse file-level imports, multiple unrelated test files receive identical boosts. Lexical noise then pushes the wrong test file to Rank 1.

#### 3. Traceback Frame Leapfrogging in `trace2code` (42 / 101 failed = 41.6%)
- **Root Cause**: In Python tracebacks, the calling test file (`tests/test_foo.py`) appears in the top frame. Because backward graph diffusion propagates energy from the implementation file back to its callers, the test caller receives energy from both the traceback string AND backward diffusion, leapfrogging the implementation target (`src/foo.py`).

#### 4. Semantic Drift & Subword Collision (Sibling Code Distraction, 29.1%)
- **Root Cause**: Subword semantic vectors (character 3-grams to 5-grams) create false-positive collisions across sibling files in the same directory. For example, `crates/ty_python_semantic/src/types/signatures.rs` collides with `builder.rs` because they share extensive type signatures.

---

## 4. V1.0.0 Architectural Blueprint: The Zero-Failure Engine

To systematically eliminate all 6 failure classes and achieve 100% accuracy, RepoNeedle V1.0.0 introduces four architectural pillars:

```
+-------------------------------------------------------------------------------------------------+
|                                 QUERY INTENT & SYMBOL EXTRACTION                                |
|  - Exact Identifier Extractor (AST tokens, function names, classes, backticks, snake/camelCase) |
|  - Traceback Deconstructor (Distinguishes test frames from internal engine frames)              |
|  - Intent Classifier (Task conditioning with fail-closed uncertainty thresholding)              |
+-------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+-------------------------------------------------------------------------------------------------+
|                               MULTI-STAGE CANDIDATE GENERATION                                  |
|  Stage 1: Exact Symbol & Qualified-Name Index (Bitwise inverted index of all AST definitions)   |
|  Stage 2: Field-Weighted BM25 (Filepath: 4.0x, Symbols: 3.0x, Docstrings: 1.5x, Body: 1.0x)   |
|  Stage 3: Fine-Grained Dependency Transitive Closure (Inverted test-call graph)                |
|  --> Guarantee: Candidate Recall = 1.000 at Stage Candidate Pool Size K = 50                  |
+-------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+-------------------------------------------------------------------------------------------------+
|                               STRUCTURAL & CONTEXTUAL RERANKING                                 |
|  - Reciprocal Rank Fusion (RRF) over multi-stage channels (prevents single-channel outliers)   |
|  - Hub-Degree Normalization (Penalizes root manifests and broad utility sinks)                  |
|  - Test-Callee Precise Anchor Linkage (Maps changed function to specific test asserting it)     |
|  - Strict Non-Code Distractor Penalty (0.1x on docs/manifests for code queries)                 |
+-------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+-------------------------------------------------------------------------------------------------+
|                               OPTIMAL KNAPSACK CONTEXT PACKING                                  |
|  - Topological Order Preservation: Ranks 1 to N packed in strict fused priority order           |
|  - Multi-Tier Structural Skeleton Fallback under Token Pressure                                 |
+-------------------------------------------------------------------------------------------------+
```

---

## 5. Controlled Experimental Roadmap & Milestones

Every intervention will be executed under the 10-step research protocol:

- **Milestone 1 (Candidate Generation)**: Implement Multi-Stage Candidate Generation (Exact Symbol + Field BM25). Target: **Candidate Recall@50 = 1.000**.
- **Milestone 2 (Code2Test & Traceback Resolution)**: Implement AST Function-Call Test Linkage and Traceback Frame Inversion. Target: **`code2test` and `trace2code` Hit@1 = 1.000**.
- **Milestone 3 (Distractor Elimination)**: Implement Manifest & Documentation Dynamic Dampening and Sibling Disambiguation. Target: **Zero distractor top-1 inversions**.
- **Milestone 4 (Generalization & Holdout Validation)**: Evaluate on untouched holdout repositories with independent ground-truth annotations. Target: **100% metrics replicated on holdout**.
- **Milestone 5 (V1.0.0 Release Verification)**: Full regression suite, clean packaging, performance benchmarking, and sign-off.
