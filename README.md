# 🪡 RepoNeedle

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/krishika08/RepoNeedle/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/krishika08/RepoNeedle/actions/workflows/ci.yml)
[![Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Dataset-RepoNeedle--Bench-blue)](https://huggingface.co/datasets/RepoNeedle/RepoNeedle-Bench)
[![Hugging Face Space](https://img.shields.io/badge/%F0%9F%A4%97%20Space-RepoNeedle--Playground-indigo)](https://huggingface.co/spaces/RepoNeedle/RepoNeedle-Playground)

**RepoNeedle finds the files an AI coding agent needs for a task, and packs them into a token budget you choose.**

Give it a bug report, an error traceback, or a request like "find the tests for `SessionManager`", and it returns a ranked selection of files, focused code spans and structural outlines that fits inside the context window you specify. It runs locally on your CPU, with no GPU, API key, model download or network access.

---

## 💡 Why RepoNeedle?

- **Agents cannot read a whole repository.** Coding agents (Claude Code, Cursor, Aider, and others) have to decide which files to load into a limited context window. Loading too much wastes tokens and money and buries the relevant code; loading too little misses it.
- **File size matters as much as relevance.** A search that ignores file size can spend an entire 4,000-token budget on one large file. RepoNeedle scores files by relevance *per token* and falls back to focused spans or signatures-only outlines when a full file does not fit. It never exceeds the budget, as measured by its own token model.
- **Different tasks need different files.** A traceback points at specific frames, a "write tests" request needs test files, and a refactor needs dependent modules. RepoNeedle adapts its ranking to the kind of task.
- **CPU-first and local.** It is plain Python (NumPy, SciPy, NetworkX), so it runs on laptops and CI machines, keeps your code on your machine, and needs no model weights.

RepoNeedle is a research-oriented project: its benchmark results, including where it does **not** beat simpler baselines, are documented in detail [below](#-benchmark-validation) and in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

---

## 📌 Release Status

| Feature | 1.1.0 (released, PyPI) | Development branch (planned 1.2.0, **unreleased**) |
| :--- | :---: | :---: |
| CPU-first execution | ✅ | ✅ |
| Python 3.10, 3.11, 3.12 | ✅ | ✅ |
| Python API with five rankers (`legacy`, `bm25`, `arm101`, `cascade`, `change_impact`) | ✅ | ✅ |
| CLI with Rich output (`--ranker`, `--task`, `--mode`, `--output-file`) | ✅ | ✅ |
| CLI JSON output (`--json`) | — | ✅ |
| CLI anchor files (`--anchors`) | — | ✅ |
| MCP server over STDIO (`reponeedle-mcp`) | — | ✅ (protocol-tested; not yet validated in a live Claude Code / Cursor session) |
| Selective abstention heuristic (experimental, uncalibrated) | Always on | **Disabled by default**, opt-in |
| Indexing diagnostics & configurable file-size limit | — (fixed 500 KB limit, skipped files not reported) | ✅ |
| Persistent index cache | Not implemented | Not implemented |
| Automatic live filesystem updates | Not implemented | Not implemented |
| HTTP / SSE MCP transport | Not implemented | Not implemented |
| AST block slicing of large files | Not implemented | Not implemented |

Features marked for the development branch require installing from source (see below) until 1.2.0 is published.

---

## 🚀 Quickstart

### 1. Install

```bash
# Released version (1.1.0) from PyPI
pip install reponeedle

# Development branch: adds --json, --anchors, the MCP server and indexing diagnostics
git clone https://github.com/krishika08/RepoNeedle.git
cd RepoNeedle
pip install -e .            # core
pip install -e ".[mcp]"     # core + MCP server
```

### 2. Try the CLI

```bash
# Rank and pack context for a task (works with 1.1.0 and the development branch)
reponeedle "where is the session cookie saved?" --repo ./my-project --budget 4000

# Development branch: machine-readable JSON for scripts and agents
reponeedle "fix token expiration in auth" --repo ./my-project --json
```

### 3. Use it from Python

```python
from reponeedle import RepoNeedleEngine

engine = RepoNeedleEngine.from_directory("./my-project")
result = engine.retrieve("Fix the session timeout bug", budget_tokens=4000)

for f in result.selected_files:
    print(f.path, f.tier.value, f.token_count)

prompt_context = result.rendered_context   # ready-to-paste markdown for an LLM
```

### 4. Connect an MCP client (development branch)

```bash
pip install -e ".[mcp]"
claude mcp add reponeedle -- python -m reponeedle.mcp --repo /absolute/path/to/your/project
```

The server exposes `reponeedle_retrieve`, `reponeedle_change_impact` and `reponeedle_inspect`. See the [MCP Integration Guide](docs/MCP_INTEGRATION.md) for Cursor and other clients. The server is tested at the protocol level (MCP Python SDK and a JSON-RPC STDIO handshake); it has not yet been validated in a live Claude Code or Cursor session.

---

## 🧩 How It Works (Technical Overview)

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
4. **Experimental Selective Abstention (opt-in, disabled by default)**: Peak-to-noise ($Z$-score), score-margin and repository symbol overlap heuristic that can abstain on out-of-scope queries. It is **not production-calibrated** (0/82 correct abstentions on the ARB v2 selective split; see Part B) and must be explicitly enabled.
5. **CUD-Pack (Capacity-Sensitive Utility-Density Packing)**: Adaptive knapsack selection engine providing strict zero downstream overflows ($C_{\text{actual}} \le B_{\text{configured}}$) according to RepoNeedle's regex code token model across dual modes: **Compact Mode** ($\le 4\text{k}$ tokens, extracting high-density implementation spans and structural skeletons) and **Complete Context Mode** ($\ge 8\text{k}$ tokens, preserving whole source files).
6. **Change-Impact Ranking Engine (V1.1 Opt-in)**: Seed-relative relationship scoring (evaluating static imports, symbol definitions, call sites, build manifests (`setup.py`, `setup.cfg`, `pyproject.toml`, `cargo.toml`, `package.json`, `go.mod`, `pom.xml`), test-stems, and directory proximity) designed for bug fixing and refactoring tasks.

---

## 📖 Usage Guide

RepoNeedle is self-contained and requires standard Python dependencies (`numpy`, `scipy`, `networkx`, `pydantic`, `pathspec`, `rich`, and `tomli` on Python < 3.11).

### 1. Installation Details

| What you need | Command |
| :--- | :--- |
| Released 1.1.0 (Python API, Rich CLI) | `pip install reponeedle` |
| Development branch (adds `--json`, `--anchors`, indexing diagnostics) | `pip install -e .` (from a clone) |
| Development branch + MCP server | `pip install -e ".[mcp]"` |
| Test and development tools | `pip install -e ".[dev]"` |

> [!NOTE]
> `pip install "reponeedle[mcp]"` from PyPI currently installs 1.1.0, which does not include the MCP server. Install from source for MCP support until 1.2.0 is published.

> [!TIP]
> On Python 3.10, `tomli>=2.0.1` is automatically installed via conditional dependency. On Python 3.11 and 3.12, native standard library `tomllib` is used with zero extra dependencies.

---

### 2. Python API

#### Standard Retrieval (Default Legacy Ranker):
```python
from reponeedle import RepoNeedleEngine, BudgetConfig

# 1. Initialize engine on a local codebase (uses default 'legacy' ranker)
engine = RepoNeedleEngine.from_directory(
    repo_dir="./my-project",
    budget_config=BudgetConfig(max_tokens=4000, allow_skeletons=True, mode="auto"),
)

# 2. Retrieve context for a task (auto-resolves to compact mode for <= 4k)
result = engine.retrieve(
    query="Add support for blueprint url_prefix inheritance in route registration",
    budget_tokens=4000,
)

if result.abstained:
    print(f"Abstained: {result.explanation}")
else:
    print(f"Retrieved {len(result.selected_files)} files ({result.total_tokens} / {result.budget_tokens} tokens):")
    for f in result.selected_files:
        print(f"[{f.tier.value.upper()}] {f.path} (score: {f.score:.3f}, tokens: {f.token_count})")

    # Access the exact fenced-markdown serialized prompt ready for LLM consumption:
    llm_prompt_context = result.rendered_context
```

> [!NOTE]
> With default settings `result.abstained` is `True` only for an empty repository (no candidate files). Heuristic out-of-scope abstention is opt-in; see below.

#### Experimental Abstention (Opt-In)

> [!WARNING]
> **Behavior change on the development branch (planned 1.2.0, unreleased)**: the selective abstention heuristic is **disabled by default**. In released 1.1.x it runs on every query. Because it is not production-calibrated (0 of 82 negative samples correctly abstained on the ARB v2 selective split), leaving it on gave a misleading impression that out-of-scope queries were being filtered. With it disabled, retrieval always returns ranked results (except for an empty repository) and **out-of-scope queries are not detected**. If you relied on the 1.1.x behavior, opt in explicitly as shown below.

```python
from reponeedle import RepoNeedleEngine, BudgetConfig, TaskType

# Engine-wide opt-in (abstention_threshold keeps working as before)
engine = RepoNeedleEngine.from_directory(
    repo_dir="./my-project",
    budget_config=BudgetConfig(enable_experimental_abstention=True, abstention_threshold=0.12),
)

# ...or per call, overriding the engine setting in either direction
result = engine.retrieve("Cargo.toml tokio runtime leak", enable_experimental_abstention=True)

print(result.abstained)               # decided by the heuristic only because we opted in
print(result.abstention.status)       # "disabled" | "evaluated" | "empty_repository"
print(result.abstention.experimental) # always True
print(result.abstention.calibrated)   # always False
```

- **`TaskType.SELECTIVE` does not enable abstention.** Selecting the `selective` task only changes routing weights; the opt-in flag is the only switch.
- `confidence_score` is still computed with the unchanged heuristic formula for every result. It is an **uncalibrated signal**, not a probability that the answer is in the repository.
- Empty repositories always return `abstained=True` (`abstention.status == "empty_repository"`), independent of the flag, because there is nothing to return.

#### Confidence Scores Are Diagnostic, Not Probabilities

`RetrievalResult.confidence_score` (also reported by the CLI `--json` output and the MCP `reponeedle_retrieve` tool) is the raw output of the experimental abstention heuristic: a weighted mix of vocabulary overlap, score peakiness and score margin.

- It is **not calibrated** and is **not** a probability that the repository contains the answer. On the ARB v2 no-gold queries it was 0.53–0.89, overlapping the values seen on in-scope queries.
- It is computed on every query, whether or not abstention is enabled, so its value does not depend on the opt-in flag.
- With abstention disabled (the development-branch default), it **never** prevents normal retrieval.
- Whether the heuristic was applied is reported explicitly in `result.abstention` (`enabled`, `status`, `experimental: true`, `calibrated: false`) in the Python API, in the `abstention` object of CLI `--json` output, and in the MCP retrieve response.

Do not use `confidence_score` to decide whether an answer exists in the repository.

#### Indexing Limits & Diagnostics

`from_directory` skips files **strictly larger** than `max_file_size_bytes` (default `500_000`; a file exactly at the limit is indexed). Skipped files are never silently dropped: they are recorded in `engine.indexing_diagnostics` and summarized by a `WARNING` on the `reponeedle.engine` logger (stderr by default). Diagnostics contain repository-relative paths and counts only, never file contents.

```python
from reponeedle import RepoNeedleEngine

engine = RepoNeedleEngine.from_directory("./my-project", max_file_size_bytes=1_000_000)

diag = engine.indexing_diagnostics
print(diag.indexed_files, diag.skipped_large_files, diag.max_file_size_bytes)
print(diag.skipped_paths)      # e.g. ["generated/large_module.py", "vendor/huge_source.cpp"]
print(diag.unreadable_paths)   # files that could not be read
print(diag.symlink_outside_repository_paths)  # links resolving outside the repo (target never read)
print(diag.max_files_reached)  # True if indexing stopped at max_files (default 3000)
```

`max_file_size_bytes` must be a positive integer: `0` and negative values raise `ValueError`, non-integers raise `TypeError`. The default is unchanged and is never raised automatically. Only files with a supported extension and not excluded by ignore rules (`.gitignore` and the built-in patterns) are counted.

#### Opt-In: Seed-Based Change-Impact Retrieval:
```python
from reponeedle import RepoNeedleEngine, Query

# Initialize engine with Change-Impact ranking
engine = RepoNeedleEngine.from_directory(
    repo_dir="./my-project",
    ranker="change_impact",
)

# Populate anchor_files with the seed path to activate relationship scoring
query = Query(
    text="Fix authentication session expiration",
    anchor_files=["auth/session.py"],
    budget_tokens=4000,
)

result = engine.retrieve(query)

for f in result.selected_files:
    print(f"[{f.tier.value.upper()}] {f.path} (score: {f.score:.3f}, tokens: {f.token_count})")
    if f.explanation:
        print(f"       Attribution: {f.explanation}")
```

> [!NOTE]
> **Behavior of Plain-String (Seedless) Change-Impact Queries**:
> The Change-Impact ranking engine reads seed file paths from `query.anchor_files`. When `engine.retrieve()` is called with a plain string query (or without `anchor_files`):
> - **Lexical and semantic scoring remain active**: Candidate files continue to be retrieved and scored using combined BM25 lexical matching and subword semantic retrieval.
> - **Seed suppression is inactive without `anchor_files`**: Seed File Suppression (SFS) is not triggered since there are no designated seed files to down-weight.
> - **Seed-relative relationship boosts are inactive without `anchor_files`**: Relationship scoring across dependencies (static imports, symbols, calls, build manifests, test-stems, and directory proximity) is skipped.
> - **Test Intent Prior adjustments remain available according to detected query intent**: Test files receive boosts or penalties (`tip_multiplier_test` / `tip_multiplier_non_test`) based on detected test intent in the query text.
>
> To activate seed-relative relationship boosts and seed suppression, pass seed paths via `Query(text=..., anchor_files=['path/to/seed.py'])`.

---

### 3. Command Line Interface (CLI)

```bash
# Default 'legacy' retrieval under a 4000 token limit
reponeedle "Fix AttributeError in SecureCookieSessionInterface cookie saving" --repo ./flask --budget 4000

# Seed-based Change-Impact retrieval with anchor files
reponeedle "Assess session timeout refactor" --repo ./my-project --ranker change_impact --anchors auth/session.py --budget 4000

# Machine-readable JSON output for AI agent pipelines
reponeedle "Fix authentication expiration" --repo ./my-project --json

# Task-conditioned retrieval for finding regression tests
reponeedle "test suite for HTTPBasicAuth" --repo ./requests --task code2test --budget 2000

# Serialize packaged markdown directly to a file
reponeedle "blueprints and route registration" --repo ./flask --budget 4000 --output-file prompt.md

# Opt in to the EXPERIMENTAL (uncalibrated) abstention heuristic
reponeedle "tokio runtime leak" --repo ./flask --json --enable-experimental-abstention

# Raise the per-file size limit (default 500000 bytes); skipped files are reported
reponeedle "parser entry point" --repo ./my-project --json --max-file-size-bytes 1000000
```

- `--task selective` does **not** enable abstention; only `--enable-experimental-abstention` does.
- With `--json`, stdout is strictly one JSON document. It contains an `abstention` object (`enabled`, `status`, `experimental`, `calibrated`, `threshold`, `reason`) and an `indexing` object (`indexed_files`, `skipped_large_files`, `skipped_paths`, `max_file_size_bytes`, `unreadable_paths`, …). Warnings about skipped files go to **stderr** only.
- Without `--json`, a yellow "Indexing notice" listing skipped paths is printed to **stderr**.
- An invalid `--max-file-size-bytes` (zero or negative) exits with code `1` and an error on stderr.

---

### 4. Model Context Protocol (MCP) Server

*Development branch only (planned 1.2.0; install with `pip install -e ".[mcp]"`).* RepoNeedle includes a local **MCP server** that lets MCP-capable coding agents call it over STDIO. It is tested with the MCP Python SDK and a JSON-RPC STDIO handshake; it has not yet been validated in a live Claude Code, Cursor, Cline or Windsurf session.

```bash
# Launch the MCP server pointing to your project
reponeedle-mcp --repo /absolute/path/to/project --budget 4000

# Or via Python module
python -m reponeedle.mcp --repo /absolute/path/to/project
```

#### Supported MCP Tools:
- `reponeedle_retrieve`: Retrieves ranked source files, focus spans, and structural skeletons packed strictly within the token budget.
- `reponeedle_change_impact`: Analyzes modified anchor files to discover downstream affected modules and regression test suites using Seed File Suppression (SFS).
- `reponeedle_inspect`: Returns repository metadata, indexed file counts, sample paths, active engine configuration, **indexing diagnostics** (files skipped for exceeding `--max-file-size-bytes` or being unreadable) and the experimental abstention status, without dumping file contents.

`reponeedle_retrieve` accepts an optional `enable_experimental_abstention` boolean (default `false`). The server's file-size limit is set at launch with `--max-file-size-bytes`.

For client configuration examples (Claude Code, Cursor), see the [MCP Integration Guide](docs/MCP_INTEGRATION.md).

---

## 📊 Benchmark Validation

To maintain strict scientific integrity, **Official External Benchmark Results** are reported separately from **Independent Research Evaluations**. Dataset sizes, query counts ($N$), candidate pool properties, and evaluation methodologies are explicitly documented for every measurement.

> [!IMPORTANT]
> **Which engine these numbers describe.** Parts A–C and the latency table in Part D come from the ARB v2 run of 2026-10-28, made with the engine at commit `8e00425` (tag `v0.1.0-baseline`); that code reproduced the published per-query records exactly on every query checked (all 82 selective and 53 of 345 positive queries). Engine changes made before the 1.1.0 release altered RepoNeedle's rankings, so these results do **not** describe released 1.1.0. The current engine (1.1.0, identical to the development branch) was re-measured on the same ARB v2 positive split on 2026-11-09:
>
> | ARB v2 positive (N=345) | MRR | Recall@5 | Recall@10 | Recall@20 | BCY@4k | BCY@8k |
> | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
> | **RepoNeedle, current engine (1.1.0)** | **0.2153** | **0.3032** | **0.3677** | **0.3842** | **0.2400** | **0.3443** |
> | RepoNeedle, 2026-10-28 engine (Part A) | 0.2287 | 0.3011 | 0.4110 | 0.4279 | 0.2436 | 0.3450 |
>
> The qualitative conclusions below still hold for the current engine: significantly higher MRR than BM25 (+0.0633, repository-clustered 95% CI [+0.0111, +0.0980]) and Lexical, parity with RepoMap on MRR, much lower deep recall than RepoMap, the strongest `code2test` MRR, and a `comment2context` deficit against BM25 (−16.0%). The current engine is somewhat weaker than the 2026-10-28 engine (MRR −0.0134, CI excludes zero). Full tables, per-task results and method: [docs/BENCHMARK_CONFIGURATION.md](docs/BENCHMARK_CONFIGURATION.md#73-current-engine-re-measurement-arb-v2-positive-n345).

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

> [!NOTE]
> **Lexical comparison caveat**: The RepoNeedle vs Lexical difference is significant under the paired $t$-test and the repository-clustered bootstrap, but **not** under the Wilcoxon signed-rank test ($p = 0.1215$), and RepoNeedle wins fewer individual queries than it loses (133 / 29 / 183). The mean gain comes from a smaller number of large wins.

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

> [!IMPORTANT]
> **Methodological Disclosure on `code2test` (+151.7%) and Workflow Routing**:
> - **Task-Conditioned Evaluation**: In the official ARB evaluation above, benchmark task labels (`code2test`, `trace2code`, etc.) were supplied directly to the `WorkflowRouter` (`task_type = sample.get("task_type")`), dynamically activating task-specific fusion weights and test-graph linkages.
> - **Not Default AUTO-Mode Performance**: This measures **task-conditioned retrieval capacity**, not unassisted automatic classification. In unassisted production deployment (`TaskType.AUTO`), the engine relies on query text regex heuristics. If a natural-language query lacks explicit test keywords, automatic intent classification may default to `comment2context`, reducing the observed gain toward baseline BM25 performance (`0.1057`).
> - **Candidate Set Integrity**: The task conditioning dynamically modulates ranking weights and structural graph boosts; candidate file pools themselves are never filtered by oracle labels.

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
> - *Root Cause*: Heuristic confidence on the 82 no-gold queries ranged from `0.532` to `0.891` (5th–95th percentile `0.635`–`0.851`), far above the engine's default threshold of `0.12`. Natural GitHub issue descriptions filed against a repository inherently contain valid repository vocabulary. Counterfactual queries similarly contain ubiquitous software engineering terminology (`error`, `parse`, `client`, `handler`).
> - *Recommendation*: Heuristic score thresholds are insufficient for reliable abstention in large codebases. Selective retrieval requires a dedicated, trained neural discriminator rather than surface lexical statistics.
> - *Consequence*: In released 1.1.0 the heuristic is always on. On the development branch (planned 1.2.0, unreleased) it is **disabled by default** and only applied when explicitly enabled. See [Experimental Abstention](#experimental-abstention-opt-in).

---

### Part C: Component Ablations on Full ARB v2 ($N=345$)

Ablation evaluation conducted on the complete $N=345$ positive ARB v2 benchmark:

| Configuration | Overall MRR | Drop vs Full | Recall@5 | Recall@20 | Description |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Full RepoNeedle** | **0.2287** | **0.00%** | **0.3011** | 0.4279 | All components active (Router + Graph + BM25 + Skeletons) |
| *w/o WorkflowRouter* | 0.1642 | **-28.20%** | — | — | Static uniform weights across all task categories |
| *w/o RepoGraph* | 0.2287 | 0.00% | — | — | Graph centrality and test-to-target links zeroed |
| **Official RepoMap Baseline** | 0.2140 | -6.45% | 0.3185 | **0.6306** | Standalone PageRank graph centrality ranker |
| **Official BM25 Baseline** | 0.1520 | -33.53% | 0.1899 | 0.4452 | Standalone field BM25 ranker |

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
| **Official BM25 Query Latency** | `994.4 ms` | `1,158.3 ms` | `1,246.0 ms` | `1,305.7 ms` | Full inverted index posting scan |
| **Official RepoMap Query Latency**| `157.5 ms` | `192.1 ms` | `239.8 ms` | `250.1 ms` | Graph PageRank vector lookup |
| **Official Lexical Query Latency**| `884.1 ms` | `1,005.2 ms` | `1,150.3 ms` | `1,156.6 ms` | BM25 + subword character bigram matching |
| **RepoNeedle Index Build** | `8,622.9 ms` | `10,471.2 ms` | `11,484.8 ms` | `11,551.5 ms` | One-time AST + dependency graph per repo |

---

### Part E: System Architecture & Deployment Status

- **CPU Native Architecture**: RepoNeedle runs entirely in Python/NumPy/SciPy/NetworkX without requiring CUDA GPUs or heavy deep learning runtime dependencies.
- **Release Status**: **1.1.0 is published on PyPI (2026-11-03)**, with the default `legacy` ranker and the opt-in `change_impact` ranker. The development branch adds the features listed in [Release Status](#-release-status) and is planned for 1.2.0; it is **not yet released**.
- **Abstention during these evaluations**: Parts A–C, the Part D latency table and Part F were measured with code in which the abstention heuristic was always on. A full re-run on ARB v2 (2026-11-09) verified that the heuristic would abstain on **0 of 345** positive queries and that selected files are identical with and without it, so the new opt-in default does not change any ARB v2 result. See [docs/BENCHMARK_CONFIGURATION.md](docs/BENCHMARK_CONFIGURATION.md).

---

### Part F: Independent R6 Change-Impact Benchmark ($N=180$ Queries across 18 Repositories)

To evaluate retrieval generalizability beyond the original 25 ARB repositories, an independent benchmark cohort was constructed across **18 unseen open-source repositories** comprising 180 retrieval queries.

Statistical inference was conducted using **repository-clustered statistical models** across independent repository clusters:

| Partition | Queries ($N$) | Repositories | Baseline MRR | Champion MRR | Delta (Δ) | Repository-Clustered Inference (95% CI) | Statistical Significance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Training** | $N=90$ | 9 repos | 0.6213 | 0.6546 | +0.0333 | — | Training fit |
| **Validation** | $N=40$ | 4 repos | 0.6472 | 0.6708 | +0.0236 | $p = 0.5073$, 95% CI [0.0000, +0.0472] | Not Statistically Significant |
| **Held-Out** | $N=50$ | 5 repos | 0.5215 | 0.5467 | +0.0252 | $p = 0.5025$, 95% CI [0.0000, +0.0629] | Not Statistically Significant |
| **Pooled Cohort** | $N=180$ | 18 repos | 0.5994 | **0.6282** | **+0.0288** | $p = 0.0078$, 95% CI [+0.0082, +0.0524] | **Statistically Significant ($p < 0.01$)** |

> [!NOTE]
> **Methodological Context & Scope of R6 Results**:
> - **Pre-Filtered Candidate Pools**: Queries were evaluated against pre-filtered candidate pools averaging approximately **53.79 files per query**. Within these candidate pools, Candidate-Pool Recall@20 is 100%.
> - **Whole-Repository Generalization**: Whole-repository Recall@20 of 60–75% represents a projected estimate under full repository indexing, not an empirically measured whole-codebase scan.
> - **Statistical Power & Default Ranker**: While the pooled 18-repository cohort achieves statistically significant improvement under repository-clustered inference ($p = 0.0078$), the smaller isolated validation ($N=40$, $p = 0.5073$) and held-out ($N=50$, $p = 0.5025$) subsets are statistically underpowered. For this reason, the Change-Impact engine is provided as an **opt-in capability** rather than overriding the default `legacy` ranker.
> - **Aspirational Research Target**: The long-term research objective of $\text{MRR} \ge 0.80$ is an aspirational research milestone, not an achieved production metric.

---

### Part G: Supplemental Product-Aligned Evaluation (Not an Official ARB Score)

> [!WARNING]
> **Supplemental evaluation, separate from the official results above.** Parts A–C are official ARB v2 harness results. This part uses a supplemental evaluator to answer a different question: how good is RepoNeedle's **actual full ranking** when it reads **whole files**, as it does in real use?

The official harness gives RepoNeedle a single fragment per file (while its BM25 baseline ranks every chunk) and scores files RepoNeedle did not pack in corpus order. The supplemental evaluation (2026-11-09, current engine) instead ranks **files** for every system and compares RepoNeedle and BM25 on the **same** input representation. It reports full-ranking metrics without remainder positions, and packed-context coverage separately.

| ARB v2 positive (345 queries, 25 repositories), file-level full ranking | MRR | Recall@5 | Recall@10 | Recall@20 |
| :--- | :---: | :---: | :---: | :---: |
| RepoNeedle, whole-file input | 0.2789 | 0.4270 | 0.5862 | 0.7042 |
| BM25, whole-file input | 0.1717 | 0.2290 | 0.3498 | 0.5138 |
| RepoNeedle, fragment input (official harness input) | 0.2379 | 0.3061 | 0.4407 | 0.5803 |
| BM25, fragment input | 0.1439 | 0.1650 | 0.2389 | 0.3604 |

- **Matched whole-file input, overall**: RepoNeedle − BM25 = MRR +0.1073 (repository-clustered 95% CI [+0.0647, +0.1596]); Recall@20 +0.1904 [+0.1114, +0.2715].
- **By task**: significantly better on `code2test` (every metric) and on `edit2ripple` Recall@10/20. Inconclusive on `trace2code` (only 7 repositories). On `comment2context`, level on MRR but **significantly worse on Recall@20** (−0.0896 [−0.1779, −0.0056]).
- **Packed context** (8,000 tokens): gold-file coverage rises from 38.3% (fragments) to 59.8% (whole files); queries with at least one gold file packed rise from 45.8% to 68.4%.

These figures are not comparable to Part A and do not replace it. Method, fidelity checks (including exact reproduction of the official harness on 345/345 queries) and limitations: [reports/experimental/phase1_product_aligned_evaluation/REPORT.md](reports/experimental/phase1_product_aligned_evaluation/REPORT.md).

---

## 🧠 CUD-Pack Architecture (Capacity-Sensitive Utility-Density Packing)

RepoNeedle integrates the **CUD-Pack** context optimization engine, replacing heuristic packing with capacity-elastic utility-density optimization:

### 1. Dual Operational Modes
- **Compact Mode ($\le 4\text{k}$ tokens, $\alpha = 0.65$)**: Prioritizes focal implementation spans (`FOCUS_SPAN`) and structural skeletons (`SKELETON`). Prevents single distractor files from consuming the budget and displacing multi-target dependencies.
- **Complete Context Mode ($\ge 8\text{k}$ tokens, $\alpha = 0.25$)**: Prioritizes whole source files (`FULL`), selectively utilizing structural outlines for oversized files ($> 500$ tokens) when capacity is tight.

### 2. Verified Token Budget Invariants
- **Deterministic Budget Enforcement**: Evaluated across tested nominal budgets (30, 50, 100, 500, 2000, 4000 tokens), CUD-Pack strictly enforces $C_{\text{actual}} \le B_{\text{configured}}$ with zero downstream token overflows according to RepoNeedle's deterministic regex token-counting model (`regex_code_tokenizer_v1`).
- **Overhead Accounting**: Pre-computes file header fences (`# File: {path}\n```{ext}\n...\n```\n\n`) deterministically before admitting candidates into the knapsack.
- **Representation Fallback Hierarchy**: Monotonically degrades candidate representations (`FULL` $\to$ `FOCUS_SPAN` $\to$ `SKELETON`) when full files exceed available token capacity.

> [!WARNING]
> **Tokenizer Boundary Disclosure**: Budget non-exceedance is enforced strictly according to RepoNeedle's internal regex token model (`regex_code_tokenizer_v1`). This does not imply exact token-count equivalence with arbitrary third-party LLM tokenizers (e.g. OpenAI tiktoken cl100k, LLaMA sentencepiece, or Qwen) or guarantee downstream token behavior for every external provider.

---

## 🔬 Reproducing Benchmark Results

```bash
# 1. Run the automated test suite (the count changes as tests are added; CI reports the current number)
python -m pytest -q -rs

# 2. Re-verify the ARB v2 abstention results and positive-query reproducibility
#    (needs external/agent-retrieval-bench; read-only; add --positives for the slower N=345 check)
python scripts/verify_abstention_reproducibility.py

# 3. Run the component ablation study with 95% bootstrap CI
#    (overwrites benchmarks/results/ablation_study_results.json; compare with `git diff`)
python benchmarks/run_ablations.py

# 4. Verify BPE token payload reduction and latency
python scripts/verify_token_savings_and_latency.py

# 5. Build distribution packages into a scratch directory
python -m build --no-isolation --outdir /tmp/reponeedle-dist
```

Which scripts enable the experimental abstention heuristic, which do not, and which historical results were measured under the old always-on default are documented in [docs/BENCHMARK_CONFIGURATION.md](docs/BENCHMARK_CONFIGURATION.md). That file also lists known reproducibility gaps; for example, the synthetic `benchmarks/results/benchmark_results.json` from v0.1.0 is not reproduced by later code.

---

## 📦 Hugging Face Release Artifacts

RepoNeedle distributes its validated assets primarily via Hugging Face:

1. **RepoNeedle-Bench Dataset**: [`hf_artifacts/dataset/`](hf_artifacts/dataset/README.md)
   - Permissively licensed JSONL datasets (`train.jsonl`, `test.jsonl`), schema, and provenance documentation.
2. **RepoNeedle Playground Space**: [`hf_artifacts/space/`](hf_artifacts/space/README.md)
   - Interactive Gradio demonstration allowing side-by-side comparison of RepoNeedle against classical BM25 and RepoMap PageRank.
3. **Automated Publishing Script**: [`scripts/prepare_hf_release.py`](scripts/prepare_hf_release.py)
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
  howpublished = {\url{https://github.com/krishika08/RepoNeedle}}
}
```
