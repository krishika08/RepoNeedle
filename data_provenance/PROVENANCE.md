# Data & Model Provenance Manifest

## Overview
This document tracks the provenance, licensing, versioning, permitted use, and preprocessing steps for all datasets, benchmark corpora, and model architectures examined and used in the **RepoNeedle** project.

RepoNeedle is developed under strict intellectual property, open-source licensing, and ethical compliance guidelines.

---

## 1. External Benchmarks & Artifacts Reviewed

### A. CORE-Bench
- **Source**: EMNLP 2026 (`https://aclanthology.org/2026.emnlp-main.1604/`, `https://github.com/zhangfw123/CORE-Bench-Eval`)
- **Authors**: Fuwei Zhang, Yanzhao Zhang, Mingxin Li, Dingkun Long, Lexiang Hu, Pengjun Xie, Zhao Zhang, Fuzhen Zhuang
- **License**: **CC BY-NC-SA 4.0** (Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International)
- **Permitted Use**: Academic research and evaluation only.
- **Restrictions**: Explicitly forbids commercial reuse, commercial model training, or redistribution under non-ShareAlike terms.
- **RepoNeedle Policy & Decision**: **DO NOT INCLUDE OR REDISTRIBUTE**. RepoNeedle does not use CORE-Bench data for model training, nor does it bundle CORE-Bench data in its releases. All benchmark samples in RepoNeedle are sourced independently from permissively licensed (MIT / Apache 2.0 / BSD) repositories.

### B. Agent Retrieval Bench
- **Source**: arXiv:2607.24882 (`https://github.com/eyuansu62/agent-retrieval-bench`)
- **Authors**: Bowen Qin, Yi Xie (NUS / PKU)
- **License**: **MIT License**
- **Permitted Use**: Commercial and non-commercial research, modification, distribution, and reuse.
- **Significance**: Identifies the 4 workflow tasks (`code2test`, `comment2context`, `trace2code`, `edit2ripple`) and selective retrieval calibration gap.
- **RepoNeedle Policy & Decision**: Used as reference methodology and benchmark schema architecture.

### C. ContextBench
- **Source**: `https://contextbench.github.io/`
- **Scope**: 1,136 tasks across 66 repositories; measures context recall vs precision and context waste.
- **Significance**: Confirmed that coding agents waste tokens on irrelevant files; token-budget optimization is crucial.
- **RepoNeedle Policy & Decision**: Used as architectural motivation for token-budget knapsack packing.

### D. ColGrep / ColGrep-Agent-2B
- **Source**: `https://huggingface.co/lightonai/colgrep-agent-2B`
- **Authors**: LightOn AI
- **License**: Apache 2.0
- **Significance**: Demonstrates utility of local token-saving pre-retrieval; however, focused on line-range grep rather than workflow-aware whole-repo budget packing.

### E. Aider RepoMap
- **Source**: `https://github.com/paul-gauthier/aider`
- **License**: Apache 2.0
- **Significance**: Tree-sitter / AST symbol graph + PageRank.
- **Weakness Analyzed**: PageRank favors central architectural hubs and penalizes leaf nodes (such as unit/regression tests in `code2test`), and has no semantic awareness or selective abstention mechanism.

---

## 2. RepoNeedle-Bench Dataset Composition

RepoNeedle-Bench is built entirely from permissively licensed open-source Python repositories (MIT and Apache 2.0).

| Repository | Source License | Upstream Origin | Task Coverage |
| :--- | :--- | :--- | :--- |
| **pallets/flask** | BSD-3-Clause | `https://github.com/pallets/flask` | `code2test`, `comment2context`, `trace2code`, `edit2ripple` |
| **psf/requests** | Apache-2.0 | `https://github.com/psf/requests` | `code2test`, `comment2context`, `trace2code`, `edit2ripple` |
| **tiangolo/fastapi** | MIT | `https://github.com/tiangolo/fastapi` | `code2test`, `comment2context`, `trace2code`, `edit2ripple` |
| **encode/httpx** | BSD-3-Clause | `https://github.com/encode/httpx` | `code2test`, `comment2context`, `trace2code`, `edit2ripple` |
| **marshmallow-code/marshmallow** | MIT | `https://github.com/marshmallow-code/marshmallow` | `code2test`, `comment2context`, `trace2code`, `edit2ripple` |
| **Selective Negative Controls** | MIT / Synthetic | Synthetic counterfactuals & cross-repo distractors | `selective` (abstention / out-of-repo) |

### Permitted Use
The entire RepoNeedle-Bench dataset is released under the **MIT License**, permitting unrestricted downstream research, development, and commercial integration.
