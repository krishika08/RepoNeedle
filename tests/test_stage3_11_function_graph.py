"""
Stage 3.11: Unit Tests for Function-Level Call Graph Engine.
"""

import pytest
import numpy as np
from reponeedle.models import FileDoc
from research.stage3_11.function_graph_engine import (
    FunctionGraphEngine,
    FunctionCascadedRanker,
)


def test_function_graph_ast_extraction():
    content = """
import os
from mypkg.helpers import compute_hash

class Engine:
    def __init__(self, name):
        self.name = name

    def process(self, data):
        h = compute_hash(data)
        return self._format(h)

    def _format(self, val):
        return f"VAL:{val}"

def standalone_task(x):
    return x * 2
"""
    engine = FunctionGraphEngine()
    funcs, calls, symbols, imports = engine.extract_python_ast(content, "src/mypkg/engine.py")

    func_names = [f.name for f in funcs]
    assert "__init__" in func_names
    assert "process" in func_names
    assert "_format" in func_names
    assert "standalone_task" in func_names

    process_func = next(f for f in funcs if f.name == "process")
    assert process_func.is_method is True
    assert process_func.parent_class == "Engine"

    standalone_func = next(f for f in funcs if f.name == "standalone_task")
    assert standalone_func.is_method is False
    assert standalone_func.parent_class is None

    call_names = [c.callee_name for c in calls]
    assert "compute_hash" in call_names
    assert "_format" in call_names


def test_function_graph_resolution_and_edge_types():
    doc1 = FileDoc(
        path="src/utils.py",
        content="""
def unique_worker_fn(val):
    return val + 1
""",
        symbols=["unique_worker_fn"],
        imports=[],
        is_test=False,
    )

    doc2 = FileDoc(
        path="src/main.py",
        content="""
from src.utils import unique_worker_fn

def run_app():
    return unique_worker_fn(42)
""",
        symbols=["run_app"],
        imports=["src.utils"],
        is_test=False,
    )

    fg = FunctionGraphEngine()
    fg.build_graph([doc1, doc2])

    assert len(fg.edges) == 1
    edge = fg.edges[0]
    assert edge.source_path == "src/main.py"
    assert edge.target_path == "src/utils.py"
    assert edge.target_func == "unique_worker_fn"
    assert edge.edge_type == "verified_call"
    assert edge.confidence == 1.0


def test_function_cascaded_ranker_preserves_top_k():
    docs = [
        FileDoc(path=f"file_{i}.py", content=f"def f{i}(): pass", symbols=[f"f{i}"], imports=[], is_test=False)
        for i in range(10)
    ]
    bm25_scores = np.array([10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0], dtype=np.float32)

    ranker = FunctionCascadedRanker(mode="full", top_k_preserve=3)
    ranking = ranker.rank(docs, bm25_scores)

    # Ranks 0, 1, 2 must be exactly file_0, file_1, file_2
    assert ranking[:3] == [0, 1, 2]


def test_function_cascaded_ranker_no_freeze_reorders():
    docs = [
        FileDoc(path="file_0.py", content="def a(): pass", symbols=["a"], imports=[], is_test=False),
        FileDoc(path="file_1.py", content="def b(): pass", symbols=["b"], imports=[], is_test=False),
        FileDoc(path="file_2.py", content="def c(): pass", symbols=["c"], imports=[], is_test=False),
    ]
    bm25_scores = np.array([10.0, 9.9, 9.8], dtype=np.float32)
    # Give semantic boost to file_2
    sem_scores = np.array([0.0, 0.0, 100.0], dtype=np.float32)

    ranker_frozen = FunctionCascadedRanker(mode="full", top_k_preserve=3)
    ranking_frozen = ranker_frozen.rank(docs, bm25_scores, semantic_scores=sem_scores)
    # Frozen ranker does not reorder 0, 1, 2
    assert ranking_frozen[0] == 0

    ranker_unfrozen = FunctionCascadedRanker(mode="no_freeze")
    ranking_unfrozen = ranker_unfrozen.rank(docs, bm25_scores, semantic_scores=sem_scores)
    # Unfrozen ranker allows file_2 to take top rank due to semantic score
    assert ranking_unfrozen[0] == 2


def test_stage3_11_deliverables_exist():
    """Verify that all required Stage 3.11 research deliverables exist."""
    from pathlib import Path
    stage_dir = Path(__file__).resolve().parent.parent / "research" / "stage3_11"
    required = [
        "STAGE3_11_PREREGISTRATION.md",
        "GRAPH_DESIGN.md",
        "EXPERIMENT_REGISTRY.jsonl",
        "GRAPH_COVERAGE_RESULTS.csv",
        "RETRIEVAL_RESULTS.csv",
        "PER_TASK_RESULTS.csv",
        "PER_REPOSITORY_RESULTS.csv",
        "CONTEXT_PACKING_RESULTS.csv",
        "RUNTIME_AND_MEMORY.csv",
        "STATISTICAL_VALIDATION.md",
        "FAILURE_ANALYSIS.md",
        "STAGE3_11_DECISION_REPORT.md",
        "RUN_PROVENANCE.json",
        "REPRODUCE.md",
    ]
    for fname in required:
        fpath = stage_dir / fname
        assert fpath.exists(), f"Required Stage 3.11 deliverable {fname} is missing"


def test_statistical_summary_integrity():
    """Verify statistical summary contents and properties."""
    import json
    from pathlib import Path
    stage_dir = Path(__file__).resolve().parent.parent / "research" / "stage3_11"
    stat_file = stage_dir / "statistical_summary.json"
    assert stat_file.exists()

    with open(stat_file, encoding="utf-8") as f:
        data = json.load(f)

    assert "FUNCTION-GRAPH vs. CONTROL-CASCADE" in data
    fg_res = data["FUNCTION-GRAPH vs. CONTROL-CASCADE"]
    assert fg_res["wins"] == 38
    assert fg_res["losses"] == 24
    assert fg_res["ties"] == 283
    assert fg_res["holm_adjusted_p_value"] < 0.01

    assert "FUNCTION-GRAPH-NO-FREEZE vs. CONTROL-CASCADE" in data
    nf_res = data["FUNCTION-GRAPH-NO-FREEZE vs. CONTROL-CASCADE"]
    assert nf_res["wins"] == 139
    assert nf_res["losses"] == 23
    assert nf_res["mean_delta"] > 0.015
    assert nf_res["holm_adjusted_p_value"] < 0.001

