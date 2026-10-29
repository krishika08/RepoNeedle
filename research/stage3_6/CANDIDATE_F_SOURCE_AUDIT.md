# RepoNeedle Stage 3.6: Forensic Source Audit of Candidate F Implementation & Changes

**Document ID**: `STAGE3-6-SRC-001`  
**Date**: October 2026  
**Stage**: Stage 3.6 — Forensic Reproducibility and Candidate F Validation Gate  
**Branch**: `research-program`  
**Base Commit**: `29bb3b9`  
**Audited Historical Commit**: `4f78cc3` (Stage 3.5)  

---

## 1. Component-by-Component Diff & Behavioral Audit

This audit examines the exact modifications introduced in Stage 3.5 across `reponeedle/core/graph.py`, `reponeedle/engine.py`, and `reponeedle/core/abstention.py`.

### 1.1 `reponeedle/core/graph.py` (RepoGraph Construction & Diffusion)

#### A. Manifest Parsers for Multi-Crate Workspaces
1. **Cargo Workspace Parsing (`parse_cargo_manifest`)**:
   - **Mechanism**: Utilizes Python 3.11 standard library `tomllib.loads`.
   - **Extracted Fields**: `package.name`, `workspace.members` (globs), and path dependencies under `[dependencies]`, `[dev-dependencies]`, `[build-dependencies]`.
   - **Resilience**: Encapsulated in `try...except Exception`. Malformed or non-standard `Cargo.toml` safely returns empty defaults without crashing.
   - **Verification**: Tested in `tests/test_graph.py::test_cargo_manifest_parsing_valid_and_malformed`.
2. **Go Module Parsing (`parse_go_mod`)**:
   - **Mechanism**: Regex extraction `r"^\s*module\s+([^\s\n]+)"` extracting root module path (e.g., `github.com/caddyserver/caddy/v2`).
   - **Resilience**: Returns empty string if directive is absent or malformed.
   - **Verification**: Tested in `tests/test_graph.py::test_go_mod_parsing_valid_and_malformed`.
3. **JavaScript / TypeScript Workspace Parsing (`parse_package_json`)**:
   - **Mechanism**: Uses `json.loads` to extract `name`, `workspaces` (arrays or yarn/npm dictionary formats), and package dependencies.
   - **Resilience**: Catches `json.JSONDecodeError` safely.
   - **Verification**: Tested in `tests/test_graph.py::test_package_json_parsing_valid_and_malformed`.

#### B. Rust `mod` Declaration Resolution
- **Regex**: `r"^\s*(?:pub(?:\s*\([^)]*\))?\s+)?mod\s+([a-zA-Z0-9_]+);"`
- **Resolution Strategy**: Resolves against both sibling file (`<dir>/<submod>.rs`) and subfolder root module (`<dir>/<submod>/mod.rs`).
- **Resilience**: If neither exists on disk, the import is dropped without generating broken references.
- **Verification**: Tested in `tests/test_graph.py::test_rust_mod_declaration_and_resolution`.

#### C. Cross-Language Regex Symbol Resolution
- **Indexed Patterns**: Rust `fn`/`struct`/`trait`/`enum`, Go `func`/`type struct`, JS/TS `export class/function/const`, Python `def`/`class`.
- **Inverted Symbol Index**: `self.symbol_to_paths[symbol] -> List[filepath]`.
- **Linking Rule**: If file $A$ contains a symbol reference and file $B$ defines it, a directed edge $(A, B)$ is established.

#### D. Graph Topology & Diffusion Properties
- **Underlying Structure**: `networkx.DiGraph`.
- **Deduplication**: Adding an existing edge is idempotent in NetworkX; zero duplicate edges are created.
- **Cycles**: NetworkX PageRank incorporates uniform random restarts ($\alpha = 0.85$), ensuring convergence even with circular dependencies.
- **Diffusion Weights**: Forward callee diffusion $\alpha_{\text{fwd}} = 0.25$, backward caller diffusion $\alpha_{\text{bwd}} = 0.20$.
- **Diffusion Fusion**: Final score fusion adds $0.15 \times \text{diffused\_boost}$ to lexical-semantic score.

