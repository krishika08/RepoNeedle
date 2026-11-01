# RepoNeedle Stage 3.8: Failure Analysis & Structural Boundaries
## Remaining Retrieval Bottlenecks, Invariants, and the Gap to RepoMap

---

### 1. Overview of Evaluated Architectures

Stage 3.8 evaluated 5 controlled configurations over all 345 positive ARB v2 queries under the unconstrained evaluation protocol:
- **`EXP-384` (Reference Repro)**: $\text{MRR} = 0.2052$, $\text{Recall@20} = 0.5508$, $\text{Hit@20} = 0.6406$
- **`EXP-385` (Query-Affinity)**: $\text{MRR} = 0.2040$, $\text{Recall@20} = 0.5566$, $\text{Hit@20} = 0.6464$
- **`EXP-386` (Edge-Type Gated)**: $\text{MRR} = 0.2062$, $\text{Recall@20} = 0.5566$, $\text{Hit@20} = 0.6464$
- **`EXP-387` (Degree Dampened)**: $\text{MRR} = 0.2036$, $\text{Recall@20} = 0.5566$, $\text{Hit@20} = 0.6464$
- **`EXP-388` (Combined QC)**: $\text{MRR} = 0.2040$, $\text{Recall@20} = 0.5566$, $\text{Hit@20} = 0.6464$

While `EXP-386` successfully resolved the test file displacement in Click and Clap, lifting MRR to **0.2062** and Recall@20 to **0.5566**, there remains an open performance gap between RepoNeedle (0.2062) and RepoMap (0.2293 MRR, 0.6599 Recall@20).

This document analyzes the fundamental failure mechanisms that account for the remaining errors.

---

### 2. Failure Mechanism Taxonomies

#### 2.1 Failure Mechanism 1: High Semantic-to-Lexical Gap
- **Description**: Natural language queries that describe abstract system behavior without mentioning specific function, class, or file names (e.g., *"Handle graceful socket teardown on sudden connection abort"*).
- **Behavior in RepoNeedle**:
  - BM25 finds zero exact symbol or stem matches.
  - Character n-gram subword retrieval matches common subwords (`<handle>`, `<connect>`), but lacks semantic word associations (e.g., connecting `teardown` with `close_socket` or `abort` with `SIGTERM`).
  - Because base scores are low, seed identification selects noisy documents, and graph propagation diffuses from incorrect seeds.
- **Why RepoMap Handles This Better**: RepoMap utilizes comprehensive repository symbol tables (ctags / tree-sitter definition tags) that extract all class, method, and variable signatures, providing broader lexical surface area.

#### 2.2 Failure Mechanism 2: Coarse File-Level vs Fine Function-Level Granularity
- **Description**: RepoNeedle's dependency graph operates at the **file level** ($G=(V_{\text{files}}, E_{\text{imports}})$).
- **Behavior**:
  - When file $A$ imports file $B$, the edge connects the entire document $A$ to document $B$.
  - In large libraries (e.g., `transformers` or `diffusers`), an import file often defines 50+ classes and functions.
  - Propagating relevance at the file level treats all 50 functions equally, transferring energy to unrelated functions in file $B$.
- **Why RepoMap Handles This Better**: RepoMap constructs a **bipartite identifier-reference graph** linking specific identifier references directly to their definition scopes.

#### 2.3 Failure Mechanism 3: Dynamic Language Resolution & Reflection Boundaries
- **Description**: In dynamic languages (Python, JavaScript), imports are frequently performed dynamically or via package namespaces:
  - Python: `importlib.import_module(...)`, `getattr(obj, "method")`
  - JavaScript: `require(dynamic_path)`
- **Behavior**:
  - Static AST and regex parsers miss dynamic call targets.
  - The graph becomes disconnected into multiple disconnected components, preventing diffusion from reaching the true gold target.

#### 2.4 Failure Mechanism 4: Context Budget Packing Truncation
- **Description**: Target files ranked between Rank #10 and #20 are often excluded from the final 8,000-token context budget.
- **Behavior**:
  - While Hit@20 is **0.6464** (nearly 65% of queries have gold targets in top 20 files), BCY@8k is **0.0527** (~5.3% gold token coverage).
  - Large files (especially in `transformers` and `diffusers`) consume thousands of tokens, exhausting the 8k budget before all gold files can be packed.

---

### 3. Forensic Case Studies of Unresolved Queries

| Query ID | Repository | Track | Target Gold File | Final Rank | Reason for Failure |
|---|---|---|---|---:|---|
| `33c925493a0f` | `clap-rs/clap` | `edit2ripple` | `clap_builder/src/util/mod.rs` | 148 | Utility module with 0 out-degree imports, high in-degree, but query contains no identifier tokens from the file. |
| `597f32e9b482` | `clap-rs/clap` | `code2test` | `tests/builder/help.rs` | 83 | Query contains general help formatting strings that match documentation files and builder files rather than test suite. |
| `a55339576600` | `huggingface/transformers` | `code2test` | `tests/models/llama/test_modeling_llama.py` | 52 | Llama model test file has over 3,000 lines; lexical matches match model definition rather than test script. |

---

### 4. Strategic Recommendations for Stage 3.9

To close the remaining gap to RepoMap (0.2293 MRR / 0.6599 Recall@20) without sacrificing CPU efficiency or falling back to heavy neural models:
1. **Function-Level / Symbol-Level Call Graph**: Extend `RepoGraph` from coarse file-level edges to fine-grained class/function invocation linkages.
2. **Selective Query-Adaptive Propagation**: Disable backward propagation when query lexical confidence is below a calibrated entropy threshold.
3. **Adaptive Chunk-Level Budget Packing**: Rather than packing entire files into the 8k budget, pack targeted chunks containing matched symbols and surrounding function scopes.

