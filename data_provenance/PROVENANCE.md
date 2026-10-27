# Comprehensive Data & Model Provenance Manifest and Licensing Audit

## Overview
This document tracks the provenance, licensing, versioning, permitted use, and preprocessing steps for all datasets, benchmark corpora, and model architectures examined and used in the **RepoNeedle** project.

RepoNeedle is developed under strict intellectual property, open-source licensing, and ethical compliance guidelines.

---

## 1. Upstream Benchmarks & Artifacts Reviewed

### A. Agent Retrieval Bench
- **Source**: arXiv:2607.24882 (`https://github.com/eyuansu62/agent-retrieval-bench`, HF: `eyuansu71/agent_retrieval_bench`)
- **Authors**: Bowen Qin, Yi Xie (National University of Singapore / Peking University)
- **License**: **MIT License** (Copyright (c) 2026 Agent Retrieval Bench contributors)
- **Permitted Use**: Commercial and non-commercial research, modification, distribution, and reuse.
- **Corpus Licensing Notice**: Repository corpus snapshots in Agent Retrieval Bench remain governed by the respective licenses of their original upstream open-source projects (`fastapi/fastapi` [MIT], `huggingface/transformers` [Apache-2.0], `clap-rs/clap` [Apache-2.0 / MIT], `tokio-rs/tokio` [MIT], `pytest-dev/pytest` [MIT], etc.). Derived files retain their original copyright notices.
- **Role in RepoNeedle**: Official external benchmark for independent validation across `v2_code2test` (106 samples), `v2_comment2context` (80 samples), `v2_trace2code` (101 samples), `v2_edit2ripple` (58 samples), and `v2_abstention` (82 samples).

### B. CORE-Bench
- **Source**: EMNLP 2026 (`https://aclanthology.org/2026.emnlp-main.1604/`, `https://github.com/zhangfw123/CORE-Bench-Eval`)
- **Authors**: Fuwei Zhang, Yanzhao Zhang, Mingxin Li, Dingkun Long, Lexiang Hu, Pengjun Xie, Zhao Zhang, Fuzhen Zhuang
- **License**: **CC BY-NC-SA 4.0** (Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International)
- **Restrictions**: Explicitly forbids commercial reuse, commercial model training, or redistribution under non-ShareAlike terms.
- **RepoNeedle Policy & Decision**: **DO NOT DISTRIBUTE OR BUNDLE**. To protect downstream users and maintain clean MIT licensing, RepoNeedle does not redistribute CORE-Bench data files or models trained on CORE-Bench. Evaluated only conceptually for Level 2 (Issue-to-Edit Localization) and Level 3 (Broader Context Retrieval) task alignment.

### C. ContextBench
- **Source**: `https://contextbench.github.io/`
- **Authors**: ContextBench Research Team (August 2026)
- **Significance**: Empirically proved that coding agents favor recall over precision, wasting large token budgets on irrelevant code (context bloat).
- **Role in RepoNeedle**: Architectural motivation for token-budget knapsack packing with structural skeletons.

### D. ColGrep / ColGrep-Agent-2B
- **Source**: `https://huggingface.co/lightonai/colgrep-agent-2B`
- **Authors**: LightOn AI
- **License**: Apache-2.0
- **Significance**: Demonstrates utility of local token-saving pre-retrieval; however, focused on line-range grep rather than workflow-aware whole-repo budget packing.

### E. Aider RepoMap
- **Source**: `https://github.com/paul-gauthier/aider`
- **Author**: Paul Gauthier
- **License**: Apache-2.0
- **Significance**: Tree-sitter / AST symbol graph + PageRank centrality.

---

## 2. Benchmark Corpus Separation & Licensing

RepoNeedle strictly separates **Official External Benchmarks** from **Synthetic Demonstration Benchmarks**:

### Split 1: Official Agent Retrieval Bench (External)
- **Sample Count**: 35 samples in v0.1 release (17 `code2test`, 16 `comment2context`, 2 `trace2code`); 287 samples in full ablation release.
- **Repositories**: 12 to 25 real open-source GitHub repositories at frozen base commits.
- **License**: Evaluator is MIT. Upstream files retain original licenses.

### Split 2: Synthetic Demonstration Benchmark (`RepoNeedle-Bench-Synthetic`)
- **Sample Count**: 15 samples (10 development samples, 5 held-out evaluation samples).
- **Repositories**:
  | Repository | Upstream License | Origin | Tasks |
  | :--- | :--- | :--- | :--- |
  | `pallets/flask` | BSD-3-Clause | `https://github.com/pallets/flask` | `trace2code`, `code2test`, `edit2ripple`, `comment2context`, `selective` |
  | `psf/requests` | Apache-2.0 | `https://github.com/psf/requests` | `trace2code`, `code2test`, `edit2ripple`, `comment2context`, `selective` |
  | `tiangolo/fastapi` (Held-out) | MIT | `https://github.com/tiangolo/fastapi` | `trace2code`, `code2test`, `edit2ripple`, `comment2context`, `selective` |

---

## 3. License Matrix and Derivation Notice

| Asset | Primary License | Upstream Origin | Permitted Downstream Use |
| :--- | :--- | :--- | :--- |
| **RepoNeedle Engine Source Code** | **MIT License** | Original implementation | Unrestricted commercial & non-commercial use |
| **RepoNeedle Tests & Runners** | **MIT License** | Original implementation | Unrestricted |
| **RepoNeedle-Bench (Synthetic)** | **MIT License** | Curated from BSD/Apache/MIT repos | Unrestricted |
| **Agent Retrieval Bench Evaluator** | **MIT License** | `eyuansu62/agent-retrieval-bench` | Attributed to ARB contributors |
| **CORE-Bench** | **CC BY-NC-SA 4.0** | `zhangfw123/CORE-Bench-Eval` | **Excluded from release** |

*Notice: In compliance with open-source licensing principles, derived code and repository snapshots retain their original copyright notices. Derivative works do not overwrite or replace upstream licenses.*
