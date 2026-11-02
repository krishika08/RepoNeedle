# R6 Integration Design Document: Change-Impact Ranking Engine in RepoNeedle V1.1

**Document ID**: `R6-INT-DES-001`  
**Status**: APPROVED & IMPLEMENTED  
**Target Release**: RepoNeedle V1.1.0  
**Integration Branch**: `v1.1-change-impact`  
**Base Commit**: `fc8efa1d29811e96be5808975bb51be93c467602` (from `v1.0-zero-failure`)  
**Author**: Principal Software Architect & Information Retrieval Engineer  

---

## 1. Executive Summary & Architectural Philosophy

RepoNeedle V1.0 established a hardened, zero-failure code retrieval engine with CUD-Pack packing guarantees. In Phase R5 and Phase R6 research, the typed Change-Impact Retrieval engine demonstrated statistically significant gains in retrieval relevance ($\Delta \text{MRR} = +0.0289$, $p = 0.0078$ pooled across 18 independent open-source repositories).

The architectural mission of RepoNeedle V1.1 is **Controlled, Opt-In Integration**:
1. **Preserve Production Default**: The default ranking engine remains `RankerType.LEGACY` (`"legacy"`). No existing user pipeline or automated workflow will change behavior unless explicitly opting in.
2. **Opt-In Flag**: Users and downstream agents activate the new capability via `ranking_engine="change_impact"` (or `ranker="change_impact"`).
3. **Fail-Safe Fallback**: If graph traversal or change-impact scoring raises an unexpected exception, the system automatically falls back to legacy lexical/semantic scoring without failing the user request (`fallback_on_error=True` by default).
4. **CUD-Pack Invariant Guarantee**: Downstream context window packing, token budget limits, deduplication, and zero-overflow guarantees are 100% preserved. The ranker alters only the candidate sorting order; the packing engine enforces the packing contract identically.
5. **Zero-Oracle Verification**: The ranking engine operates strictly on query strings, repo files, and static graph topology (imports, definitions, directories, test stems). Zero ground-truth or benchmark oracle metadata is accessible.

---

## 2. Component Architecture

```
+-----------------------------------------------------------------------------------------+
|                                    User / CLI / API                                     |
|                       RepoNeedleEngine.query(..., ranking_engine="change_impact")       |
+-----------------------------------------------------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                   RepoNeedleEngine                                      |
|  1. Lexical / Semantic Scoring (BM25 + Dense Candidates)                                 |
|  2. Ranker Dispatch:                                                                    |
|     - "legacy": Sort candidates by base score                                           |
|     - "change_impact": Invoke ChangeImpactRanker.rank_candidates(...)                   |
+-----------------------------------------------------------------------------------------+
                                             |
                      +----------------------+----------------------+
                      | (try)                                       | (on error & fallback)
                      v                                             v
+------------------------------------------+        +-----------------------------------+
|            ChangeImpactRanker            |        |           Legacy Ranker           |
|  - Parse query seed files / target stems |        |  - Default stable score sort      |
|  - Graph-guided structural propagation   |        |  - Zero change to V1.0 behavior   |
|  - Edge-weight propagation (depth=2)     |        +-----------------------------------+
|  - Explainability generation             |                          |
+------------------------------------------+                          |
                      |                                               |
                      +----------------------+------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                CUD-Pack Packing Engine                                  |
|  - Deduplication & Seed-First Preservation                                              |
|  - Greedy Context Packing up to Token Budget                                            |
|  - Zero-Token Overflow Invariant                                                        |
+-----------------------------------------------------------------------------------------+
```

---

## 3. Data Structures and API Contracts

