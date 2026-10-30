# RepoNeedle Stage 3.20 — Clean Reproduction Guide

**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Starting Commit:** `89a3ef4`  
**Tags Verified:**
- `v0.1.0-baseline` -> `8e0042553a14b6e3c6cf5b35823c4da84181a8e9`
- `stage3-candidate-freeze` -> `cd7f3b01e28695f9a9357e0815069e0eae85baca`

---

## 1. Environment Requirements

- **OS:** Windows 10/11 64-bit AMD64
- **Python:** 3.10+ (tested on Python 3.12.10 64-bit)
- **Dependencies:** `numpy`, `scipy`, `networkx`, `pydantic`, `pathspec`, `rich`, `pytest`, `pytest-cov`
- **Benchmark Corpus:** `external/agent-retrieval-bench` (authentic local dataset)

---

## 2. Step-by-Step Reproduction Instructions

### Step 1: Verify Baseline & Existing Test Suite
Run the full pytest suite to verify zero regressions across existing components:

```bash
pytest tests/
```
*Expected Result:* 220 tests pass in ~8 seconds.

---

### Step 2: Execute Research-to-Production Parity Tests
Run the deterministic multi-language test suite comparing `research/stage3_14/pilot_attenuation.py` against `reponeedle.core.arm101.ARM101Ranker`:

```bash
python research/stage3_20/run_parity_tests.py
```
Or run via pytest:
```bash
pytest tests/test_arm101_production_parity.py
```
*Expected Result:* 16/16 test scenarios pass with 100.0% exact ranking parity across Python, Rust, Go, TypeScript, Java, and all edge cases (cyclic imports, duplicate symbols, syntax errors, empty repositories, large files).

---

### Step 3: Execute Full ARB v2 Production-Path Reproduction
Execute the full benchmark pipeline evaluating `RepoNeedleEngine.retrieve(..., ranker="arm101")` across all 345 positive ARB v2 queries:

```bash
python research/stage3_20/run_production_arb_reproduction.py
```
*Expected Result:*
- Production ARM-101 MRR: `0.2078`
- Research ARM-101 MRR: `0.2078`
- Absolute Delta: `0.000000` ($\le 0.0010$ requirement met)
- Outputs written to:
  - `research/stage3_20/PRODUCTION_ARB_RESULTS.csv`
  - `research/stage3_20/PRODUCTION_PER_QUERY_RESULTS.csv`
  - `research/stage3_20/RESEARCH_VS_PRODUCTION_PARITY.csv`
  - `research/stage3_20/FULL_CORPUS_REPRODUCTION.md`

---

### Step 4: Profile Real Isolated Process Memory & Latency
Execute the isolated Win32 PSAPI and tracemalloc memory profiler across small (`pallets/click`), medium (`caddyserver/caddy`), and large (`etcd-io/etcd`) codebases:

```bash
python research/stage3_20/benchmark_resources.py
```
*Expected Result:*
- Click: Indexing ~7.1s, Post-Index RSS ~105MB, P50 latency ~14ms
- Caddy: Indexing ~29.7s, Post-Index RSS ~150MB, P50 latency ~6.7ms
- etcd: Indexing ~126s, Post-Index RSS ~287MB, P50 latency ~18.9ms
- Outputs written to:
  - `research/stage3_20/RESOURCE_BENCHMARKS.csv`
  - `research/stage3_20/RESOURCE_METHODOLOGY.md`
  - `research/stage3_20/SCALABILITY_FINDINGS.md`

---

### Step 5: Test CLI and Public Python API
Run the CLI on the local repository:

```bash
python -m reponeedle.cli "retrieval ranking engine" --repo reponeedle --ranker arm101 --budget 2000
```
*Expected Result:* Displays formatted context table with ranked files, token counts, and scores in sub-50ms.

---

### Step 6: Test Wheel Build & Isolated Virtual Environment Installation
Build wheel package and test installation in a clean virtual environment:

```bash
pip wheel --no-deps --no-build-isolation -w dist .
python -m venv test_env --system-site-packages
./test_env/Scripts/pip install --no-deps dist/reponeedle-0.1.0-py3-none-any.whl
./test_env/Scripts/reponeedle "FunctionGraphEngine call graph" --repo reponeedle --ranker arm101 --budget 1500
Remove-Item -Recurse -Force test_env, dist
```
*Expected Result:* Successfully builds wheel, installs in clean venv, and executes `reponeedle` CLI binary with 100% functionality.
