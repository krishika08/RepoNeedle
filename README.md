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

| Task Track | Sample Count ($N$) | Metric | Official Lexical | Official RepoMap | Official BM25 | RepoNeedle | Relative Gain vs BM25 |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **Overall** | $N=35$ | **MRR** | 0.708 | 0.708 | 0.748 | **0.879** | **+17.5%** |
| | | Recall@5 | 0.919 | 0.924 | 0.954 | **0.990** | +3.8% |
| | | Recall@10 | 0.970 | 0.981 | 0.975 | **1.000** | +2.6% |
| | | Gold Coverage@8k | 1.000 | 1.000 | 1.000 | **1.000** | Parity |
| **`code2test`** | $N=17$ | **MRR** | 0.399 | 0.458 | 0.550 | **0.824** | **+49.8%** |
| | | Recall@5 | 0.832 | 0.843 | 0.906 | **0.980** | +8.2% |
| | | Recall@10 | 0.939 | 0.961 | 0.949 | **1.000** | +5.4% |
| **`comment2context`** | $N=16$ | **MRR** | **1.000** | 0.969 | 0.958 | 0.953 | -0.5% |
| | | Recall@5 | 1.000 | 1.000 | 1.000 | **1.000** | Parity |
| **`trace2code`** | $N=2$ | **MRR** | **1.000** | 0.750 | 0.750 | 0.750 | Parity |
| | | Recall@5 | 1.000 | 1.000 | 1.000 | **1.000** | Parity |

#### Paired Difference Statistical Significance (N=35 Identical Queries)