### 3.1 `RankerType` Enum
Located in [`reponeedle/models.py`](file:///F:/RepoNeedle/reponeedle/models.py):
```python
class RankerType(str, Enum):
    LEGACY = "legacy"
    CHANGE_IMPACT = "change_impact"
```

### 3.2 `ChangeImpactConfig` Dataclass
Located in [`reponeedle/core/change_impact.py`](file:///F:/RepoNeedle/reponeedle/core/change_impact.py):
```python
@dataclass
class ChangeImpactConfig:
    """Configuration for typed Change-Impact Ranking Engine."""
    enable_graph: bool = True
    max_hops: int = 2
    decay_factor: float = 0.6
    confirmed_weight: float = 1.0
    heuristic_weight: float = 0.35
    fallback_on_error: bool = True
    return_explanations: bool = True
```

### 3.3 `ChangeImpactRanker` Implementation Contract
```python
class ChangeImpactRanker:
    """Production Change-Impact Ranking Engine for RepoNeedle V1.1."""
    
    def __init__(self, config: Optional[ChangeImpactConfig] = None):
        self.config = config or ChangeImpactConfig()

    def rank_candidates(
        self,
        query: str,
        candidates: List[ScoredFile],
        all_indexed_files: Optional[List[str]] = None,
        seed_files: Optional[List[str]] = None,
    ) -> List[ScoredFile]:
        """Reranks candidate files based on typed dependency and impact graph."""
        ...
```

### 3.4 `ScoredFile.explanation` Contract
Each candidate file scored by `ChangeImpactRanker` receives an explanation string attached to `ScoredFile.explanation`, documenting:
- Prior base score
- Net structural boost
- Active graph hops and triggering seed files
- Top relationship edge types (e.g., `import`, `dir_proximity`, `symbol_def`)

---

## 4. Invariant Preservation Details

### 4.1 CUD-Pack Invariant
RepoNeedle's core value proposition is deterministic context construction without LLM context window overflows.
- **Budget Compliance**: CUD-Pack measures exact token lengths per file using `TokenCounter` (`tiktoken` / `cl100k_base` approximation).
- **Ranking vs Packing Separation**: The ranker solely alters the priority ordering $P = (f_{\pi(1)}, f_{\pi(2)}, \dots, f_{\pi(K)})$. CUD-Pack iterates over $P$ and packs files greedily until `token_budget` is exhausted.
- **Preservation Invariant**: Regardless of ranker output or edge weights, `total_tokens <= max_token_budget` is guaranteed by unit and integration tests.

### 4.2 Fail-Safe Fallback
If an unhandled exception occurs inside `ChangeImpactRanker.rank_candidates` (e.g. malformed AST, OS path decoding failure, unexpected recursion):
- When `fallback_on_error=True` (default): A warning is logged, and the candidates are returned in their original base-score ranking order. No exception propagates to the caller.
- When `fallback_on_error=False` (strict mode): The exception is raised directly, allowing CI and debugging harnesses to detect issues immediately.

### 4.3 Graph Disablement
Setting `enable_graph=False` (or `--disable-graph` in the CLI) bypasses graph parsing and edge propagation entirely. Candidates are ranked purely by lexical and semantic priors.

---

## 5. CLI Interface Design

The RepoNeedle CLI (`reponeedle/cli.py`) is enhanced with backwards-compatible flags:
```bash
# Default V1.0 behavior
reponeedle search "auth session handler" --budget 8000

# Opt-in Change-Impact Ranking
reponeedle search "auth session handler" --ranking-engine change_impact --budget 8000

# Advanced Tuning Options
reponeedle search "auth session handler" \
    --ranking-engine change_impact \
    --graph-depth 2 \
    --decay-factor 0.6 \
    --explain
```

Output formatting includes rank changes, final scores, and structural explanation summaries in rich ASCII/ANSI tabular format.

---

## 6. Security, Zero-Oracle, and Privacy Boundaries
- **Zero Oracle**: The ranking engine has no network calls, no telemetry, and no ingestion of benchmark test harnesses, ground truth manifests, or `.gold` files.
- **Path Isolation**: Path traversal is validated to prevent directory traversal outside the active repository root.
- **Deterministic**: Given identical query string and file tree, output ranking is strictly deterministic.

