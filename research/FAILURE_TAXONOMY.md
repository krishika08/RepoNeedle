# FAILURE TAXONOMY AND ERROR DIAGNOSTICS: REPONEEDLE

**Document ID**: `FT-2026-001`  
**Dataset**: Full Agent Retrieval Bench v2 ($N=427$ samples: 345 positive, 82 selective)  
**Evaluation Date**: 2026-10-28  
**Author**: Principal Retrieval Researcher & Lead Systems Engineer  

---

## 1. High-Level Empirical Summary

Out of 345 positive retrieval queries on frozen repository candidate pools:
- **Zero-Gold Hits (Complete Retrieval Failure)**: 0 / 345 (0.0% — at least one gold file was identified in every sample)
- **Queries Regressing against BM25**: 179 / 345 (51.9%)
- **Queries Regressing against RepoMap**: 197 / 345 (57.1%)

Out of 82 selective abstention queries:
- **Correct Abstentions**: **0 / 82 (0.0% accuracy)**
- **False Return Rate (Returning Noise on No-Gold Tasks)**: **82 / 82 (100.0%)**

---

## 2. Per-Task Empirical Diagnostics

| Task Track | Samples ($N$) | RepoNeedle MRR | RepoMap MRR | BM25 MRR | RN R@20 | RM R@20 | Head-to-Head vs RM | Head-to-Head vs BM25 | Primary Failure Mechanism |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`code2test`** | 106 | **0.2660** | 0.1942 | 0.1057 | 0.5931 | 0.5572 | +46 / -53 (7 ties) | +62 / -41 (3 ties) | Non-standard test directory conventions |
| **`comment2context`**| 80 | 0.1708 | 0.1532 | **0.1974** | 0.2083 | 0.4688 | +24 / -52 (4 ties) | +16 / -57 (7 ties) | Documentation distractor files crowding code |
| **`trace2code`** | 101 | 0.2337 | **0.2723** | 0.1638 | 0.4092 | **0.8465** | +27 / -66 (8 ties) | +40 / -57 (4 ties) | Graph diffusion failure on core architectural hubs |
| **`edit2ripple`** | 58 | 0.2320 | **0.2323** | 0.1536 | 0.4612 | 0.6121 | +25 / -26 (7 ties) | +30 / -24 (4 ties) | Inward callers vs outward dependencies confusion |

---

## 3. Five Major Architectural Failure Categories

### Failure Category 1: Documentation Distractor Pollution (`comment2context`)
- **Observed Behavior**: On high-level issue comment queries, BM25 beat RepoNeedle on 57 out of 80 tasks (+16 / -57).
- **Mechanistic Root Cause**: RepoNeedle indexes all text files, including `Documentation/`, `docs/`, and markdown files (`.md`, `.rst`). Issue comments are written in conversational prose (e.g. asking how to triage an issue or configure a client). Files like `Documentation/contributor-guide/triage_issues.md` or `docs/testing.rst` share dense vocabulary with the query. Because RepoNeedle splits score weights between lexical, subword-semantic, and graph, the document files receive top-1 to top-3 ranks, displacing the actual implementation source files.
- **Representative Case**:
  - Sample ID: `d5f1198f6fb5e19244fd4ac7` (`etcd-io/etcd`)
  - Gold Target: `['server/etcdserver/txn/txn_test.go', 'server/storage/mvcc/index_test.go']`
  - RepoNeedle Top 3: `['Documentation/contributor-guide/triage_issues.md', 'server/storage/mvcc/kv.go', ...]`
  - RepoNeedle MRR: `0.1250` vs BM25 MRR: `0.3333`
- **Actionable Countermeasure**: Implement content-type gating and path-penalty priors for non-code assets (`docs/`, `.rst`, `.md`) during code retrieval unless explicitly requested.

### Failure Category 2: Disconnected Component & Centrality Deficit (`trace2code`)
- **Observed Behavior**: RepoMap drastically outperformed RepoNeedle on `trace2code` at high recall (RepoMap Recall@20 was `0.8465` vs RepoNeedle `0.4092`), beating RepoNeedle on 66 out of 101 queries (+27 / -66).
- **Mechanistic Root Cause**: In repositories like `pallets/click`, the central hub file `src/click/core.py` is referenced by virtually every command decorator, test, and type parser. When a stack trace contains an error from an outer test or handler, RepoNeedle matches the immediate error line or test options, while RepoMap's PageRank spreads probability mass across the entire inward reference graph, guaranteeing that core files (`core.py`, `app.py`) appear in top 20. RepoNeedle's local AST graph lacks global PageRank diffusion.
- **Representative Case**:
  - Sample ID: `08d24e63e480c9447082ccfb` (`pallets/click`)
  - Gold Target: `['src/click/core.py']`
  - RepoNeedle Top 3: `['tests/test_options.py', 'tests/test_arguments.py', 'tests/test_basic.py']` (MRR: `0.0101`)
  - RepoMap Top 3: `['tests/test_options.py', 'src/click/core.py', 'tests/test_commands.py']` (MRR: `0.5000`)
- **Actionable Countermeasure**: Add multi-hop inward graph diffusion (personalized PageRank) to propagate score from matched perimeter frames to architectural hub implementations.