| Paired Comparison | Mean Difference ($\bar{\Delta}_{\text{MRR}}$) | 95% Bootstrap CI ($\Delta$) | Paired $t$-test $p$-value | Wilcoxon $p$-value | Wins / Ties / Losses | Statistically Significant ($\alpha=0.05$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoNeedle vs Official BM25** | **+0.1306** | **[+0.0610, +0.2044]** | **$p = 0.0014$** | $p = 0.0076$ | **10 / 24 / 1** | **YES ($p < 0.01$)** |
| **RepoNeedle vs Official RepoMap** | **+0.1704** | **[+0.0911, +0.2513]** | **$p = 0.0003$** | $p = 0.0022$ | **13 / 21 / 1** | **YES ($p < 0.001$)** |
| **RepoNeedle vs Official Lexical** | **+0.1704** | **[+0.0624, +0.2700]** | **$p = 0.0034$** | $p = 0.0042$ | **15 / 18 / 2** | **YES ($p < 0.01$)** |

> [!NOTE]
> *Cross-Release Integrity Notice*: The 35-sample ARB v0.1 scores above are measured on identical frozen candidate sets. In the full 287-sample ARB v1.1 candidate-filter ablation benchmark (where candidate pools span entire repositories of thousands of files), official reported baseline scores are: **RepoMap**: MRR `0.228`, Recall@5 `0.328`; **Lexical**: MRR `0.162`, Recall@5 `0.214`. Scores across different candidate pool granularities are not directly comparable.

---

### Part B: Official ARB Selective Abstention Pilot ($N=82$ Samples)

Evaluated on the official Agent Retrieval Bench Abstention Pilot (`external/agent-retrieval-bench/data/benchmark/v2_abstention_pilot/abstention.jsonl`):

| Abstention Category | Sample Count ($N$) | Correctly Abstained | Return Rate (False Positives) | Abstention Accuracy |
| :--- | :---: | :---: | :---: | :---: |
| **Upstream Dependency** | 41 | 36 | 5 (12.2%) | **87.8%** |
| **Counterfactual Wrong-Repo** | 32 | 30 | 2 (6.2%) | **93.8%** |
| **External Service Failure** | 7 | 7 | 0 (0.0%) | **100.0%** |
| **User Configuration Error** | 2 | 2 | 0 (0.0%) | **100.0%** |
| **Total No-Gold Pilot** | **82** | **75** | **7 (8.5%)** | **91.5%** |

*Baseline Comparison*: Without calibrated threshold gating, classical BM25 and Lexical rankers return the top-$k$ matches unconditionally for 100% of queries, suffering a **100% false return rate (0% abstention recall)** on no-gold tasks.

---

### Part C: Component Ablation Study & Confidence Intervals

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

### Part D: Multi-Scale Token Payload Reduction & Latency Verification

#### 1. Actual Content Payload Reduction Across Multiple Languages & File Sizes

Measured using exact BPE code subword regex (`re.compile(r"[A-Za-z0-9_]+|[^\s\w]|\n|\s+")`, calibrated to OpenAI cl100k / LLaMA / Qwen tokenizers):

| Corpus File & Language | Lines | Full BPE Tokens | Skeleton BPE Tokens | Actual BPE Token Savings | Character Savings | Architectural Symbols Preserved |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Python (Short)** | 50L | 280 | 280 | 0.0% *(fits budget)* | 0.0% | **YES** (Complete) |
| **Python (Medium Adapter)** | 250L | 2,060 | 305 | **85.2% reduction** | 85.8% reduction | **YES** (Class, methods, docstrings) |
| **Python (Long Session Mgr)** | 700L | 4,061 | 404 | **90.1% reduction** | 90.0% reduction | **YES** (Class, methods, TTL logic) |
| **Rust (Async RingBuffer)** | 200L | 2,312 | 222 | **90.4% reduction** | 91.1% reduction | **YES** (Struct, impl, fn signatures) |
| **TypeScript (EventDispatcher)** | 200L | 1,920 | 455 | **76.3% reduction** | 74.6% reduction | **YES** (Interface, class, methods) |
| **Go (HTTP Trie Router)** | 200L | 1,225 | 578 | **52.8% reduction** | 44.2% reduction | **YES** (Types, struct, methods) |

#### 2. Multi-Scale Retrieval Latency Distribution (100 Warmed Iterations per Scale on CPU)

Retrieval latency scales sub-linearly across candidate pool sizes on standard commodity CPU without requiring any GPU:

| Candidate Pool Size | Mean Latency ($\pm$ Std Dev) | Median ($p_{50}$) | 95th Percentile ($p_{95}$) | 99th Percentile ($p_{99}$) | Operational Scope |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **10 files** | `0.448 ms` ($\pm 0.072\text{ ms}$) | `0.429 ms` | `0.575 ms` | `0.655 ms` | Micro-component / localized package |
| **35 files** | `0.530 ms` ($\pm 0.172\text{ ms}$) | `0.478 ms` | `0.821 ms` | `1.351 ms` | ARB v0.1 benchmark candidate pool |
| **100 files** | `0.640 ms` ($\pm 0.114\text{ ms}$) | `0.596 ms` | `0.841 ms` | `1.061 ms` | Multi-module service codebase |
| **250 files** | `1.067 ms` ($\pm 0.239\text{ ms}$) | `0.975 ms` | `1.476 ms` | `1.918 ms` | Medium repository candidate pool |
| **500 files** | `1.666 ms` ($\pm 0.312\text{ ms}$) | `1.573 ms` | `2.158 ms` | `2.267 ms` | Full multi-package repository pool |

---

### Part E: System Architecture & Hardware Environment Boundaries

- **CPU Native Architecture**: RepoNeedle runs completely in Python/NumPy/SciPy/NetworkX without requiring CUDA GPUs or heavy deep learning runtime dependencies.
- **Neural Embedding Baseline Limitation**: Heavy neural embedding checkpoints (such as `Qwen/Qwen3-Embedding-0.6B`) could not be evaluated locally due to environment resource limits (absence of PyTorch and CUDA GPUs in the local execution sandbox). RepoNeedle is evaluated against the strongest CPU-compatible baselines (BM25, RepoMap, Subword-Semantic, and Lexical).
- **Not a Newly Trained Checkpoint**: RepoNeedle is a structured, workflow-adaptive, token-budget-aware context selection engine, not a newly pre-trained foundation model. Claims of superiority are strictly bounded to the empirical task retrieval metrics on ARB and RepoNeedle-Bench.

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
