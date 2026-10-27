# RepoNeedle Research & Engineering Roadmap

This roadmap is grounded in empirical limitations observed during benchmark evaluations and practical deployments.

---

## Current Status (v0.1.0) - Completed & Validated
- [x] Multi-signal hybrid retrieval (Field-weighted BM25 + Subword Semantic Vectors + AST Repository Graph).
- [x] Workflow-adaptive routing (`trace2code`, `code2test`, `edit2ripple`, `comment2context`, `selective`).
- [x] Inverted test-to-target dependency mapping for `code2test` regression test discovery.
- [x] Calibrated selective abstention engine for no-gold and out-of-repo queries.
- [x] Token-budget knapsack packing with multi-tier structural skeletons.
- [x] Zero-network, offline CPU execution under 1 ms latency.
- [x] Reproducible benchmark suite with clean repository-level held-out split (`RepoNeedle-Bench`).
- [x] 100% test coverage across core modules.
- [x] Hugging Face release assets (Dataset Card, Gradio Playground Space).

---

## Phase 2: Multi-Language & Protocol Integration (Q1 2027)
- [ ] **Tree-sitter & SCIP Indexing**:
  - Add optional Tree-sitter parsers for TypeScript, Go, Rust, Java, and C++ to extend deep AST symbol graphs beyond Python.
  - Implement SCIP (Source Code Intelligence Protocol) index ingest for enterprise codebases.
- [ ] **Dynamic Dependency Tracking**:
  - Ingest optional pytest / coverage runtime trace logs (`.coverage` or test execution logs) to bridge dynamic dispatch and reflection.
- [ ] **Third-Party Package Boundary Disambiguation**:
  - Refine selective abstention to detect when an issue belongs in an external upstream library (e.g., `urllib3` vs `requests`) using `pip freeze` / `pyproject.toml` dependency parsing.

---

## Phase 3: Agent Scaffolding & Framework Adapters (Q2 2027)
- [ ] **Aider Adapter**: Drop-in replacement for Aider's RepoMap to enable workflow routing and test discovery.
- [ ] **SWE-bench / OpenHands / Cline Integration**: MCP (Model Context Protocol) server wrapping RepoNeedle for one-click installation into coding assistants.
- [ ] **Disk-Backed Inverted Indexing**:
  - Add optional embedded DuckDB / SQLite backing for giant monorepos (> 100,000 files).