### Failure Category 3: Total Collapse of Heuristic Selective Abstention
- **Observed Behavior**: 0 out of 82 no-gold queries were correctly abstained (100% false return rate).
- **Mechanistic Root Cause**:
  - The `SelectiveAbstainer` computes confidence as $C = 0.5 \cdot Z_{\text{norm}} + 0.5 \cdot \text{Overlap}$.
  - The calibrated threshold was $\tau = 0.38$.
  - Across the 82 benchmark samples, observed confidence scores ranged strictly from **`0.5321` to `0.8908`** (mean `0.7578`).
  - *Natural Issues Contain Repo Terms*: Bug reports on `pytest-dev/pytest` or `etcd-io/etcd` describe valid repo symbols (e.g. `FixtureManager`, `watchable_store`), producing high overlap even when the root bug is in an external dependency.
  - *Counterfactual Queries Contain Generic Code Terms*: Queries from other projects contain `parse`, `client`, `error`, `config`, `handler`, which inevitably match dozens of identifiers in large repos, driving $Z$-scores well above 2.0.
- **Actionable Countermeasure**: Surface lexical statistics cannot solve selective abstention. A trained neural cross-encoder discriminator or semantic entailment gate is mandatory for safe selective retrieval.

### Failure Category 4: Deep Rust AST Parsing & Multi-Crate Partitioning (`clap-rs/clap`, `astral-sh/ruff`)
- **Observed Behavior**: On `astral-sh/ruff` ($N=6$), RepoNeedle MRR was `0.0017` and Recall@20 was `0.0000`. On `clap-rs/clap` ($N=10$), RepoNeedle MRR was `0.0869` vs RepoMap `0.3252`.
- **Mechanistic Root Cause**: Multi-crate Rust workspaces (e.g. `clap_builder`, `clap_derive`, `clap_mangen`) distribute functionality across nested `Cargo.toml` packages. RepoNeedle's regex-based AST parser extracted fewer symbols from Rust macro definitions (`proc_macro_derive`) and failed to resolve inter-crate dependencies that tree-sitter or RepoMap successfully trace.
- **Actionable Countermeasure**: Implement multi-language tree-sitter AST parsing or dedicated crate-level manifest resolvers for Rust and Go.

### Failure Category 5: Context Saturation & Monolithic File Crowding
- **Observed Behavior**: In large codebases (e.g. `etcd`, `transformers`), single implementation files often exceed 2,500 lines (e.g. `server.go`, `modeling_bert.py`).
- **Mechanistic Root Cause**: When greedy knapsack packing includes a 3,000-line file in `FULL` tier, it consumes ~5,000 tokens out of an 8,000 token budget, leaving room for only 1 or 2 supporting files and causing Recall@10 and Recall@20 to truncate prematurely.
- **Actionable Countermeasure**: Implement block-level / function-level context extraction so that monolithic files only contribute relevant sub-classes or methods rather than occupying the entire context window.

---

## 4. Repository-Specific Performance Matrix

| Repository | Samples ($N$) | Primary Language | RepoNeedle MRR | RepoMap MRR | BM25 MRR | RN Recall@20 | RM Recall@20 | Verdict / Action |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `gin-gonic/gin` | 88 | Go | **0.3231** | 0.2886 | 0.1934 | 0.6231 | **0.8807** | Strong MRR lead; lags RM on tail recall |
| `etcd-io/etcd` | 41 | Go | **0.2672** | 0.2249 | 0.1625 | 0.3098 | **0.5037** | Strong MRR lead; doc distractors in comments |
| `tokio-rs/tokio` | 38 | Rust | 0.1852 | **0.2397** | 0.2025 | 0.4452 | **0.6206** | RepoMap leads; async trait graph traversal needed |
| `huggingface/transformers`| 36 | Python | **0.2697** | 0.1896 | 0.1603 | 0.4861 | **0.6296** | RepoNeedle leads by +42.2% on MRR |
| `pallets/click` | 26 | Python | 0.0746 | **0.2949** | 0.1302 | 0.1538 | **0.9872** | **Severe failure**: RepoMap PageRank dominates |
| `vitejs/vite` | 25 | TypeScript | **0.1787** | 0.0316 | 0.0341 | **0.4733** | 0.1333 | **Massive win**: RepoNeedle beats all baselines 5x |
| `huggingface/diffusers` | 16 | Python | **0.2878** | 0.1245 | 0.0600 | **0.3854** | 0.3750 | **Massive win**: +131% MRR over RepoMap |
| `caddyserver/caddy` | 13 | Go | **0.3157** | 0.3129 | 0.1989 | 0.4744 | **0.6538** | Parity with RepoMap; both beat BM25 |
| `clap-rs/clap` | 10 | Rust | 0.0869 | **0.3252** | 0.0780 | 0.3000 | **0.6667** | RepoMap leads; multi-crate cargo links missing |
| `spring-projects/spring-boot`| 8 | Java | **0.2733** | 0.1764 | 0.1513 | **0.6667** | 0.4792 | RepoNeedle leads on Java codebase |
| `pytest-dev/pytest` | 7 | Python | 0.1445 | 0.1628 | **0.1748** | 0.1190 | **0.3333** | Dynamic test fixtures defeat static AST |
| `vuejs/core` | 6 | TypeScript | **0.1447** | 0.0540 | 0.0363 | **0.5833** | **0.5833** | RepoNeedle leads 2.7x on TypeScript |
| `astral-sh/ruff` | 6 | Rust | 0.0017 | 0.0436 | **0.0897** | 0.0000 | **0.3333** | Macro-generated AST symbols unparsed |

