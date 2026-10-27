# 🪡 RepoNeedle

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: Passing](https://img.shields.io/badge/tests-25%20passed-brightgreen.svg)]()
[![Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Dataset-RepoNeedle--Bench-blue)](https://huggingface.co/datasets/RepoNeedle/RepoNeedle-Bench)
[![Hugging Face Space](https://img.shields.io/badge/%F0%9F%A4%97%20Space-RepoNeedle--Playground-indigo)](https://huggingface.co/spaces/RepoNeedle/RepoNeedle-Playground)

**RepoNeedle** is an open-source, token-budget-aware repository context retrieval system designed to help AI coding agents discover the most critical files for a coding task under strict context-token constraints.

---

## ⚡ The Upstream Context Problem in AI Coding

Autonomous coding agents (e.g., Claude Code, Aider, OpenHands, Cline) face a severe upstream bottleneck: **Context Acquisition**.

When an agent tackles an issue, bug report, or test failure, passing the entire repository into the prompt is cost-prohibitive or exceeds context windows. Existing approaches face persistent failure modes:
- **Dense Embedding Models**: Rank files without considering file size (tokens), repository topology (call/import graphs), or task intent. They frequently retrieve huge irrelevant files that exhaust the context window.
- **RepoMap / PageRank Centrality**: Heavily prioritizes architectural hubs, but is completely blind to test files (which are leaf nodes with zero in-degree in import graphs) and cannot route specific error frames.
- **Context Bloat & Token Waste**: Studies like ContextBench demonstrate that coding agents pull massive amounts of irrelevant noise into context, degrading reasoning quality via "lost-in-the-middle" effects.
- **Selective Hallucination**: When a query cannot be answered within the repository (e.g. out-of-scope or counterfactual tasks), standard retrievers still force top-$k$ hallucinated files into context instead of abstaining.

RepoNeedle solves this upstream bottleneck by combining:
1. **Multi-Signal Hybrid Scoring**: Field-weighted BM25 + Subword Semantic Vectors + AST Repository Graph Centrality.
2. **Workflow-Adaptive Routing**: Automatic classification of query intent (`trace2code`, `code2test`, `edit2ripple`, `comment2context`, `selective`) with dynamic weight tuning.
3. **Inverted Test-to-Target Mapping**: Dependency graph inversion and naming convention heuristics to locate regression test suites.
4. **Calibrated Selective Abstention**: Peak-to-noise ($Z$-score) and repository symbol overlap gating to abstain from returning noise on counterfactual tasks.
5. **Token-Budget Knapsack Optimization**: Marginal utility density packing ($U_i / C_i^\gamma$) with multi-tier structural skeletons to maximize relevant context yield under hard token limits (2k, 4k, 8k tokens).

---

## 📊 Verified Benchmark Results

Evaluated on **RepoNeedle-Bench** against standard baselines across multiple repositories, including a clean held-out evaluation repository (`tiangolo/fastapi`) with **zero repository leakage**:

| Retrieval System | MRR | Recall@1 | Recall@3 | nDCG@3 | Irrelevant Tokens (4k) | Selective Abstention | Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoMap (PageRank Centrality)** | 0.394 | 0.083 | 0.403 | 0.314 | 926.7 | 0.0% | **0.03 ms** |
| **Dense Semantic Vector** | 0.771 | 0.375 | 0.833 | 0.731 | 926.7 | 0.0% | 0.63 ms |
| **Static Hybrid (BM25+Dense+PR)** | 0.743 | 0.375 | 0.875 | 0.746 | 926.7 | 0.0% | 0.65 ms |
| **BM25 (Sparse Lexical)** | 0.819 | 0.417 | 0.861 | 0.784 | 693.6 | 33.3% | 0.15 ms |
| **RepoNeedle (Adaptive + Budget)** | **0.917** | **0.528** | **1.000** | **0.936** | **581.0** | **100.0%** | 0.80 ms |

### Key Improvements:
- **+11.9% higher MRR** and **+26.6% higher Recall@1** over the strongest baseline (BM25).
- **100% Recall@3** across all positive retrieval tasks.
- **37.3% reduction in irrelevant tokens** (context bloat) compared to Dense Semantic / RepoMap.
- **1.000 MRR on Test Discovery (`code2test`)** vs 0.122 for RepoMap and 0.778 for BM25.
- **100% Selective Abstention Accuracy** on counterfactual/out-of-repo queries.
- **Sub-millisecond execution (< 0.8 ms)** running 100% offline on standard CPU without requiring GPUs.

---

## 🚀 Quickstart & Installation

RepoNeedle is self-contained and requires only standard, battle-tested ML dependencies (`numpy`, `scipy`, `networkx`, `pydantic`, `pathspec`, `rich`).

### 1. Installation

```bash
git clone https://github.com/RepoNeedle/RepoNeedle.git
cd RepoNeedle
pip install -e .
```

### 2. Python API

```python
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import BudgetConfig

# Initialize engine on a local codebase
engine = RepoNeedleEngine.from_directory(
    repo_dir="./my-project",
    budget_config=BudgetConfig(max_tokens=4000, allow_skeletons=True),
)

# 1. Retrieve context for a task
result = engine.retrieve(
    query="Add support for blueprint url_prefix inheritance in route registration",
    budget_tokens=4000,
)

if result.abstained:
    print(f"Abstained: {result.explanation}")
else:
    print(f"Retrieved {len(result.selected_files)} files ({result.total_tokens} tokens):")
    for f in result.selected_files:
        print(f"[{f.tier.value.upper()}] {f.path} (score: {f.score:.3f}, tokens: {f.token_count})")
        # Access full code or structural skeleton
        # print(f.rendered_content)
```

### 3. Command Line Interface (CLI)

```bash
# Retrieve context for a bug report under a 4000 token limit
reponeedle "Fix AttributeError in SecureCookieSessionInterface cookie saving" --repo ./flask --budget 4000

# Explicitly find regression tests for a module
reponeedle "test suite for HTTPBasicAuth" --repo ./requests --task code2test --budget 2000

# Analyze ripple impact of an edit
reponeedle "What files depend on RequestContext?" --repo ./flask --task edit2ripple
```

---

## 🔬 Reproducing Benchmark Results

Run the complete deterministic benchmark suite with a single command:

```bash
python scripts/run_benchmarks.py
```

Results are saved to `benchmarks/results/benchmark_results.json`.

Run the unit test suite:

```bash
python -m pytest -v
```

---

## 📦 Hugging Face Release Artifacts

RepoNeedle distributes its validated assets primarily via Hugging Face:

1. **RepoNeedle-Bench Dataset**: [`hf_artifacts/dataset/`](file:///hf_artifacts/dataset/README.md)
   - Permissively licensed JSONL datasets (`train.jsonl`, `test.jsonl`), schema, and provenance documentation.
2. **RepoNeedle Playground Space**: [`hf_artifacts/space/`](file:///hf_artifacts/space/README.md)
   - Interactive Gradio demonstration allowing side-by-side comparison of RepoNeedle against classical BM25 and RepoMap PageRank.
3. **Automated Publishing Script**: [`scripts/prepare_hf_release.py`](file:///scripts/prepare_hf_release.py)
   - Verified local release package ready to publish with `python scripts/prepare_hf_release.py --token <HF_TOKEN>`.

---

## 🛡️ License & Data Provenance

- **Source Code**: [MIT License](LICENSE)
- **RepoNeedle-Bench**: [MIT License](hf_artifacts/dataset/README.md)
- **Data Provenance**: Sourced exclusively from permissively licensed open-source projects (BSD-3-Clause, Apache-2.0, MIT). **Zero CC BY-NC or copyleft share-alike data is used.** Full manifest available in [`data_provenance/PROVENANCE.md`](data_provenance/PROVENANCE.md).

---

## 📚 Citation

```bibtex
@misc{reponeedle2026,
  author = {RepoNeedle Contributors},
  title = {RepoNeedle: Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI Coding Agents},
  year = {2026},
  publisher = {GitHub},
  howpublished = {\url{https://github.com/RepoNeedle/RepoNeedle}}
}
```
