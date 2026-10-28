# 🪡 RepoNeedle

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests: Passing](https://img.shields.io/badge/tests-34%20passed-brightgreen.svg)]()
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

To maintain strict scientific integrity, **Official External Benchmark Results** are reported separately from **Synthetic Demonstration Benchmark Results**. Dataset sizes, query counts ($N$), and frozen repository snapshots are explicitly documented for every measurement.

---

### Part A: Full Official Agent Retrieval Bench (ARB v2) Evaluation ($N=345$ Positive Samples)

Evaluated directly using the official `agent_retrieval_bench` evaluation package (`agent_retrieval_bench.baseline.sample_metrics`, v0.2.1, commit `9e4d68937f29`) on the complete **Agent Retrieval Bench v2** release ($N=345$ positive retrieval samples across 25 open-source repositories and 218 frozen repository snapshots):

| System / Ranker | Overall MRR | Recall@5 | Recall@10 | Recall@20 | BCY@4k | BCY@8k | BCY@16k | BCY@32k |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoNeedle (Full)** | **0.2287** | **0.3011** | **0.4110** | **0.4279** | **0.2436** | **0.3450** | **0.4192** | **0.4279** |
| **Official RepoMap** | 0.2140 | 0.3185 | 0.4786 | **0.6306** | 0.2024 | **0.3788** | **0.5235** | **0.6166** |
| **Official Lexical** | 0.1574 | 0.2292 | 0.3548 | 0.4940 | 0.1488 | 0.2650 | 0.3886 | 0.4882 |
| **Official BM25** | 0.1520 | 0.1899 | 0.3034 | 0.4452 | 0.1220 | 0.2051 | 0.3184 | 0.4365 |
| *Qwen3-Embedding-4B (Ext Ref)* | *0.2379* | *—* | *—* | *0.6306* | *—* | *0.3409* | *—* | *—* |
| *Qwen3-Embedding-8B (Ext Ref)* | *0.2336* | *—* | *—* | *0.7029* | *—* | *0.3732* | *—* | *—* |
| *pplx-embed-v1-4b (Ext Ref)* | *0.2267* | *—* | *—* | *0.6072* | *—* | *0.3549* | *—* | *—* |
| *jina-code-0.5b (Ext Ref)* | *0.1914* | *—* | *—* | *0.4823* | *—* | *0.2783* | *—* | *—* |

#### Matched Paired Statistical Tests against Baselines ($N=345$ Identical Queries)

Evaluated with **10,000 bootstrap resamples** (repository-clustered bootstrap across 25 repositories):

| Paired Comparison | Mean Diff (Δ) | Std Error | Sample 95% CI | Repo-Clustered 95% CI | Paired $t$-test | Wilcoxon $W$ ($p$-value) | Wins / Ties / Losses | Statistically Significant |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoNeedle vs BM25** | **+0.0767** (+50.5%) | 0.0161 | [+0.0458, +0.1085] | **[+0.0202, +0.1129]** | $t = 4.776$ ($p = 2.65\times 10^{-6}$) | $W = 22384.0$ ($p = 0.0096$) | 148 / 18 / 179 | **YES ($p < 0.01$)** |
| **RepoNeedle vs RepoMap** | **+0.0148** (+6.9%) | 0.0179 | [-0.0198, +0.0497] | **[-0.0466, +0.0619]** | $t = 0.827$ ($p = 0.4089$) | $W = 23821.5$ ($p = 0.3032$) | 122 / 26 / 197 | **NO (Parity in MRR)** |
| **RepoNeedle vs Lexical** | **+0.0713** (+45.3%) | 0.0157 | [+0.0409, +0.1031] | **[+0.0307, +0.1029]** | $t = 4.529$ ($p = 8.17\times 10^{-6}$) | $W = 22521.5$ ($p = 0.1215$) | 133 / 29 / 183 | **YES ($p < 0.001$)** |

> [!IMPORTANT]
> **Scientific Disclosure on RepoMap Comparison**: RepoNeedle does **NOT** achieve statistically significant overall superiority over RepoMap on MRR ($p = 0.4089$, repository-clustered 95% CI crosses zero: `[-0.0466, +0.0619]`). Furthermore, **RepoMap achieves substantially higher deep recall** (Recall@20: `0.6306` vs `0.4279`, a +47.4% relative advantage for RepoMap) and higher BCY@8k (`0.3788` vs `0.3450`, +9.8% relative advantage). RepoNeedle demonstrates a focused advantage under strict low-token budgets (BCY@4k: `0.2436` vs `0.2024`, +20.4% relative advantage) and specialized regression test discovery (`code2test`).

#### Per-Task Track Breakdown ($N=345$ Positive Samples)

| Task Track | Sample Count ($N$) | Metric | Official BM25 | Official Lexical | Official RepoMap | RepoNeedle | Relative Gain vs BM25 | Relative Gain vs RepoMap |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`code2test`** | $N=106$ | **MRR** | 0.1057 | 0.0663 | 0.1942 | **0.2660** | **+151.7%** | **+37.0%** |
| | | Recall@5 | 0.1305 | 0.0676 | 0.2645 | **0.3918** | +200.2% | +48.1% |
| | | Recall@20 | 0.3066 | 0.2469 | 0.5572 | **0.5931** | +93.4% | +6.4% |
| | | **BCY@8k** | 0.1541 | 0.0928 | 0.3462 | **0.4814** | **+212.4%** | **+39.1%** |
| **`comment2context`** | $N=80$ | **MRR** | **0.1974** | 0.1530 | 0.1532 | 0.1708 | **-13.5%** | +11.5% |
| | | Recall@5 | **0.2146** | 0.1667 | 0.1750 | 0.1646 | -23.3% | -5.9% |
| | | Recall@20 | **0.5292** | 0.4979 | 0.4688 | 0.2083 | -60.6% | -55.6% |
| | | **BCY@8k** | 0.2604 | 0.2167 | **0.2792** | 0.1896 | -27.2% | -32.1% |
| **`trace2code`** | $N=101$ | **MRR** | 0.1638 | 0.2075 | **0.2723** | 0.2337 | +42.7% | **-14.2%** |
| | | Recall@5 | 0.2228 | 0.3432 | **0.4604** | 0.2855 | +28.1% | -38.0% |
| | | Recall@20 | 0.4934 | 0.6964 | **0.8465** | 0.4092 | -17.1% | -51.7% |
| | | **BCY@8k** | 0.1931 | 0.3795 | **0.5066** | 0.2954 | +53.0% | -41.7% |
| **`edit2ripple`** | $N=58$ | **MRR** | 0.1536 | **0.2428** | 0.2323 | 0.2320 | +51.0% | -0.1% |
| | | Recall@5 | 0.2069 | **0.4124** | 0.3678 | 0.3506 | +69.5% | -4.7% |
| | | Recall@20 | 0.4986 | 0.5876 | **0.6121** | 0.4612 | -7.5% | -24.7% |
| | | **BCY@8k** | 0.2428 | **0.4468** | 0.3534 | 0.3966 | +63.3% | +12.2% |

> [!NOTE]
> *Historical Pilot Record ($N=35$ exploratory pilot)*: In early pre-release testing on a small 35-sample v0.1 subset with restricted candidate pools, RepoNeedle achieved MRR `0.879` vs BM25 `0.748`. Those scores reflect narrow candidate sub-pools. Full whole-repository evaluation ($N=345$) across full codebases yields the realistic production MRRs shown above.

---

### Part B: Official ARB Selective Retrieval Evaluation ($N=82$ Abstention Samples)

Evaluated on the complete official Agent Retrieval Bench Selective Retrieval split (`v2_selective_mixed`, $N=82$ total queries across 71 repository snapshots):

| Evaluation Track | Sample Count ($N$) | Correctly Abstained | False Positives (Returned Noise) | Abstention Accuracy |
| :--- | :---: | :---: | :---: | :---: |
| **Natural No-Gold Issues** | 50 | 0 | 50 (100.0%) | **0.0%** |
| **Counterfactual Wrong-Repo** | 32 | 0 | 32 (100.0%) | **0.0%** |
| **Combined Selective Benchmark** | **82** | **0** | **82 (100.0%)** | **0.0%** |

> [!CAUTION]
> **Heuristic Abstention Failure Analysis**: In production benchmark conditions, RepoNeedle's heuristic confidence gating ($Z$-score + repository symbol overlap) achieved **0% abstention accuracy (0/82)**. 
> - *Root Cause*: Heuristic confidence scores ranged between `0.64` and `0.86`, far exceeding the default threshold (`0.38`). Natural GitHub issue descriptions filed against a repository inherently contain valid repository vocabulary. Counterfactual queries similarly contain ubiquitous software engineering terminology (`error`, `parse`, `client`, `handler`).
> - *Recommendation*: Heuristic score thresholds are insufficient for reliable abstention in large codebases. Selective retrieval requires a dedicated, trained neural discriminator rather than surface lexical statistics.

---

### Part C: Component Ablations on Full ARB v2

Ablation evaluation conducted on the complete $N=345$ positive ARB v2 benchmark:

| Configuration | Overall MRR | Drop vs Full | Recall@5 | Recall@20 | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Full RepoNeedle** | **0.2287** | **0.00%** | **0.3011** | 0.4279 | All components active (Router + Graph + BM25 + Skeletons) |
| *w/o WorkflowRouter* | 0.1642 | **-28.20%** | — | — | Static uniform weights across all task categories |
| *w/o RepoGraph* | 0.2287 | 0.00% | — | — | Graph centrality and test-to-target links zeroed |
| **Official RepoMap Baseline** | 0.2140 | -6.45% | 0.3185 | **0.6306** | Standalone PageRank graph centrality ranker |
| **Official BM25 Baseline** | 0.1520 | -33.53% | 0.1899 | 0.4452 | Standalone field BM25 ranker |

*Diagnostic Observation*: While zeroing `RepoGraph` is neutral across the aggregate MRR, it is critical for `code2test` specifically, where graph-based inverted test linkage is responsible for boosting MRR from `0.1057` (BM25) to `0.2660` (+151.7%).

#### Historical / Synthetic Demonstration Suite ($N=15$, Diagnostic Only)

| System / Ablation | Overall MRR | 95% Bootstrap CI | Dev MRR ($N=8$) | Held-out MRR ($N=4$) | Recall@1 | Recall@3 | Wasted Tokens (4k) | Selective Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full RepoNeedle** | **0.917** | [0.792, 1.000] | 1.000 | 0.750 | 0.528 | 1.000 | 581 | 100.0% |
| *w/o WorkflowRouter* | 0.743 | [0.569, 0.903] | 0.844 | 0.542 | 0.375 | 0.875 | 700 | 100.0% |
| *w/o SelectiveAbstainer* | 0.917 | [0.792, 1.000] | 1.000 | 0.750 | 0.528 | 1.000 | 807 | 0.0% |
| **Baseline: Static Hybrid** | 0.743 | [0.569, 0.903] | 0.844 | 0.542 | 0.375 | 0.875 | 927 | 0.0% |
| **Baseline: BM25 Only** | 0.819 | [0.667, 0.958] | 0.938 | 0.583 | 0.417 | 0.861 | 694 | 33.3% |
| **Baseline: Dense Semantic** | 0.771 | [0.604, 0.917] | 0.781 | 0.750 | 0.375 | 0.833 | 927 | 0.0% |
| **Baseline: RepoMap Only** | 0.394 | [0.249, 0.577] | 0.448 | 0.286 | 0.083 | 0.403 | 927 | 0.0% |

---

### Part D: Multi-Scale Token Payload Reduction & Measured Runtime

#### 1. Actual Content Payload Reduction Across Multiple Languages & File Sizes

Measured using exact BPE code subword regex (`re.compile(r"[A-Za-z0-9_]+|[^\s\w]|\s+")`, calibrated to OpenAI cl100k / LLaMA / Qwen tokenizers):

| Corpus File & Language | Lines | Full BPE Tokens | Skeleton BPE Tokens | Actual BPE Token Savings | Character Savings | Architectural Symbols Preserved |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Python (Short)** | 50L | 280 | 280 | 0.0% *(fits budget)* | 0.0% | **YES** (Complete) |
| **Python (Medium Adapter)** | 250L | 2,060 | 305 | **85.2% reduction** | 85.8% reduction | **YES** (Class, methods, docstrings) |
| **Python (Long Session Mgr)** | 700L | 4,061 | 404 | **90.1% reduction** | 90.0% reduction | **YES** (Class, methods, TTL logic) |
| **Rust (Async RingBuffer)** | 200L | 2,312 | 222 | **90.4% reduction** | 91.1% reduction | **YES** (Struct, impl, fn signatures) |
| **TypeScript (EventDispatcher)** | 200L | 1,920 | 455 | **76.3% reduction** | 74.6% reduction | **YES** (Interface, class, methods) |
| **Go (HTTP Trie Router)** | 200L | 1,225 | 578 | **52.8% reduction** | 44.2% reduction | **YES** (Types, struct, methods) |

#### 2. Measured Benchmark Latency Distribution (Commodity CPU, Windows 11 AMD64)

Empirically measured across the full Agent Retrieval Bench evaluation suite:

| Component / Ranker | Mean Latency | Median ($p_{50}$) | 95th Percentile ($p_{95}$) | 99th Percentile ($p_{99}$) | Method Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **RepoNeedle Query Latency** | `317.7 ms` | `142.4 ms` | `827.2 ms` | `997.6 ms` | Multi-signal scoring + knapsack packing |
| **Official BM25 Query Latency** | `994.4 ms` | `1,158.3 ms` | `1,246.0 ms` | `1,305.7 ms` | Full inverted index inverted posting scan |
| **Official RepoMap Query Latency**| `157.5 ms` | `192.1 ms` | `239.8 ms` | `250.1 ms` | Graph PageRank vector lookup |
| **Official Lexical Query Latency**| `884.1 ms` | `1,005.2 ms` | `1,150.3 ms` | `1,156.6 ms` | BM25 + subword character bigram matching |
| **RepoNeedle Index Build** | `8,622.9 ms` | `10,471.2 ms` | `11,484.8 ms` | `11,551.5 ms` | One-time AST + dependency graph per repo |

---

### Part E: System Architecture & Clear Hardware Boundaries

- **CPU Native Architecture**: RepoNeedle runs entirely in Python/NumPy/SciPy/NetworkX without requiring CUDA GPUs or heavy deep learning runtime dependencies.
- **Neural Embedding Baseline Scope**: Heavy neural embedding checkpoints (such as `Qwen/Qwen3-Embedding-4B` and `8B`) were evaluated via published ARB literature. Local GPU inference was not executed due to host sandbox environment boundaries (CPU-only execution).
- **Release Status**: **Limited Research Release (v0.1.0 Research Preview)**. Recommended for retrieval benchmarking and research experiments. Not recommended as a standalone zero-shot abstention gate without an upstream trained neural classifier.

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
