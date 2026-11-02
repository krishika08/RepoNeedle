# RepoNeedle V1.1 — CI Failure Root Cause Analysis

**Document Version**: 1.0.0  
**Author**: Senior Python Test Infrastructure Engineer  
**Date**: November 2026  
**Repository**: `krishika08/RepoNeedle`  
**Failed CI Runs**: `41466687625`, `41466579695`, `41471107007`, `41472126587`  
**Target Green Run**: [`41472997734`](https://github.com/krishika08/RepoNeedle/actions/runs/41472997734) (All Jobs Succeeded)

---

## 1. Executive Summary

Upon deploying the initial GitHub Actions workflow on branch `v1.1-production-release`, test runs on Python 3.10, 3.11, and 3.12 failed during the test collection and execution stages.

Forensic examination identified **four distinct root causes**:
1. **Primary Root Cause**: Unconditional module imports of uncommitted external research submodule (`external/agent-retrieval-bench/`) causing collection-time `ModuleNotFoundError`.
2. **Secondary Root Cause A (Git Shallow Clone)**: Default `fetch-depth: 1` in `actions/checkout@v4` and unpushed historical release tags causing git subprocess assertion failures (Exit Code 128).
3. **Secondary Root Cause B (Python 3.10 Standard Library Divergence)**: Absence of `tomllib` in the Python 3.10 standard library causing empty dictionary returns in Cargo manifest parsing.
4. **Secondary Root Cause C (Online CI vs Offline Sandbox Assumption)**: Test assertion expecting network block (Exit Code 2) in an online cloud runner environment that has internet access (Exit Code 0).

---

## 2. Detailed Root Cause Forensics

### 2.1 Primary Root Cause: Missing Optional Benchmark Dependency

#### Symptom
In GitHub Actions runs `41466687625` and `41466579695`, pytest aborted immediately during test collection:
```
ModuleNotFoundError: No module named 'agent_retrieval_bench'
```
Failing collection targets:
- `tests/test_arm101_production_parity.py:13`
- `tests/test_stage3_7_metrics.py:26`
- `tests/test_stage3_8_reproducibility.py:22`

#### Dependency Lineage & Mechanism
1. **`tests/test_arm101_production_parity.py`**:
   Imports `ExperimentalLanguageRanker` from `research/stage3_14/pilot_attenuation.py`.
   At line 24 of `pilot_attenuation.py`, it executes:
   ```python
   from agent_retrieval_bench.baseline import read_jsonl, target_gold_files, query_text_for_eval
   ```
2. **`tests/test_stage3_7_metrics.py`**:
   Tests the canonical metric contract pinned in `agent_retrieval_bench`. It adds `ROOT_DIR / "external" / "agent-retrieval-bench" / "src"` to `sys.path` and executes:
   ```python
   from agent_retrieval_bench.baseline import reciprocal_rank, recall_at, ...
   ```
3. **`tests/test_stage3_8_reproducibility.py`**:
   Tests hand-calculated metric fixtures by importing from `agent_retrieval_bench.baseline`.

#### Why This Failed on GitHub Actions but Passed Locally
- On developer workstations, `external/agent-retrieval-bench/` was cloned from `https://github.com/eyuansu62/agent-retrieval-bench.git` (commit `9e4d68937f29d5967afd62f4f6a24c1478298133`).
- However, `external/` is explicitly listed in [`.gitignore`](file:///F:/RepoNeedle/.gitignore).
- Clean repository checkouts in GitHub Actions (`actions/checkout@v4`) do not contain untracked directories, causing `agent_retrieval_bench` to be unimportable.

---

### 2.2 Secondary Root Cause A: Shallow Git Clones & Missing Remote Tags

#### Symptom
Once collection errors were bypassed, 21 tests in `tests/test_stage3_12_factorial.py`, `test_stage3_13_reconciliation.py`, `test_stage3_18_...`, and `test_stage3_19_...` failed with:
```
subprocess.CalledProcessError: Command '['git', 'rev-parse', 'v0.1.0-baseline^{commit}']' returned non-zero exit status 128.
fatal: ambiguous argument 'v0.1.0-baseline^{commit}': unknown revision or path not in the working tree.
```

#### Mechanism
1. **Shallow Fetch**: By default, `actions/checkout@v4` fetches only the single tip commit (`fetch-depth: 1`). Previous commit history is truncated.
2. **Missing Remote Tags**: When the local git repository was pushed to GitHub, historical release tags (`v0.1.0-baseline`, `v0.1.0-release`, `stage3-candidate-freeze`) were stored only in local `.git/refs/tags/` and had never been pushed to `origin` (`git push origin --tags` had not been executed).
3. **Test Invariant**: Stage 3 audit tests deliberately inspect historical git commits and tags via `git cat-file -p` and `git rev-parse` to guard against revision drift.

---

### 2.3 Secondary Root Cause B: Python 3.10 Standard Library (`tomllib`)

#### Symptom
In Python 3.10 runners, `tests/test_stage3_9_cascade.py:156` failed:
```
AssertionError: assert '' == 'my_crate'
- my_crate
```

#### Mechanism
In [`reponeedle/core/graph.py`](file:///F:/RepoNeedle/reponeedle/core/graph.py#L14-L17):
```python
try:
    import tomllib
except ImportError:
    tomllib = None
```
- The `tomllib` module was introduced in Python 3.11.
- In Python 3.10, `import tomllib` raises `ImportError`, setting `tomllib = None`.
- In `RepoGraph.parse_cargo_manifest(content)`:
  ```python
  if tomllib:
      data = tomllib.loads(content)
      res["name"] = data.get("package", {}).get("name", "")
  return res
  ```
- Because `tomllib` was `None`, the function returned `{"name": ""}`, failing the test on Python 3.10 while succeeding on 3.11 and 3.12.

---

### 2.4 Secondary Root Cause C: Sandbox vs. Online Network Semantics

#### Symptom
In `tests/test_stage3_13_reconciliation.py:118`:
```
AssertionError: Expected returncode 2 (BLOCKED), got 0
[STATUS: ONLINE] Network access verified. Proceeding with dataset acquisition...
```

#### Mechanism
The test author hardcoded:
```python
# Inside sandbox, exit code must be 2 (BLOCKED)
assert res.returncode == 2, f"Expected returncode 2 (BLOCKED), got {res.returncode}"
```
`research/stage3_13/validate_contextbench.py` probes external network connectivity:
- In an offline development sandbox: network probe fails $\to$ returns Exit Code 2 (`[STATUS: BLOCKED]`).
- In GitHub Actions cloud runners: network probe succeeds $\to$ returns Exit Code 0 (`[STATUS: ONLINE]`).
Hardcoding return code 2 broke the test in standard online CI environments.