---

## 2. Forensic Discovery: The `BurntSushi/ripgrep` Diagnostic Cheat

### 2.1 The Code Inspection Finding
In Stage 3.5 commit `4f78cc3`, inspection of `reponeedle/core/graph.py` lines 425–435 revealed hardcoded strings tailored specifically to pass the single diagnostic benchmark instance `BurntSushi/ripgrep`:

```python
# PREVIOUS UNETHICAL BYPASS IN COMMIT 4f78cc3:
is_entrypoint = norm_p.endswith((..., "search.rs", "standard.rs"))
...
if ("core" in my_crate and "printer" in o_crate):
    self.graph.add_edge(doc.path, o_path)
```

### 2.2 Root Cause of the Cheat
1. The diagnostic test case `BurntSushi/ripgrep` (`CB-HELD-014`) consisted of an isolated 2-file snippet (`crates/core/search.rs` and `crates/printer/src/standard.rs`).
2. Because the test fixture **omitted `Cargo.toml`**, a legitimate manifest parser could not discover that `core` depended on `printer`.
3. To force a graph edge and report a perfect $MRR = 1.0000$ on `BurntSushi/ripgrep`, the author hardcoded specific filenames and crate names.

### 2.3 Corrective Action in Stage 3.6
- **Complete Removal**: The hardcoded strings `"search.rs", "standard.rs"` and `("core" in my_crate and "printer" in o_crate)` were completely excised.
- **Legitimate Resolution**: Inter-crate linking is strictly restricted to valid `Cargo.toml` path dependencies, documented crate entrypoints (`lib.rs`, `main.rs`), and explicit symbol imports.
- **Diagnostic Scope**: The `BurntSushi/ripgrep` test is classified strictly as a **targeted diagnostic fixture**, not independent generalizable evidence.

---

## 3. The Root Cause of Candidate F's Full-Corpus Rank Collapse

When Candidate F was evaluated on the full, unconstrained 25-repository ARB v2 benchmark ($N=345$), its MRR collapsed from the claimed **0.2152** to **0.1351** (and **0.1334** in Stage 3.8/3.9).

Forensic investigation isolated the exact architectural mechanisms responsible for this collapse:

### 3.1 Supernode PageRank Dilution
In large codebases (e.g. `astral-sh/ruff`, `tokio-rs/tokio`, `caddyserver/caddy`), multi-crate manifests created thousands of cross-crate edges. Crate root entrypoints (such as `src/lib.rs` or `main.rs`) became massive **supernodes** connected to hundreds of files.

During PageRank diffusion:
1. Supernodes absorbed disproportionately high PageRank mass.
2. In subsequent diffusion steps, this mass diffused broadly across all connected nodes, homogenizing the score distribution across entire subdirectories.
3. This diluted high-precision lexical matches: true gold files deep in module trees were displaced by generic crate entrypoints and top-level definitions.

### 3.2 Uncoupled BM25 Token Length Inflation
In Stage 3.5, polyglot regex symbols were concatenated directly into document content buffers.
Under BM25 Okapi length normalization:
$$\text{BM25}(D, Q) = \sum_{q \in Q} \text{IDF}(q) \cdot \frac{f(q, D) \cdot (k_1 + 1)}{f(q, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$
Appending thousands of extracted symbol tokens increased $|D|$ by $2\times - 5\times$, heavily penalizing the document's base lexical score.

### 3.3 Evaluation Verdict
Candidate F is architecturally flawed on full repositories. The combination of supernode PageRank dilution and token length inflation causes Candidate F ($0.1351$ MRR) to regress below both frozen Candidate C ($0.1399$ MRR) and pure BM25 ($0.1735$ MRR). Candidate F is permanently rejected.
