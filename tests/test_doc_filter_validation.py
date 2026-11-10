"""
Milestone 2B: documentation-filter validation harness and filter behaviour.

Covers the existing (unchanged) engine filter semantics, false-negative behaviour for gold
documentation files, the statistical helpers of the experiment, and integrity of the frozen
pre-registered split.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))

import run_doc_filter_validation as V  # noqa: E402
from reponeedle.engine import RepoNeedleEngine  # noqa: E402
from reponeedle.models import AblationConfig, FileDoc  # noqa: E402

PHASE2 = ROOT / "reports" / "experimental" / "phase2_documentation_filter"

CONTENT = "class SessionManager:\n    def refresh_token(self):\n        return 'session timeout refresh'\n"


def _engine():
    docs = [
        FileDoc(path="docs/session.md", content="# Session timeout refresh guide\n" + CONTENT),
        FileDoc(path="README.rst", content="Session timeout refresh token overview\n" + CONTENT),
        FileDoc(path="src/session.py", content=CONTENT),
        FileDoc(path="src/other.py", content="def unrelated():\n    return 42\n"),
    ]
    return RepoNeedleEngine.from_documents(docs)


def _ranked(engine, cfg):
    return engine.retrieve("session timeout refresh token", budget_tokens=4000, ablation_config=cfg).ranked_files


class TestFilterSemantics:

    def test_filter_is_off_by_default(self):
        cfg = AblationConfig()
        assert cfg.enable_doc_filter is False
        assert cfg.doc_filter_penalty == 0.5

    @pytest.mark.parametrize("path,expected", [
        ("docs/guide.md", True), ("README.rst", True), ("CHANGELOG.txt", True), (".github/workflows/ci.yml", True),
        ("site/index.html", True), ("src/tutorial/intro.py", True), ("pkg/doc/conf.py", True),
        ("src/session.py", False), ("tests/test_docs_helpers.py", False), ("Makefile", False),
    ])
    def test_predicate_replica(self, path, expected):
        assert V.is_doc(path) is expected

    def test_predicate_is_broader_than_documentation(self):
        """Documented limitation: the existing path predicate also matches non-documentation files."""
        assert V.is_doc("requirements.txt") and V.is_doc("CMakeLists.txt") and V.is_doc("lib/pydoc/x.py")

    def test_penalty_zero_demotes_docs_below_matching_code(self):
        e = _engine()
        on = _ranked(e, AblationConfig(enable_doc_filter=True, doc_filter_penalty=0.0))
        assert on.index("src/session.py") < on.index("docs/session.md")
        assert on.index("src/session.py") < on.index("README.rst")

    def test_penalty_one_is_a_no_op(self):
        e = _engine()
        assert _ranked(e, AblationConfig()) == _ranked(e, AblationConfig(enable_doc_filter=True, doc_filter_penalty=1.0))

    def test_gold_documentation_is_demoted_never_removed(self):
        """False-negative regression: the filter must keep documentation files in the ranking."""
        e = _engine()
        for pen in (0.5, 0.25, 0.0):
            ranked = _ranked(e, AblationConfig(enable_doc_filter=True, doc_filter_penalty=pen))
            assert {"docs/session.md", "README.rst"} <= set(ranked)
            assert len(ranked) == 4

    def test_off_arm_with_explicit_config_matches_default(self):
        e = _engine()
        default = e.retrieve("session timeout refresh token", budget_tokens=8000)
        explicit = e.retrieve("session timeout refresh token", budget_tokens=8000, ablation_config=AblationConfig())
        assert default.ranked_files == explicit.ranked_files
        assert [f.path for f in default.selected_files] == [f.path for f in explicit.selected_files]


class TestStatistics:

    def test_holm_known_example(self):
        adj = V.holm([0.01, 0.04, 0.03, 0.005])
        assert adj == pytest.approx([0.03, 0.06, 0.06, 0.02])

    def test_holm_is_monotone_and_capped(self):
        adj = V.holm([0.5, 0.9, 0.01])
        assert max(adj) <= 1.0 and adj[2] == pytest.approx(0.03)

    def test_regression_p_value_direction(self):
        clusters = [f"r{i % 5}" for i in range(50)]
        _, p_harm = V.bootstrap([-0.1] * 50, clusters, n_boot=500)
        _, p_gain = V.bootstrap([+0.1] * 50, clusters, n_boot=500)
        assert p_harm < 0.01 and p_gain > 0.99

    def test_canonical_hash_is_order_independent(self):
        assert V.canonical_hash({"b": 1, "a": [1, 2]}) == V.canonical_hash({"a": [1, 2], "b": 1})


@pytest.mark.skipif(not (PHASE2 / "split.json").exists(), reason="pre-registered split not generated")
class TestFrozenSplit:

    def test_split_hash_matches_record_and_protocol(self):
        split = V.load_split(verify=True)
        assert split["seed"] == V.PROTOCOL["split"]["seed"]

    def test_repositories_assigned_exactly_once_and_stratified(self):
        split = json.loads((PHASE2 / "split.json").read_text(encoding="utf-8"))
        assign = split["assignment"]
        assert len(assign) == 25 and set(assign.values()) == {"dev", "test"}
        assert sum(v == "test" for v in assign.values()) == V.PROTOCOL["split"]["test_repositories"]
        for task, info in split["repositories_per_task"].items():
            assert info["dev"] >= 1 and info["test"] >= 1
            assert abs(info["test"] - info["target_test"]) <= 1

    def test_results_never_cross_splits(self):
        split = json.loads((PHASE2 / "split.json").read_text(encoding="utf-8"))
        for phase in ("dev", "test"):
            for p in (PHASE2 / phase).glob("shard_*.jsonl") if (PHASE2 / phase).exists() else []:
                for line in open(p, encoding="utf-8"):
                    r = json.loads(line)
                    assert split["assignment"][r["repo"]] == phase
