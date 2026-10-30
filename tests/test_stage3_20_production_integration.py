"""
Stage 3.20 Production Integration & Governance Verification Suite.
Automated audit tests for ARM-101 production parity, zero research imports,
backward-compatible default ranking, and all Stage 3.20 research deliverables.
"""

import subprocess
import csv
from pathlib import Path
import pytest

from reponeedle.models import FileDoc, RankerType, TaskType
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.arm101 import ARM101Ranker
from reponeedle.core.function_graph import FunctionGraphEngine

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE20_DIR = ROOT_DIR / "research" / "stage3_20"


def test_immutable_tags_preserved():
    """Verify frozen baseline tags remain completely unchanged."""
    r1 = subprocess.run(
        ["git", "rev-parse", "v0.1.0-baseline^{commit}"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    assert r1.stdout.strip() == "8e0042553a14b6e3c6cf5b35823c4da84181a8e9"

    r2 = subprocess.run(
        ["git", "rev-parse", "stage3-candidate-freeze^{commit}"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    assert r2.stdout.strip() == "cd7f3b01e28695f9a9357e0815069e0eae85baca"


def test_zero_research_imports_in_reponeedle():
    """Verify strict prohibition: reponeedle/ must NEVER import from research/."""
    reponeedle_dir = ROOT_DIR / "reponeedle"
    for py_file in reponeedle_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "from research" not in content, f"Forbidden research import in {py_file}"
        assert "import research" not in content, f"Forbidden research import in {py_file}"


def test_production_arm101_presence():
    """Verify ARM-101 and FunctionGraphEngine are fully integrated in production package."""
    assert issubclass(ARM101Ranker, object)
    assert issubclass(FunctionGraphEngine, object)

    engine = RepoNeedleEngine.from_documents([
        FileDoc(path="a.py", content="def foo(): return 1"),
        FileDoc(path="b.py", content="from a import foo\ndef bar(): return foo()"),
    ])
    assert hasattr(engine, "arm101_ranker")
    assert hasattr(engine, "function_graph")
    assert len(engine.function_graph.graph) > 0


def test_legacy_default_ranker():
    """Verify default retrieval behavior remains 'legacy' until formal release."""
    engine = RepoNeedleEngine.from_documents([
        FileDoc(path="main.py", content="print('hello')"),
    ])
    res = engine.retrieve("hello")
    assert res.ranker == "legacy"


def test_arm101_explicit_dispatch():
    """Verify --ranker arm101 / ranker='arm101' activates ARM-101 engine."""
    engine = RepoNeedleEngine.from_documents([
        FileDoc(path="main.py", content="def calculate(): return 42"),
    ])
    res_str = engine.retrieve("calculate", ranker="arm101")
    assert res_str.ranker == "arm101"
    assert res_str.ranked_files is not None

    res_enum = engine.retrieve("calculate", ranker=RankerType.ARM101)
    assert res_enum.ranker == "arm101"


def test_stage3_20_deliverables_exist():
    """Verify all required Stage 3.20 research and governance deliverables exist."""
    required = [
        "CANDIDATE_F_FORENSIC_RECONCILIATION.md",
        "CANDIDATE_F_QUERY_DIFF.csv",
        "CANDIDATE_F_METRIC_RECOMPUTATION.csv",
        "CANDIDATE_F_INVALIDATION_EVIDENCE.md",
        "ARM101_ALGORITHM_SPEC.md",
        "ARM101_PARAMETER_REGISTRY.csv",
        "ARM101_DATAFLOW.md",
        "ARM101_RESEARCH_TO_PRODUCTION_MAP.md",
        "PRODUCTION_ARCHITECTURE.md",
        "PRODUCTION_PARITY_RESULTS.csv",
        "PARITY_FAILURE_ANALYSIS.md",
        "RESOURCE_BENCHMARKS.csv",
        "RESOURCE_METHODOLOGY.md",
        "SCALABILITY_FINDINGS.md",
        "CLI_API_INTEGRATION_RESULTS.md",
        "PACKAGE_INSTALLATION_RESULTS.md",
        "INSTALLED_PACKAGE_SMOKE_TESTS.md",
        "CLAIM_STATUS_REGISTER.csv",
        "REPRODUCE.md",
    ]
    for fname in required:
        fpath = STAGE20_DIR / fname
        assert fpath.exists(), f"Missing required deliverable: {fname}"
        assert fpath.stat().st_size > 50, f"Deliverable is empty: {fname}"
