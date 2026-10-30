# RepoNeedle Stage 3.20 — CLI & API Integration Verification

**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Date:** October 2026  
**Status:** VERIFIED COMPLETE  

---

## 1. Executive Summary

Stage 3.20 establishes end-to-end integration of ARM-101 and modular rankers across RepoNeedle's public interfaces:
1. **Command-Line Interface (CLI)**: Full support for `--ranker {legacy,bm25,arm101,cascade}`, retaining `legacy` as the default until parity gates pass.
2. **Python API**: Full support for `RepoNeedleEngine.retrieve(..., ranker="arm101")` and `RepoNeedleEngine.from_directory(..., ablation_config=...)`.
3. **Structured Result Transparency**: `RetrievalResult` exposes `ranker: str` and `ranked_files: List[str]` to provide callers with full visibility into the candidate ranking pipeline.

---

## 2. CLI Surface Verification

### 2.1 Help Specification (`reponeedle --help`)

```text
usage: reponeedle [-h] [--repo REPO] [--budget BUDGET]
                  [--task {auto,code2test,comment2context,trace2code,edit2ripple,selective}]
                  [--no-skeletons] [--ranker {legacy,bm25,arm101,cascade}]
                  query

Token-Budget-Aware, Workflow-Adaptive Repository Context Retrieval for AI
Coding Agents.

positional arguments:
  query                 Coding task, issue description, or error traceback.

options:
  -h, --help            show this help message and exit
  --repo REPO, -r REPO  Path to repository root (default: current directory).
  --budget BUDGET, -b BUDGET
                        Maximum context token budget (default: 4000).
  --task {auto,code2test,comment2context,trace2code,edit2ripple,selective}, -t {auto,code2test,comment2context,trace2code,edit2ripple,selective}
                        Explicit workflow task type (default: auto).
  --no-skeletons        Disallow structural skeleton mode; require full files.
  --ranker {legacy,bm25,arm101,cascade}
                        Retrieval ranker architecture (default: legacy).
```

### 2.2 Live Execution Test

```bash
python -m reponeedle.cli "retrieval ranking engine" --repo reponeedle --ranker arm101 --budget 2000
```

**Output Display:**
```text
+-----------------------------------+
| RepoNeedle Context Retrieval      |
| Target Repository: reponeedle     |
| Query: "retrieval ranking engine" |
| Token Budget: 2000                |
| Ranker: arm101                    |
+-----------------------------------+
                 Retrieved Context (1965/2000 tokens) - 28.7ms                 
+-----------------------------------------------------------------------------+
| Rank | File Path          |   Tier   | Tokens | Score | Explanation         |
|------+--------------------+----------+--------+-------+---------------------|
|  1   | core/cascade.py    | SKELETON |    270 | 0.523 | Structural skeleton |
|  2   | __init__.py        |   FULL   |     88 | 0.302 | Full file included  |
|  3   | engine.py          | SKELETON |    251 | 0.245 | Structural skeleton |
|  4   | cli.py             |   FULL   |    586 | 0.275 | Full file included  |
|  5   | core/abstention.py | SKELETON |    188 | 0.191 | Structural skeleton |
|  6   | core/function_graph| SKELETON |    265 | 0.168 | Structural skeleton |
|  7   | core/lexical.py    | SKELETON |    146 | 0.165 | Structural skeleton |
|  8   | core/router.py     | SKELETON |    171 | 0.107 | Structural skeleton |
+-----------------------------------------------------------------------------+
```

---

## 3. Python API Contract Verification

```python
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import RankerType, TaskType, BudgetConfig

# 1. Directory ingestion
engine = RepoNeedleEngine.from_directory(
    "reponeedle",
    budget_config=BudgetConfig(max_tokens=4000),
)

# 2. String ranker flag
result_str = engine.retrieve(
    "auth login authentication",
    ranker="arm101",
    budget_tokens=4000,
)
assert result_str.ranker == "arm101"
assert len(result_str.ranked_files) == len(engine.docs)

# 3. Enum ranker flag
result_enum = engine.retrieve(
    "find tests",
    ranker=RankerType.ARM101,
    task_type=TaskType.CODE2TEST,
)
assert result_enum.ranker == "arm101"

# 4. Default ranker preserves exact legacy behavior
result_default = engine.retrieve("parse ast")
assert result_default.ranker == "legacy"
```

---

## 4. Defect Remediation Log

During CLI smoke testing, `from_directory` was found to have a missing `ablation_config` parameter in its signature, causing a `NameError` when lines 190 and 214 referenced `ablation_config`. This was promptly fixed:
- Signature updated: `from_directory(cls, repo_dir: str, budget_config: Optional[BudgetConfig] = None, max_files: int = 3000, extra_ignore: List[str] = None, ablation_config: Optional[AblationConfig] = None)`
- End-to-end verification re-run cleanly.
