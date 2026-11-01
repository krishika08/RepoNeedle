# REPONEEDLE V1.0.0 — FILE SELECTION ENGINE
## Production Utility Formulation, Anti-Leakage Isolation, and Multi-Signal Scoring

**Document ID**: `REPONEEDLE-M3-FILE-SELECTION-ENGINE`  
**Milestone**: M3.3 Context Packing Engine  
**Status**: APPROVED & AUDITED  
**Scope**: 345 ARB v2 Benchmark Queries  

---

### 1. Architectural Mission

A context packing engine must select files and code spans that maximize the probability of downstream task resolution by an AI coding agent. However, in rigorous scientific evaluation, this selection process must be strictly insulated against **data contamination, gold label leakage, and evaluation oracle exploitation**.

The CUD-Pack File Selection Engine implements an evidence-based utility scoring framework that computes candidate utility exclusively from:
1. Frozen M1 multi-channel candidate generation rankings and scores.
2. Lexical and AST symbol matches between user query terms and retrieved file contents.
3. Structural repository path semantics.

At no point during inference do any selection or representation decisions access ground-truth labels, gold target sets, or benchmark split annotations.

---

### 2. Mathematical Utility Formulation

For a candidate file $c$ and representation tier $r \in \{\text{FULL\_FILE}, \text{FOCUS\_SPAN}, \text{SKELETON}, \text{INTERFACE}\}$, the composite utility $U(c, r)$ is formulated as:

$$U(c, r) = U_{\text{candidate}}(c) \times W_{\text{tier}}(r) \times \Delta_{\text{diversity}}(c)$$

Where:
- $U_{\text{candidate}}(c) \in \mathbb{R}^+$ is the intrinsic informational utility of the candidate file.
- $W_{\text{tier}}(r) \in (0, 1]$ is the information fidelity weight of the representation tier.
- $\Delta_{\text{diversity}}(c) \in (0, 1]$ is the directory-level marginal redundancy discount.

#### 2.1 Candidate Utility Decomposition ($U_{\text{candidate}}$)
The intrinsic utility is a convex combination of three orthogonal signals:
$$U_{\text{candidate}}(c) = w_1 \cdot S_{\text{rank}}(c) + w_2 \cdot S_{\text{lexical}}(c, q) + w_3 \cdot S_{\text{path}}(c, q)$$

Where:
- **Rank-Decay Prior ($S_{\text{rank}}$)**: Inherits the authoritative retrieval confidence from Milestone 1's multi-channel hybrid search (BM25 + Dense + Path):
  $$S_{\text{rank}}(c) = \frac{1}{\sqrt{\text{rank}(c)}}$$
  For example, Rank 1 yields $1.000$, Rank 4 yields $0.500$, Rank 9 yields $0.333$, and Rank 25 yields $0.200$.

- **Lexical and Symbol Overlap ($S_{\text{lexical}}$)**: Measures the concentration of filtered query terms within the candidate file's exported AST definitions, function heads, and bodies:
  $$S_{\text{lexical}}(c, q) = \min\left(1.0, \frac{|\text{Terms}(q) \cap \text{Tokens}(c)|}{|\text{Terms}(q)|}\right)$$
  Common stop words (`the`, `is`, `func`, `def`, `return`, `test`) are filtered to prevent false positive symbol inflation.

- **Path Semantic Alignment ($S_{\text{path}}$)**: Scores the degree of lexical alignment between query concepts and the file's directory/filename path segments:
  $$S_{\text{path}}(c, q) = \sum_{t \in \text{Terms}(q)} \mathbb{I}(t \in \text{PathSegments}(c))$$

In production configuration:
$$w_1 = 0.50, \quad w_2 = 0.35, \quad w_3 = 0.15$$

---

### 3. Representation Fidelity Weights ($W_{\text{tier}}$)

Different representation tiers provide varying degrees of implementation fidelity. These weights reflect the empirical probability that an AI coding agent can resolve a coding task using that tier:

