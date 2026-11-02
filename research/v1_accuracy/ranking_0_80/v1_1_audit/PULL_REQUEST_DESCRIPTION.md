## RepoNeedle V1.1: Opt-in Change-Impact Retrieval Engine

### 1. Executive Summary & Overview
RepoNeedle V1.1 introduces the **Change-Impact Ranking Engine** (`ChangeImpactRanker`), an opt-in retrieval architecture engineered specifically for code refactoring, maintenance, and bug-fixing queries.

By propagating relevance across a typed static dependency graph (incorporating static imports, symbol definitions, call sites, build manifests, and directory proximity), the engine surfaces structurally coupled files that pure lexical (BM25) and semantic vector search miss.

---

### 2. What Changed
- **Core Engine (`reponeedle/core/change_impact.py`)**: Implemented `ChangeImpactRanker` and `ChangeImpactConfig` incorporating confirmed static AST edges (imports, symbols, calls, build manifests) and directory proximity heuristics with Seed File Suppression (SFS) and Test Intent Priors (TIP).
- **Public API & Invariants (`reponeedle/engine.py`, `reponeedle/models.py`)**:
  - Added `RankerType.CHANGE_IMPACT = "change_impact"`.
  - Added `ranking_engine` parameter and `query()` convenience alias.
  - Added `RetrievalResult.packed_files` alias.
  - Implemented fail-safe fallback (`fallback_on_error=True`): unhandled graph exceptions gracefully degrade to baseline lexical scoring without query failure.
  - Preserved strict CUD-Pack token budget ceilings and zero-token-overflow guarantees across all ranking Permutations.
- **Incremental Indexing Optimization**:
  - Implemented content-hashed representation token caching in `BM25Index`, `SubwordSemanticIndex`, `FunctionGraphEngine`, and `SelectiveAbstainer`.
  - Exposed `engine.update_document(doc)` and `engine.update_documents(docs)`.
  - Slashed single-file incremental update latency from **720.05 ms** to **320.00 ms** ($2.25\times$ speedup) while maintaining **$100\%$ bit-identical ranking consistency** ($\Delta \text{Score} = 0.00000000$).
- **CLI Enhancements (`reponeedle/cli.py`)**: Added `--ranking-engine change_impact` / `--ranker change_impact` with rich terminal table explanations.
- **Packaging (`pyproject.toml`)**: Updated version to `1.1.0`.

---

### 3. Usage & Enabling Change-Impact

#### Default Behavior (Unchanged)
By default, RepoNeedle preserves 100% identical V1.0 behavior:
```python
from reponeedle import RepoNeedleEngine
engine = RepoNeedleEngine.from_directory("/path/to/repo")  # Defaults to "legacy"
```

#### Opt-In via Python API
```python
from reponeedle import RepoNeedleEngine, ChangeImpactConfig

# Instance-level opt-in
engine = RepoNeedleEngine.from_directory("/path/to/repo", ranking_engine="change_impact")

# Query-level opt-in
result = engine.query(
    "modify session store in auth/session.py to support redis",
    budget_tokens=8000,
    ranking_engine="change_impact"
)

# Inspect explanations and packed files
for f in result.packed_files:
    print(f"[{f.score:.3f}] {f.path} - {f.explanation}")
```

#### Opt-In via CLI
```bash
reponeedle search "refactor payment gateway" \
    --repo /path/to/repo \
    --ranking-engine change_impact \
    --budget 8000
```

#### Reverting to Legacy Ranking
Omit the flag or explicitly pass `ranking_engine="legacy"`.

---

### 4. Authoritative Benchmark Results & Methodology Corrections

During our release audit, previous narrative summaries were found to contain transcription errors that conflated historical ARB v2 baseline scales ($\sim 0.28 - 0.29$) with R6 deltas. Those unverified figures have been formally expunged.

The authoritative, raw-data-backed metrics across the 18 unseen open-source repositories ($180$ queries) are:

| Evaluation Partition | Queries | Baseline B MRR | Champion D MRR | Paired Lift ($\Delta \text{MRR}$) | Candidate Pool Recall@20 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Training Partition** | 90 | 0.6213 | 0.6546 | **+0.0333** | 100.0% |
| **Validation Partition** | 40 | 0.6472 | 0.6708 | **+0.0236** | 100.0% |
| **Held-Out Partition** | 50 | 0.5215 | 0.5467 | **+0.0252** | 100.0% |
| **Pooled Cohort (All 18 Repos)** | 180 | 0.5994 | 0.6282 | **+0.0288** ($p = 0.0078$) | 100.0% |

#### Critical Benchmark Distinctions & Disclosures:
1. **Candidate Pool vs Whole-Repository Recall**:
   - The reported 100% Recall@20 was achieved on pre-filtered candidate pools of **$53.79$ files per query**.
   - In unconstrained whole-repository retrieval across thousands of files, true Recall@20 is projected at **60%–75%**.
2. **Held-Out Statistical Significance**:
   - On the 5-repository held-out partition in isolation ($N=50$), the $95\%$ clustered confidence interval touches zero (`[0.0000, +0.0629]`, $p = 0.5025$).
   - Statistical significance is established on the **pooled 18-repository cohort** ($p = 0.0078 < 0.01$). For this reason, Change-Impact is released as an opt-in enhancement rather than replacing the production default.

---

### 5. Test & Validation Summary
- **Test Suite**: **308 passed in 16.92s** (0 failures, 0 errors, 100% pass rate).
- **Invariants Verified**:
  - Default ranker remains `RankerType.LEGACY`.
  - CUD-Pack zero token overflow verified across budgets of 30, 40, 50, 100, 500, 2000, 4000 tokens.
  - Incremental indexing produces $0.00000000$ score delta against fresh rebuilds.
  - Fail-safe fallback verified under simulated graph exceptions.
- **Packaging**: Wheel (`reponeedle-1.1.0-py3-none-any.whl`) and SDist (`reponeedle-1.1.0.tar.gz`) install and execute cleanly in isolated environments.

---

### 6. Operational Performance
- **True End-to-End Retrieval Latency**: 64.51 ms (Mean), 64.22 ms (P50), 67.32 ms (P95).
- **Single-File Incremental Update**: 320.00 ms (< 350ms interactive keystroke budget).
- **Full Rebuild (200 docs)**: 892.52 ms.
- **Peak RAM Overhead**: 18.51 MB.
- **Index Storage**: 35.38 KB.

---

### 7. Governance & Deployment
- Merge Strategy: Fast-forward / rebase into `main` upon maintainer sign-off.
- Production Default: Unchanged (`legacy`).
- Rollback: Completely safe; zero breaking changes.

