# RepoNeedle Stage 3.9.5: Fragment-Aware Lexical Retrieval Architecture Design

> **Document ID:** `research/stage3_9/FRAGMENT_LEXICAL_DESIGN.md`  
> **Status:** Proposal for Research Review (Implementation NOT Authorized)  
> **Reference Architecture:** EXP-386 (Query-conditioned edge-type-aware file graph)  
> **Core Innovation:** Function-level lexical indexing using complete symbol fragments with calibrated container projection, eliminating graph diffusion and call resolution dependencies.

---

## 1. Architectural Motivation & Theoretical Foundation

### 1.1 The Two Fundamental Bottlenecks of Call Graph Diffusion
The empirical failure of Stage 3.9.4 Lean Function Call Graph (LFCG) diffusion was traced to two structural bottlenecks:
1. **The Gold Reachability Bound:** In chunked retrieval benchmarks, reconstructing whole files from snippets results in syntax errors on $33.26\%$ of files, leaving **$64.42\%$ of queries with zero gold files parsed into the symbol graph**.
2. **Super-Hub Pollution:** Propagating scores along CALLS edges allows high-degree utility function hubs to diffuse activation backward into irrelevant caller files, causing rank demotions on previously well-ranked queries.

### 1.2 The Fragment-Aware Lexical Solution
In [`research/stage3_9/SYMBOL_FRAGMENT_RECOVERY.md`](file:///F:/RepoNeedle/research/stage3_9/SYMBOL_FRAGMENT_RECOVERY.md), an inspection of 390,277 `kind == "symbol"` chunks demonstrated that:
- **$91.73\%$ of symbol chunks (357,987 chunks) represent complete, parseable function definitions.**
- Function fragments cover **$91.72\%$ of gold target files (133 of 145)**, compared to only $31.72\%$ for reconstructed whole files.
- While symbol fragments cannot be reliably bound into cross-file call graphs due to absent module-level import tables ($99.98\%$ unresolved calls), **lexical retrieval does NOT require call resolution**.

By shifting from *graph diffusion* to *fragment-aware lexical indexing*, we harvest dense, function-level semantic tokens without any dependency on fragile call resolution or susceptibility to hub diffusion.

---

## 2. Fragment Ingestion, Categorization & Deduplication Schema

### 2.1 Complete vs Incomplete Fragment Taxonomy
All symbol chunks (`kind == "symbol"`) from the corpus are ingested and categorized fail-closed into mutually exclusive tiers:

```
Symbol Fragment Taxonomy:
├── Tier 1: COMPLETE_FUNCTION
│   ├── Exact Python AST `FunctionDef` or `AsyncFunctionDef`
│   ├── Well-formed syntax: matching delimiters, complete signature, parseable body
│   └── Includes docstrings, parameter lists, and decorators
├── Tier 2: INCOMPLETE_HEADER_ONLY
│   ├── Function signature truncated at chunk boundary (unclosed parenthesis / colon)
│   └── Quarantined: Excluded from body lexical index; parameter tokens salvaged if valid
├── Tier 3: INCOMPLETE_BODY_TRUNCATED
│   ├── Function header parsed cleanly, but body truncated by token budget cutoff
│   └── Retained: Signature, name, and docstring indexed; truncated body tokens quarantined
└── Tier 4: QUARANTINED_INVALID
    ├── Class bodies without functions, module-level expressions, syntax errors
    └── Strictly excluded from symbol index
```

### 2.2 Deduplication & Snapshot Isolation Invariants
To prevent corpus pollution across multi-commit benchmarks:
1. **Deduplication Identity Key:** Every complete fragment is uniquely keyed by:
   $$\text{FragKey} = \langle \text{repo}, \text{base\_commit}, \text{filepath}, \text{qualified\_name}, \text{start\_line}, \text{end\_line}, \text{content\_sha256} \rangle$$
2. **Snapshot Boundary Isolation:** Chunks from different repository commit snapshots are never combined or cross-referenced.
3. **No Unrestricted File Creation:** Fragments only contribute lexical evidence to their enclosing parent `FileDoc`. If a fragment's `filepath` does not exist in the canonical candidate file pool $\mathcal{C}_{\text{file}}$ of that corpus, it is discarded. Fragments never create new candidate documents.

---

## 3. Multi-Field Lexical Representation

In whole-file BM25 retrieval, long files suffer from severe term frequency dilution:
$$\text{BM25}(q, D) = \sum_{t \in q} \text{IDF}(t) \cdot \frac{f(t, D) \cdot (k_1 + 1)}{f(t, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$
For large repository files ($|D| \gg \text{avgdl}$), the length penalty drastically diminishes the score of highly relevant 10-line utility or test functions.

### 3.1 Field-Weighted Function Document
For each complete function fragment $f \in \mathcal{F}(D)$, a structured lexical document $\mathbf{x}_f$ is extracted:

| Field | Source Content | Tokenization & Normalization | Field Weight ($w_i$) |
|---|---|---|:---:|
| **$F_{\text{name}}$** | Function identifier (e.g. `test_batch_norm`) | Snake_case and camelCase splitting + exact raw token | $2.5$ |
| **$F_{\text{qual}}$** | Qualified hierarchy (e.g. `ModelTrainer.eval_step`) | Hierarchical prefix tokens + class name | $2.0$ |
| **$F_{\text{sig}}$** | Parameters, argument names, type hints | Parameter identifier subwords (excluding builtins) | $1.5$ |
| **$F_{\text{doc}}$** | Function docstring text | Natural language lowercased tokens + punctuation strip | $1.8$ |
| **$F_{\text{body}}$** | Function body statements | Standard code lexical tokens (identifiers + literals) | $1.0$ |

The composite lexical score for function $f$ against query $q$ is:
$$\text{Score}_{\text{frag}}(q, f) = \sum_{i \in \{\text{name}, \text{qual}, \text{sig}, \text{doc}, \text{body}\}} w_i \cdot \text{BM25}(q, F_i(f))$$

---

## 4. Proposed Retrieval Systems: EXP-397, EXP-398, EXP-399

To rigorously isolate and evaluate the function-level lexical signal, three distinct experimental systems are formulated:

```
                            ┌──────────────────────────────────────────────┐
                            │               Query q, Corpus C              │
                            └──────────────────────┬───────────────────────┘
                                                   │
                   ┌───────────────────────────────┴───────────────────────────────┐
                   ▼                                                               ▼
    ┌─────────────────────────────┐                                 ┌─────────────────────────────┐
    │     File-Level Indexing     │                                 │   Function Fragment Index   │
    │  - BM25_file (decoupled)    │                                 │  - BM25_frag (multi-field)  │
    │  - Subword Semantic         │                                 │  - Complete functions only  │
    │  - File Graph (EXP-386 QC)  │                                 │  - Zero graph diffusion     │
    └──────────────┬──────────────┘                                 └──────────────┬──────────────┘
                   │                                                               │
                   ▼                                                               ▼
       S_EXP-397(d) = S_base(d)                                            Score_frag(q, f)
            + 0.15 * boost_386(d)                                                  │
                   │                                                               │
                   ├───────────────────────────────┬───────────────────────────────┤
                   │                               │                               │
                   ▼                               ▼                               ▼
            ┌──────────────┐               ┌──────────────┐                ┌──────────────┐
            │   EXP-397    │               │   EXP-398    │                │   EXP-399    │
            │  Reference   │               │ Direct Max-  │                │  Calibrated  │
            │   Baseline   │               │   Pooling    │                │  Projection  │
            └──────────────┘               └──────────────┘                └──────────────┘
```

### 4.1 EXP-397: Exact EXP-386 Reference Baseline
The frozen, validated Stage 3.8 query-conditioned edge-type-aware file graph:
$$S_{\text{EXP-397}}(d) = S_{\text{base}}(d) + 0.15 \cdot \text{boost}_{\text{386}}(d)$$
where:
$$S_{\text{base}}(d) = 0.5 \cdot \text{BM25}_{\text{file}}(q, d) + 0.5 \cdot \text{Semantic}_{\text{file}}(q, d)$$
with documentation file attenuation ($0.50$), test-file edge gating ($1.25$ / $0.15$), manifest dampening ($0.05$), and degree-dampened backward file graph propagation.

### 4.2 EXP-398: Isolated Function-Level Lexical Matching (Direct Max-Pooling)
Isolates the raw function lexical matching signal by taking the maximum function score associated with each candidate file:
$$S_{\text{EXP-398}}(d) = S_{\text{EXP-397}}(d) + \alpha \cdot \Pi_{\text{max}}(q, d)$$
where:
$$\Pi_{\text{max}}(q, d) = \begin{cases}
\max_{f \in \mathcal{F}(d)} \text{Score}_{\text{frag}}(q, f) & \text{if } \mathcal{F}(d) \neq \emptyset \\
0 & \text{otherwise}
\end{cases}$$
- **Normalization:** $\Pi_{\text{max}}(q, d)$ is normalized by $\max_{d'} \Pi_{\text{max}}(q, d')$ and scaled by $\max_{d'} S_{\text{base}}(d')$.
- **Fixed Fusion Coefficient:** $\alpha = 0.10$.
- **Principle:** If any single function in file $d$ has an exact, dense match with the query terms, file $d$ receives an additive boost proportional to the match quality.

### 4.3 EXP-399: Calibrated File Projection with Density & Hub Dampening
Implements a calibrated projection that prevents common utility functions from overpowering file-level evidence:
$$S_{\text{EXP-399}}(d) = S_{\text{EXP-397}}(d) + \beta \cdot \Pi_{\text{calibrated}}(q, d)$$
where:
$$\Pi_{\text{calibrated}}(q, d) = \left( \text{SoftMaxTop2}(q, d) \cdot \Psi_{\text{spec}}(q, d) \cdot \Theta_{\text{type}}(q, d) \right)$$

1. **Soft-Max Pooling over Top-2 Functions:** Captures multi-function evidence while avoiding score inflation in huge files:
   $$\text{SoftMaxTop2}(q, d) = f_{(1)} + 0.5 \cdot f_{(2)}$$
   where $f_{(1)} \ge f_{(2)}$ are the top-2 scoring functions in file $d$.
2. **Specificity Attenuation ($\Psi_{\text{spec}}$):** Dampens functions matching ubiquitous terms across many files:
   $$\Psi_{\text{spec}}(q, d) = \frac{1}{\sqrt{|\{d' \in \mathcal{C} : \max_{f \in \mathcal{F}(d')} \text{Score}(q, f) > \tau\}|}}$$
3. **Query-Conditioned Task Modulation ($\Theta_{\text{type}}$):**
   - For `code2test` queries seeking tests: Boost files where top-scoring functions are test functions ($1.20$), attenuate non-test functions ($0.80$).
   - For `trace2code` queries seeking error sources: Attenuate test functions ($0.20$), boost implementation functions ($1.10$).
4. **Calibrated Coefficient:** $\beta = 0.12$.

---

## 5. Invariants and Architectural Guarantees

1. **Zero Graph Diffusion:** No function-to-function edges or file-to-file diffusion hops are applied to fragment scores. Score projection is strictly local: $\text{Function} \to \text{Enclosing File}$.
2. **Candidate Pool Invariance:** The candidate file set $\mathcal{C}_{\text{file}}$ remains strictly identical to EXP-386. Fragments cannot propose, inject, or resurrect candidate files outside $\mathcal{C}_{\text{file}}$.
3. **Base File Lexical Score Immutability:** $S_{\text{base}}(d)$ is computed using the exact canonical RepoNeedle indices and is completely untouched.
4. **Deterministic Bit-for-Bit Reproduction:** Fragment parsing, token extraction, and scoring use deterministic ordering, ensuring bit-for-bit repeatability across independent runs.