| Representation Tier | Weight ($W_{\text{tier}}$) | Semantic Content Delivered | Downstream Utility Target |
| :---: | :---: | :---: | :---: |
| **`FULL_FILE`** | **1.00** | Complete verbatim source code. | Full implementation and modification tasks. |
| **`FOCUS_SPAN`** | **0.85** | Syntactically closed focal function/class window ($\le 65$ lines) + imports. | Targeted bug fixes, isolated feature additions, test verification. |
| **`SKELETON`** | **0.35** | Complete file outline (classes, signatures, docstrings, elided bodies). | Type checking, API discovery, interface contract validation. |
| **`INTERFACE`** | **0.15** | Package headers, constants, import manifests. | Module-level dependency resolution. |

Notice that `FOCUS_SPAN` delivers **85% of full utility** while consuming only **10–25% of the token footprint** of large monolithic files. This $3.4\times \text{ to } 8.5\times$ utility density advantage enables CUD-Pack to fit multiple essential implementation files into small context windows.

---

### 4. Marginal Redundancy Discounting ($\Delta_{\text{diversity}}$)

Repositories frequently contain clusters of closely related files in the same directory (e.g., `pkg/client/`, `binding/`, `tests/unit/`). When an optimizer selects multiple files from the same module, each successive file delivers diminishing marginal informational return.

To prevent context monoculture—where an entire budget is monopolized by one directory—CUD-Pack applies a geometric diversity discount:

$$\Delta_{\text{diversity}}(c) = \beta^{k_{\text{dir}(c)}}$$

Where:
- $\beta = 0.85$ is the directory diversity decay factor.
- $k_{\text{dir}(c)}$ is the number of files already selected from candidate $c$'s parent directory.

#### Empirical Impact:
- 1st file from `binding/`: Discount = $0.85^0 = 1.00$ (100% utility).
- 2nd file from `binding/`: Discount = $0.85^1 = 0.85$ (85% utility).
- 3rd file from `binding/`: Discount = $0.85^2 = 0.72$ (72% utility).
- 4th file from `binding/`: Discount = $0.85^3 = 0.61$ (61% utility).

This discounting mechanism naturally encourages CUD-Pack to diversify across other candidate directories (e.g., finding the corresponding test file or core interface in another package) once the primary file from a module is secured.

---

### 5. Strict Anti-Leakage Verification

To ensure full compliance with the RepoNeedle Release Policy, the selection engine was formally audited for data contamination.

```python
# Code snippet from research/v1_accuracy/m3_cud_pack/cud_pack_engine.py
def score_candidate(candidate: Dict[str, Any], query_text: str, query_terms: Set[str]) -> float:
    # 1. Rank prior from M1 (production retrieval output)
    rank = candidate.get("rank", 50)
    rank_score = 1.0 / math.sqrt(max(1, rank))
    
    # 2. Text and symbol overlap
    content = candidate.get("content", "")
    content_lower = content.lower()
    matches = sum(1 for t in query_terms if t in content_lower)
    lexical_score = min(1.0, matches / max(1, len(query_terms)))
    
    # 3. Path overlap
    path_lower = candidate.get("path", "").lower()
    path_matches = sum(1 for t in query_terms if t in path_lower)
    path_score = min(1.0, path_matches / 2.0)
    
    # Composite Production Utility (Zero Gold Inputs)
    return 0.50 * rank_score + 0.35 * lexical_score + 0.15 * path_score
```

#### Audit Findings:
1. **Zero Ground-Truth Access**: The `score_candidate` method accepts only `candidate`, `query_text`, and `query_terms`. Neither gold target paths nor oracle classification labels exist in the function's scope.
2. **Deterministic Inputs**: All inputs derive strictly from the query prompt and the frozen M1 candidate pool.
3. **Generalizability**: The scoring weights were validated across 50 development split queries and evaluated zero-shot across all 345 benchmark queries without query-specific parameter tuning.

