# RepoNeedle Stage 3.9.6: Fragment-Aware Lexical Index Implementation

> **Module Location:** [`research/stage3_9/prototypes/fragment_lexical_engine.py`](file:///F:/RepoNeedle/research/stage3_9/prototypes/fragment_lexical_engine.py)  
> **Status:** Implemented and Unit-Tested  
> **Architecture Invariant:** Zero modifications to production code (`reponeedle/`) or benchmark harness (`external/`).

---

## 1. Architectural Overview

The Fragment-Aware Lexical Engine provides fine-grained, function-level lexical representations directly from syntactically complete symbol fragments. It replaces the structurally fragile Lean Function Call Graph (LFCG) with a multi-field inverted index that operates purely within local container files, eliminating graph diffusion, call resolution dependencies, and super-hub rank distortions.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Corpus Symbol Chunks                            │
│                     (kind == "symbol", *.py)                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                         [ Dedent & AST Parse ]
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
   [ Syntax Error ]                                 [ Clean AST Parse ]
           │                                                 │
   ┌───────┴───────┐                                 ┌───────┴───────┐
   ▼               ▼                                 ▼               ▼
Header Error    Body Error                       No Func        FuncDef / Async
(Line <= 2)    (Line > 2)                        Found               Found
   │               │                                 │               │
   ▼               ▼                                 ▼               ▼
INCOMPLETE_     INCOMPLETE_                     QUARANTINED_    COMPLETE_FUNCTION
HEADER_ONLY    BODY_TRUNCATED                     INVALID            │
(Quarantine)    (Quarantine)                    (Quarantine)         ▼
                                                             Multi-Field Extraction:
                                                             - F_name   (w = 2.5)
                                                             - F_qual   (w = 2.0)
                                                             - F_sig    (w = 1.5)
                                                             - F_params (w = 1.5)
                                                             - F_doc    (w = 1.8)
                                                             - F_body   (w = 1.0)
```

---

## 2. Ingestion & Classification Taxonomy

All chunks where `kind == "symbol"` are evaluated fail-closed into four distinct categories:

### 2.1 Complete Functions (`COMPLETE_FUNCTION`)
- **Criteria:** Dedented chunk parses cleanly via Python's standard `ast.parse`. Contains at least one `ast.FunctionDef` or `ast.AsyncFunctionDef`.
- **Extraction:**
  - `name`: Exact function identifier (e.g. `upsert_item`).
  - `parent_class`: Enclosing class name if inside `ast.ClassDef` (e.g. `Item`), else `None`.
  - `qualified_name`: Formatted as `ParentClass.func_name` or `func_name`.
  - `signature`: Reconstructed parameter names, type annotations, and return type hint.
  - `params`: Tuple of parameter names excluding `self` and `cls`.
  - `docstring`: Extracted via `ast.get_docstring(node)` (empty string if absent).
  - `body_text`: Clean source code lines corresponding to the function body.
  - `start_line` / `end_line`: Absolute line boundaries in the parent file.
  - `content_hash`: SHA-256 digest of chunk content.

### 2.2 Incomplete Headers (`INCOMPLETE_HEADER_ONLY`)
- **Criteria:** `SyntaxError` raised on line 1 or 2 of the dedented text while containing function definition keywords (`def `, `async def `).
- **Handling:** Quarantined. Excluded from index to prevent corrupt token attribution.

### 2.3 Truncated Bodies (`INCOMPLETE_BODY_TRUNCATED`)
- **Criteria:** `SyntaxError` raised after line 2 (e.g. unclosed string literal, EOF in multi-line call, unclosed block at chunk boundary).
- **Handling:** Quarantined. Does not contribute partial body tokens.

### 2.4 Quarantined Invalid (`QUARANTINED_INVALID`)
- **Criteria:** Non-Python files, chunks with no function definitions (e.g. standalone class declarations, module-level constant tables), or empty chunks.
- **Handling:** Excluded from the fragment index.

---

## 3. Deduplication and Snapshot Isolation Invariants

1. **Within-Commit Deduplication:** To prevent multiple overlapping chunks from amplifying term frequency for the same function, fragments are deduplicated within each `(repo, base_commit)` snapshot using the composite key:
   $$\text{DedupKey} = \langle \text{filepath}, \text{qualified\_name}, \text{start\_line}, \text{end\_line}, \text{content\_hash} \rangle$$
2. **Strict Snapshot Isolation:** Different repository base commits are evaluated in completely isolated engine instances. Fragments from different commits are never combined.
3. **Candidate Pool Invariance:** If a fragment's `filepath` is not an active candidate document in the current corpus split's `doc_paths`, the fragment is dropped. Fragments can never propose or inject new file candidates.

---

## 4. Multi-Field BM25 Scoring Specification

The index maintains 6 separate inverted posting lists for each complete fragment:

| Field | Description | Weight ($w_k$) | Length Normalization ($b$) |
|---|---|:---:|:---:|
| **$F_{\text{name}}$** | Function identifier | $2.5$ | $0.75$ |
| **$F_{\text{qual}}$** | Qualified hierarchy (Class + Function) | $2.0$ | $0.75$ |
| **$F_{\text{sig}}$** | Full signature text | $1.5$ | $0.75$ |
| **$F_{\text{params}}$** | Space-delimited parameter names | $1.5$ | $0.75$ |
| **$F_{\text{doc}}$** | Extracted docstring text | $1.8$ | $0.75$ |
| **$F_{\text{body}}$** | Function body statements (capped at 1,000 tokens) | $1.0$ | $0.75$ |

For query $q$ and fragment $f$:
$$\text{Score}_{\text{frag}}(q, f) = \sum_{k \in \text{FIELDS}} w_k \sum_{t \in q} \text{IDF}_k(t) \cdot \frac{\text{TF}(t, F_k(f)) \cdot (k_1 + 1)}{\text{TF}(t, F_k(f)) + k_1 \cdot \left(1 - b + b \cdot \frac{|F_k(f)|}{\text{avgdl}_k}\right)}$$
where $k_1 = 1.2$, $b = 0.75$, and $\text{IDF}_k(t) = \ln\left(1 + \frac{N - \text{DF}_k(t) + 0.5}{\text{DF}_k(t) + 0.5}\right)$.

---

## 5. Experimental Retrieval Systems Formulation

### EXP-397: Canonical Stage 3.8 EXP-386 Reference Baseline
- Untouched file lexical BM25 + Subword Semantic.
- Query-conditioned backward edge gating on file graph.
- Verified bit-for-bit locked against historical Stage 3.8 per-query results.
$$S_{\text{EXP-397}}(d) = S_{\text{base}}(d) + 0.15 \cdot \text{boost}_{\text{386}}(d)$$

### EXP-398: Complete-Function Max Pooling
- Projects the maximum complete-function score to its containing candidate file:
$$\Pi_{\text{max}}(d) = \max_{f \in \mathcal{F}(d)} \text{Score}_{\text{frag}}(q, f)$$
- Normalized by corpus maximum and scaled by $\max_{d'} S_{\text{base}}(d')$:
$$S_{\text{EXP-398}}(d) = S_{\text{EXP-397}}(d) + 0.10 \cdot \left( \frac{\Pi_{\text{max}}(d)}{\max_{d'} \Pi_{\text{max}}(d') + 10^{-9}} \right) \cdot \max_{d'} S_{\text{base}}(d')$$

### EXP-399a: Soft-Max Top-2 Function Pooling
- Changes *only* the projection function to reward files with multiple relevant functions:
$$\Pi_{\text{top2}}(d) = f_{(1)} + 0.5 \cdot f_{(2)}$$
where $f_{(1)} \ge f_{(2)}$ are top-2 function scores in file $d$.
$$S_{\text{EXP-399a}}(d) = S_{\text{EXP-397}}(d) + 0.10 \cdot \left( \frac{\Pi_{\text{top2}}(d)}{\max_{d'} \Pi_{\text{top2}}(d') + 10^{-9}} \right) \cdot \max_{d'} S_{\text{base}}(d')$$

### EXP-399b: Symbol Specificity Attenuation
- Attenuates function scores matching generic function names appearing across many files:
$$\Psi_{\text{spec}}(f) = \frac{1}{\sqrt{\text{corpus\_symbol\_count}(f.\text{name})}}$$
$$\Pi_{\text{spec}}(d) = \max_{f \in \mathcal{F}(d)} \left( \text{Score}_{\text{frag}}(q, f) \cdot \Psi_{\text{spec}}(f) \right)$$
$$S_{\text{EXP-399b}}(d) = S_{\text{EXP-397}}(d) + 0.10 \cdot \left( \frac{\Pi_{\text{spec}}(d)}{\max_{d'} \Pi_{\text{spec}}(d') + 10^{-9}} \right) \cdot \max_{d'} S_{\text{base}}(d')$$

