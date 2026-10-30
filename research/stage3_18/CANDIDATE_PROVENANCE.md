# RepoNeedle Stage 3.18 — Forensic Candidate Provenance Ledger

**Document ID**: `STAGE3-18-PROV-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `461f690d5b4bd3c21776eaaf94f038250ee9d6a0`  
**Evaluation Benchmark**: Agent Retrieval Benchmark (ARB v2, $N = 345$ positive queries, 25 repositories)  

---

## 1. Executive Charter & Candidate Scope

This document establishes the exact, auditable technical identity for each retrieval candidate evaluated throughout the RepoNeedle research program. A candidate name alone is not evidence of candidate identity. Each candidate's architectural parameters, source files, scoring formulas, graph diffusion topologies, candidate generation constraints, and evaluation hashes are systematically documented below.

The audited candidate systems are:
1. **`CAND-C`**: Frozen Stage 3 baseline candidate.
2. **`CAND-F`**: Stage 3.5 polyglot graph prototype (**formally invalidated**).
3. **`ARM-101-BASE`**: Legitimate RepoNeedle candidate champion.
4. **`BASE-BM25`**: Decoupled Okapi BM25 lexical baseline.
5. **`BASE-REPOMAP`**: Pinned official Aider RepoMap reference.

---

## 2. Systematic Forensic Provenance per Candidate

### 2.1 Candidate C (`CAND-C`)
- **1. Exact Source Commit**: `cd7f3b01e28695f9a9357e0815069e0eae85baca` (Git tag: `stage3-candidate-freeze`).
- **2. Source Files Implementing Architecture**:
  - [`reponeedle/engine.py`](file:///F:/RepoNeedle/reponeedle/engine.py): Ranker implementation in `AblationConfig.candidate_c()`.
  - [`reponeedle/core/lexical.py`](file:///F:/RepoNeedle/reponeedle/core/lexical.py): `BM25Index`.
  - [`reponeedle/core/semantic.py`](file:///F:/RepoNeedle/reponeedle/core/semantic.py): `SubwordSemanticIndex`.
  - [`reponeedle/core/graph.py`](file:///F:/RepoNeedle/reponeedle/core/graph.py): AST import parsing and PageRank diffusion.
  - [`reponeedle/core/abstention.py`](file:///F:/RepoNeedle/reponeedle/core/abstention.py): `SelectiveAbstainer`.
- **3. Configuration Parameters & Values**:
  - Score fusion weights: $W_{\text{bm25}} = 0.3333$, $W_{\text{sem}} = 0.3333$, $W_{\text{graph}} = 0.3333$.
  - Documentation penalty factor: $0.50\times$ penalty applied to documentation paths (`/doc/`, `/docs/`, `.md`, `.rst`, `.txt`).
  - Selective abstention: Enabled (standard vocabulary overlap threshold $0.15$).
- **4. Graph Construction & Diffusion**:
  - Python AST import graph (`import <module>`, `from <module> import <symbol>`).
  - File-level directed graph (`networkx.DiGraph`).
  - Global PageRank with damping $\alpha = 0.85$, single-hop diffusion.
- **5. Lexical Scoring Configuration**:
  - Coupled token-and-path BM25 index. Document length normalization coupled across body and path tokens.
- **6. Semantic Scoring Configuration**:
  - Character n-gram subword semantic index (`SubwordSemanticIndex`, $n \in [3, 5]$). Pure CPU cosine similarity over TF-IDF vectors.
- **7. Candidate Generation & Filtering Policy**:
  - In Stage 3.5: Evaluated with restricted candidate pools (`tests_only` filter for `code2test`, `code_only` for `trace2code`, capping pool to 20 files per task).
  - In Stage 3.8 / 3.15 / 3.18 Canonical Evaluation: Evaluated across the complete unconstrained repository corpus (all files in repository eligible for ranking).
- **8. Context Packing Policy**:
  - Greedy file packing with skeleton compression permitted. Full files packed until budget threshold, then compressed to structural signatures.
- **9. Tokenizer & Budget**:
  - Tiktoken `cl100k_base`. Budgets: 4,000 tokens (4k) and 8,000 tokens (8k).
- **10. Evaluation Harness**:
  - `research/stage3_8/build_canonical_results.py` and `research/stage3_15/generate_stage3_15_reconciliation.py`.
- **11. Dataset & Manifest**:
  - ARB v2 positive query split ($N = 345$ queries across 25 repositories).
- **12. Result Artifacts & SHA-256 Hashes**:
  - Primary result artifact: `research/stage3_8/CANONICAL_PER_QUERY_RESULTS.csv` (SHA-256: `430574460e5339e692c6fbefcc07604b2ee9840d551aeda1e1321981483ad929`).
  - Canonical scoreboard: `research/stage3_15/CANONICAL_SCOREBOARD.csv` (SHA-256: `7fc5dc4be1ec23948a15d8169051a32452f20090dd24d7f3148defc6132f467c`).
  - Unconstrained Performance: **MRR: 0.1399**, **Recall@20: 0.5105**, **P50 Latency: 28.50 ms**.

---

### 2.2 Candidate F (`CAND-F`) — FORMALLY INVALIDATED
- **1. Exact Source Commit**: `4f78cc3658dfb5e338a5458579d38d5d7ef416e8` (Stage 3.5 commit).
- **2. Source Files Implementing Architecture**:
  - [`reponeedle/core/graph.py`](file:///F:/RepoNeedle/reponeedle/core/graph.py): Manifest parsers (`parse_cargo_manifest`, `parse_go_mod`, `parse_package_json`) and polyglot symbol linking.
  - [`reponeedle/core/abstention.py`](file:///F:/RepoNeedle/reponeedle/core/abstention.py): English suffix stemming in `_stem()`.
  - [`reponeedle/engine.py`](file:///F:/RepoNeedle/reponeedle/engine.py): Candidate F ranker configuration.
  - `research/stage3_5/evaluate_graph_retrieval.py`: Evaluation runner.
- **3. Configuration Parameters & Values**:
  - Fusion weights: $W_{\text{bm25}} = 0.3333$, $W_{\text{sem}} = 0.3333$, $W_{\text{graph}} = 0.3333$.
  - Forward callee diffusion weight: $0.25$, reverse caller diffusion weight: $0.20$.
  - Hardcoded Ripgrep strings in commit `4f78cc3`: `"search.rs"`, `"standard.rs"`, and `("core" in my_crate and "printer" in o_crate)` (excised in commit `9a9944a`).
- **4. Graph Construction & Diffusion**:
  - Multi-language manifest-aware call/import graph (Cargo workspaces, Go modules, npm packages).
  - Global PageRank diffusion. Manifest expansion created $27,125$ cross-crate edges in polyglot codebases.
- **5. Lexical Scoring Configuration**:
  - Coupled BM25 index with extracted polyglot regex symbols concatenated directly into document content buffers.
- **6. Semantic Scoring Configuration**:
  - `SubwordSemanticIndex` character n-gram cosine matching.
- **7. Candidate Generation & Filtering Policy**:
  - In Stage 3.5: Synthetic Stage 2 lookup dictionaries with artificial `tests_only` candidate pool restriction for `code2test`.
  - In Stage 3.6 / 3.8 / 3.15 / 3.18 Canonical Evaluation: Complete unconstrained repository corpus.
- **8. Context Packing Policy**:
  - Skeletons permitted with implementation preservation priority.
- **9. Tokenizer & Budget**:
  - Tiktoken `cl100k_base` (4k and 8k token budgets).
- **10. Evaluation Harness**:
  - Originally evaluated in `research/stage3_5/evaluate_graph_retrieval.py`; re-evaluated authoritatively in `research/stage3_6/evaluate_systems.py` and `research/stage3_8/build_canonical_results.py`.
- **11. Dataset & Manifest**:
  - ARB v2 positive query split ($N = 345$ queries across 25 repositories).
- **12. Result Artifacts & SHA-256 Hashes**:
  - Stage 3.5 Claim Artifact: `research/stage3_5/STAGE3_5_REPORT.md` (Claimed MRR: 0.2152).
  - Canonical Full-Corpus Evaluation: `research/stage3_6/CANONICAL_FULL_CORPUS_RESULTS.csv` (SHA-256: `3b46985a538d6df729be59451ba21b1ee45bf383fa14118d7aa648939b4b0fa0`).
  - True Unconstrained Performance: **MRR: 0.1351**, **Recall@20: 0.5078**, **P50 Latency: 32.42 ms**.
  - Invalidation Rationale: Massive PageRank supernode dilution from manifest expansion and BM25 document length inflation caused retrieval performance to collapse by $-37.2\%$, rendering Candidate F statistically significantly worse than standard BM25 ($p = 0.0085$).

---

### 2.3 Candidate Champion: `ARM-101-BASE`
- **1. Exact Source Commit**:
  - Preregistered in commit `809ee6a` (Stage 3.12A), evaluated in `275f0ae` (Stage 3.12), validated in `12142e8` (Stage 3.14), and verified in `461f690` (Stage 3.17).
- **2. Source Files Implementing Architecture**:
  - [`reponeedle/core/lexical.py`](file:///F:/RepoNeedle/reponeedle/core/lexical.py): Decoupled Okapi BM25 engine.
  - [`research/stage3_11/function_graph_engine.py`](file:///F:/RepoNeedle/research/stage3_11/function_graph_engine.py): High-precision AST call-site extractor and Level 1 verified edge builder (`FunctionGraphEngine`).
  - [`research/stage3_14/pilot_attenuation.py`](file:///F:/RepoNeedle/research/stage3_14/pilot_attenuation.py): `ExperimentalLanguageRanker(policy="unattenuated", soft_damping_tau=0.25)`.
  - [`research/stage3_12/run_stage3_12_benchmarks.py`](file:///F:/RepoNeedle/research/stage3_12/run_stage3_12_benchmarks.py): Factorial runner for `ARM-101`.
- **3. Configuration Parameters & Values**:
  - Damping parameter: $\tau = 0.25$ (Soft Lexical Damping).
  - Forward propagation weight: $0.25$.
  - Reverse propagation weight: $0.20$.
  - Graph boost weight: $0.25$.
  - BM25 score weight: $0.60$.
  - Semantic score weight: $0.15$.
  - Documentation filter penalty: $0.50\times$.
  - Hub attenuation: None ($W_{\text{hub}} = 1.0$, unattenuated).
- **4. Graph Construction & Diffusion**:
  - Function-level call graph: AST call-site extraction with identifier scoping.
  - Edge filtering: Level 1 verified call edges only (`allowed = {"verified_call", "unique_global_call", "intra_file_call"}`). Unverified or high-ambiguity call sites are dropped.
  - Depth: Exactly 1 hop from top-3 BM25 seeds.
  - Hub attenuation: None. (Stage 3.14 factorial analysis proved that uniform or language-calibrated hub attenuation harmed or did not improve MRR).
- **5. Soft Lexical Damping Verification**:
  - The implementation is verified in [`research/stage3_14/pilot_attenuation.py`](file:///F:/RepoNeedle/research/stage3_14/pilot_attenuation.py#L143-L151):
    ```python
    s1 = bm25_order[0]
    s2 = bm25_order[1] if n_docs > 1 else s1
    bm25_margin = max(0.0, float(bm25_scores[s1]) - float(bm25_scores[s2]))
    threshold = self.soft_damping_tau * bm25_margin

    best = sorted_by_fused[0]
    if best == s1 or (fused[best] - fused[s1] >= threshold):
        return sorted_by_fused
    else:
        return [s1] + [idx for idx in sorted_by_fused if idx != s1]
    ```
  - This ensures that if the top BM25 candidate has strong lexical margin over the runner-up, a graph neighbor cannot displace it unless its combined fused score exceeds the top candidate by at least $\tau \times \text{margin}$.
- **6. Candidate Generation & Filtering Policy**:
  - Full unconstrained repository corpus (all files eligible for ranking; zero test-only filtering or oracle shortcuts).
- **7. Context Packing Policy**:
  - Token-budget-aware file packing (8k budget) with signature skeleton compression.
- **8. Tokenizer & Budget**:
  - Tiktoken `cl100k_base`, 8,000 tokens.
- **9. Evaluation Harness**:
  - `research/stage3_14/run_stage3_14_experiments.py` and `research/stage3_15/generate_stage3_15_reconciliation.py`.
- **10. Result Artifacts & SHA-256 Hashes**:
  - Per-query results: `research/stage3_14/PER_QUERY_RESULTS.csv` (SHA-256: `ce596bee6e604488afb384a8ff5dd30c1919d2acf6b8fd1e523cfce2a3311eb7`).
  - Runtime and memory: `research/stage3_14/RUNTIME_AND_MEMORY.csv` (SHA-256: `eeeb36c563265c5bc00b6972d789a7e211645bc79bf2bd4520541b59c5fa1208`).
  - Canonical Performance: **MRR: 0.2078**, **Recall@20: 0.5648**, **Token BCY@8k: 0.2822**, **P50 Latency: 12.92 ms**, **P95 Latency: 130.53 ms**.

---

### 2.4 Lexical Baseline: `BASE-BM25`
- **1. Exact Source Commit**: `12142e8` (verified unchanged at HEAD `461f690`).
- **2. Source Files Implementing Architecture**:
  - [`reponeedle/core/lexical.py`](file:///F:/RepoNeedle/reponeedle/core/lexical.py): `BM25Index`.
- **3. Configuration Parameters & Values**:
  - Okapi BM25 parameters: $k_1 = 1.5$, $b = 0.75$.
  - Decoupled scoring: Path terms scored independently from file body tokens to prevent document length dilution.
  - Graph weight: $0.0$, Semantic weight: $0.0$.
- **4. Graph Construction**: None.
- **5. Candidate Generation & Filtering Policy**:
  - Full repository candidate generation across all 25 repositories.
- **6. Context Packing Policy**:
  - Skeletons permitted, 8k token packing.
- **7. Tokenizer & Budget**:
  - Tiktoken `cl100k_base`, 8,000 tokens.
- **8. Evaluation Harness**:
  - `research/stage3_14/run_stage3_14_experiments.py`.
- **9. Result Artifacts & SHA-256 Hashes**:
  - Primary query results: `research/stage3_14/PER_QUERY_RESULTS.csv` (SHA-256: `ce596bee6e604488afb384a8ff5dd30c1919d2acf6b8fd1e523cfce2a3311eb7`).
  - Canonical Performance: **MRR: 0.1752**, **Recall@20: 0.4535**, **Token BCY@8k: 0.2150**, **P50 Latency: 10.24 ms**, **P95 Latency: 116.49 ms**.

---

### 2.5 External Leader Reference: `BASE-REPOMAP`
- **1. Exact Source Commit**: Pinned official Aider repository commit `9e4d689`.
- **2. Source Files Implementing Architecture**:
  - Pinned official Aider repository: `aider/repomap.py` using Tree-sitter symbol extractors and NetworkX PageRank.
- **3. Configuration Parameters & Values**:
  - PageRank damping: $\alpha = 0.85$.
  - Seed personalization: Identifiers extracted from user query statement.
- **4. Graph Construction & Diffusion**:
  - Tree-sitter AST extraction of classes, functions, and references across all supported languages.
  - Global PageRank on identifier reference graph.
- **5. Candidate Generation & Filtering Policy**:
  - Full repository corpus.
- **6. Context Packing Policy**:
  - Definition tag packing into 8k budget.
- **7. Evaluation Harness**:
  - `research/stage3_10/CANONICAL_PER_QUERY_RESULTS.csv` and `research/stage3_14/PER_QUERY_RESULTS.csv`.
- **8. Result Artifacts & SHA-256 Hashes**:
  - Primary query results: `research/stage3_14/PER_QUERY_RESULTS.csv` (SHA-256: `ce596bee6e604488afb384a8ff5dd30c1919d2acf6b8fd1e523cfce2a3311eb7`).
  - Canonical Performance: **MRR: 0.2293**, **Recall@20: 0.6599**, **Token BCY@8k: 0.3177**, **P50 Latency: 180.20 ms**, **P95 Latency: 180.20 ms**.
