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
- **Dense Embedding Models**: Rank files without considering file size (tokens), repository topology (call/import graphs), or task intent. They frequently retrieve large, irrelevant files that exhaust the context window.
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

## 📊 Benchmark Validation

To maintain strict scientific integrity, **Official External Benchmark Results** are reported separately from **Synthetic Demonstration Benchmark Results**. Dataset sizes and query counts ($N$) are explicitly documented for every measurement.

---

### Part A: Official Agent Retrieval Bench (ARB) Results

Evaluated directly using the official `agent_retrieval_bench` evaluation package (`agent_retrieval_bench.baseline.sample_metrics`) on the official **Agent Retrieval Bench** release ($N=35$ samples across 12 real open-source GitHub repositories at frozen base commits):

| Task Track | Sample Count ($N$) | Metric | Official Lexical | Official BM25 | RepoNeedle | Relative Gain vs BM25 |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| **Overall** | $N=35$ | **MRR** | 0.708 | 0.748 | **0.879** | **+17.5%** |
| | | Recall@5 | 0.919 | 0.954 | **0.990** | +3.8% |
| | | Recall@10 | 0.970 | 0.975 | **1.000** | +2.6% |
| | | Gold Coverage@8k | 1.000 | 1.000 | **1.000** | Parity |
| **`code2test`** | $N=17$ | **MRR** | 0.399 | 0.550 | **0.824** | **+49.8%** |
| | | Recall@5 | 0.832 | 0.906 | **0.980** | +8.2% |
| | | Recall@10 | 0.939 | 0.949 | **1.000** | +5.4% |
| **`comment2context`** | $N=16$ | **MRR** | **1.000** | 0.958 | 0.953 | -0.5% |
| | | Recall@5 | 1.000 | 1.000 | **1.000** | Parity |
| **`trace2code`** | $N=2$ | **MRR** | **1.000** | 0.750 | 0.750 | Parity |
| | | Recall@5 | 1.000 | 1.000 | **1.000** | Parity |

*Reference Baseline Context from ARB Full Release ($N=287$ samples across 25 repositories, `candidate_filter=code_only`):*
- **ARB Official RepoMap**: Overall MRR: `0.228`, `code2test` MRR: `0.228`, `comment2context` MRR: `0.159`, `trace2code` MRR: `0.283`.
- **ARB Official Lexical**: Overall MRR: `0.162`, `code2test` MRR: `0.079`, `comment2context` MRR: `0.161`, `trace2code` MRR: `0.250`.

---

### Part B: Component Ablation Study & Confidence Intervals

Conducted across all 15 benchmark tasks (12 positive, 3 selective) using **1,000 bootstrap resamples** to compute 95% Confidence Intervals for MRR:

| System / Ablation | Overall MRR | 95% Bootstrap CI | Dev MRR ($N=8$) | Held-out MRR ($N=4$) | Recall@1 | Recall@3 | Wasted Tokens (4k) | Selective Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full RepoNeedle** | **0.917** | **[0.792, 1.000]** | **1.000** | **0.750** | **0.528** | **1.000** | **581** | **100.0%** |
| *w/o WorkflowRouter* | 0.743 | [0.569, 0.903] | 0.844 | 0.542 | 0.375 | 0.875 | 700 | 100.0% |
| *w/o SelectiveAbstainer* | 0.917 | [0.792, 1.000] | 1.000 | 0.750 | 0.528 | 1.000 | 807 | 0.0% |
| *w/o Skeletons (Full only)* | 0.917 | [0.792, 1.000] | 1.000 | 0.750 | 0.528 | 1.000 | 581 | 100.0% |
| **Baseline: Static Hybrid** | 0.743 | [0.569, 0.903] | 0.844 | 0.542 | 0.375 | 0.875 | 927 | 0.0% |
| **Baseline: BM25 Only** | 0.819 | [0.667, 0.958] | 0.938 | 0.583 | 0.417 | 0.861 | 694 | 33.3% |
| **Baseline: Dense Semantic** | 0.771 | [0.604, 0.917] | 0.781 | 0.750 | 0.375 | 0.833 | 927 | 0.0% |
| **Baseline: RepoMap Only** | 0.394 | [0.249, 0.577] | 0.448 | 0.286 | 0.083 | 0.403 | 927 | 0.0% |

#### Key Ablation Findings:
1. **Router Impact**: Removing `WorkflowRouter` causes a **-19.0% relative drop in MRR** (0.917 down to 0.743) and lowers Recall@3 from 1.000 to 0.875, demonstrating that task-adaptive routing is essential.
2. **Abstainer Impact**: Disabling `SelectiveAbstainer` drops Selective Accuracy to **0.0%**, increasing wasted context tokens by **+38.9%** (581 up to 807 tokens).
3. **Held-out MRR Parity Analysis**: On the held-out FastAPI split ($N=4$ positive tasks), both RepoNeedle and Dense Semantic achieve MRR 0.750. Diagnostic analysis revealed:
   - On `trace2code` and `comment2context`, both achieve reciprocal rank 1.000 or 0.500.
   - On `code2test`, RepoNeedle outperforms Dense Semantic (RR: 1.000 vs 0.500).
   - On `edit2ripple`, RepoNeedle ranks `tests/test_routing.py` (an imported dependent) ahead of `fastapi/__init__.py`.
   - On the selective task, Dense Semantic hallucinates 3 files (0% accuracy), while RepoNeedle achieves 100% accuracy with zero wasted tokens.

---

### Part C: Actual Content Payload Reduction & Latency Verification

Verified using exact byte, character, word, and BPE code tokenization:

| Metric | Full File Content | Structural Skeleton | Actual Savings |
| :--- | :---: | :---: | :---: |
| **Raw Characters** | 8,255 | 1,252 | **84.8% reduction** |
| **Whitespace Words** | 721 | 148 | **79.5% reduction** |
| **BPE Code Tokens** | 3,030 | 442 | **85.4% reduction** |
| **Estimated Tokens** | 1,585 | 266 | **83.2% reduction** |

#### Latency Statistics (100 Warmed Iterations across 33 repository files on standard CPU):
- **Mean Latency**: `0.635 ms` ($\pm 0.098\text{ ms}$)
- **Median (p50)**: `0.613 ms`
- **95th Percentile (p95)**: `0.841 ms`
- **99th Percentile (p99)**: `1.005 ms`

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

Run the complete deterministic benchmark suite with single commands:

```bash
# 1. Run Official Agent Retrieval Bench evaluation (v0.1, N=35)
python benchmarks/run_arb_official_eval.py

# 2. Run Component Ablation Study with 95% Bootstrap CI
python benchmarks/run_ablations.py

# 3. Verify actual BPE token payload reduction and latency
python scripts/verify_token_savings_and_latency.py

# 4. Run automated unit test suite (25 tests)
pytest -v
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
- **Upstream Notices**: Agent Retrieval Bench is Copyright (c) 2026 Agent Retrieval Bench contributors (MIT License). All upstream open-source code snapshots retain their original licenses and copyright notices.

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
