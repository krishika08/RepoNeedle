# RepoNeedle Stage 3.20 — ARM-101 Research-to-Production Architectural Map

This document defines the exact structural mapping from the experimental prototype scripts to the clean, production-grade components in `reponeedle/`.

---

## 1. Component Mapping Table

| Research Prototype Component | Location in `research/` | Production Module in `reponeedle/` | Architectural Responsibility |
| :--- | :--- | :--- | :--- |
| **`FunctionGraphEngine`** | `research/stage3_11/function_graph_engine.py` | `reponeedle/core/function_graph.py` | Extracts function symbols, call sites, resolves qualified/unqualified calls, builds fine-grained call graph. |
| **`ExperimentalLanguageRanker`** | `research/stage3_14/pilot_attenuation.py` | `reponeedle/core/arm101.py` | Implements seed selection, forward/reverse diffusion, degree normalization, score fusion, and soft lexical damping ($\tau=0.25$). |
| **`detect_file_language` & `compute_hub_attenuation`** | `research/stage3_14/pilot_attenuation.py` | `reponeedle/core/attenuation.py` | Language detection and hub attenuation policies (`unattenuated`, `uniform_log2`, `lang_calibrated`). |
| **`CascadedRanker`** | `reponeedle/core/cascade.py` | `reponeedle/core/cascade.py` | Preserved for `CONTROL-CASCADE` ablation; refactored to share common graph structures. |
| **Ranker Selector & Engine Routing** | Embedded in research eval scripts | `reponeedle/engine.py` (`ranker="legacy"\|"bm25"\|"arm101"`) | Selects ranker behind explicit configuration flag in `RepoNeedleEngine.retrieve()`. |
| **CLI Argument Configuration** | None (CLI ran legacy only) | `reponeedle/cli.py` (`--ranker`) | Exposes `--ranker` flag with choices `["legacy", "bm25", "arm101"]`. |
| **Ablation / Retrieval Config** | `research/stage3_12/factorial_engine.py` | `reponeedle/models.py` (`RetrievalConfig`) | Structured dataclass for ranker parameters, soft damping tau, weights, and timeouts. |

---

## 2. Invariants & Migration Principles

1. **No Circular Dependencies:**
   - `reponeedle/core/function_graph.py` depends only on `reponeedle/models.py`.
   - `reponeedle/core/arm101.py` depends on `function_graph.py`, `models.py`, and `attenuation.py`.
   - `reponeedle/engine.py` imports rankers and coordinates indices.
2. **Deterministic Output:**
   - All dictionary traversals and set operations are sorted by path / symbol name to ensure bit-level deterministic tie-breaking.
3. **Graceful Degradation:**
   - If an unsupported language file is encountered, symbol extraction returns empty lists without throwing.
   - If a repository has 0 function edges, ARM-101 gracefully reduces to BM25 + subword ranking with soft damping.
4. **Zero Impact on Existing Defaults:**
   - The default `ranker` setting in `RepoNeedleEngine.retrieve(...)` remains `"legacy"` or respects user config until Stage 3.20 parity certification is complete.
