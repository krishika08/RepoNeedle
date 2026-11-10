"""
Release 1.2.0 compatibility guards:
- B2: change_impact reports the router-classified task for AUTO queries (1.1.0 behaviour on
  main, as published to PyPI); explicit task types are unchanged; ranking is unaffected (reporting only).
- MCP serverInfo.version reports RepoNeedle's version, not the MCP SDK's.
- The `api` optional extra published with 1.1.0 is retained (optional; used by the demo api.py).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import reponeedle
from reponeedle import RepoNeedleEngine, Query, TaskType
from reponeedle.core.router import WorkflowRouter
from reponeedle.models import FileDoc

ROOT = Path(__file__).resolve().parent.parent
if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

DOCS = [
    FileDoc(path="auth/session.py", content="class SessionManager:\n    def refresh_token(self):\n        return 'x'\n"),
    FileDoc(path="auth/token.py", content="from auth.session import SessionManager\n\ndef issue():\n    return SessionManager()\n"),
    FileDoc(path="tests/test_session.py", content="from auth.session import SessionManager\n\ndef test_refresh():\n    assert SessionManager()\n",
            is_test=True),
]


class TestChangeImpactTaskReporting:

    @pytest.mark.parametrize("text", [
        "Find the unit tests covering SessionManager.refresh_token",
        "Traceback (most recent call last):\n  File \"auth/session.py\", line 3, in refresh_token\nKeyError: 'x'",
        "Assess the impact of changing the session module",
    ])
    def test_auto_query_reports_router_classification(self, text):
        engine = RepoNeedleEngine.from_documents(DOCS)
        expected, _ = WorkflowRouter().classify_intent(Query(text=text, anchor_files=["auth/session.py"]))
        res = engine.retrieve(Query(text=text, anchor_files=["auth/session.py"]), ranker="change_impact")
        assert res.task_type == expected
        assert res.task_type != TaskType.AUTO

    @pytest.mark.parametrize("task", [TaskType.CODE2TEST, TaskType.COMMENT2CONTEXT, TaskType.EDIT2RIPPLE])
    def test_explicit_task_type_is_unchanged(self, task):
        engine = RepoNeedleEngine.from_documents(DOCS)
        res = engine.retrieve("assess session change", ranker="change_impact", task_type=task, anchor_files=["auth/session.py"])
        assert res.task_type == task

    def test_reporting_only_ranking_unchanged(self):
        engine = RepoNeedleEngine.from_documents(DOCS)
        q = "Find the unit tests covering SessionManager.refresh_token"
        auto = engine.retrieve(Query(text=q, anchor_files=["auth/session.py"]), ranker="change_impact")
        for task in (TaskType.CODE2TEST, TaskType.COMMENT2CONTEXT):
            explicit = engine.retrieve(Query(text=q, anchor_files=["auth/session.py"], task_type=task), ranker="change_impact")
            assert explicit.ranked_files == auto.ranked_files
            assert [f.path for f in explicit.selected_files] == [f.path for f in auto.selected_files]

    def test_other_rankers_unaffected(self):
        """The compatibility patch touches only change_impact; other rankers keep their behaviour
        (an AUTO query is reported as AUTO, as in 1.1.0)."""
        engine = RepoNeedleEngine.from_documents(DOCS)
        for ranker in ("bm25", "arm101", "cascade"):
            assert engine.retrieve("session refresh", ranker=ranker).task_type == TaskType.AUTO
            assert engine.retrieve("session refresh", ranker=ranker, task_type=TaskType.CODE2TEST).task_type == TaskType.CODE2TEST


class TestMCPServerVersion:

    @pytest.fixture(autouse=True)
    def _require_mcp(self):
        pytest.importorskip("mcp")

    def test_initialization_options_report_reponeedle_version(self, tmp_path: Path):
        from reponeedle.mcp.server import create_mcp_server
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        app = create_mcp_server(repo_dir=str(tmp_path))
        opts = app._mcp_server.create_initialization_options()
        assert opts.server_name == "reponeedle"
        assert opts.server_version == reponeedle.__version__

    def test_stdio_initialize_reports_reponeedle_version(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        init = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                      "clientInfo": {"name": "t", "version": "1"}}}) + "\n"
        proc = subprocess.run([sys.executable, "-m", "reponeedle.mcp", "--repo", str(tmp_path)], input=init,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        resp = json.loads(proc.stdout.strip().splitlines()[0])
        assert resp["result"]["serverInfo"] == {"name": "reponeedle", "version": reponeedle.__version__}
        assert resp["result"]["protocolVersion"] == "2024-11-05"  # negotiated protocol unchanged


class TestPackageMetadata:

    def _project(self):
        return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    def test_api_extra_retained_for_1_1_0_compatibility(self):
        extras = self._project()["optional-dependencies"]
        assert "api" in extras
        names = {d.split("[")[0].split(">")[0].split("<")[0].split("=")[0].strip().lower() for d in extras["api"]}
        assert names == {"fastapi", "httpx", "uvicorn"}

    def test_api_extra_dependencies_stay_optional(self):
        runtime = " ".join(self._project()["dependencies"]).lower()
        for name in ("fastapi", "httpx", "uvicorn", "mcp"):
            assert name not in runtime

    def test_mcp_and_dev_extras(self):
        extras = self._project()["optional-dependencies"]
        assert any(d.startswith("mcp") for d in extras["mcp"])
        assert any(d.startswith("pytest-asyncio") for d in extras["dev"])

    def test_version_consistency(self):
        assert self._project()["version"] == reponeedle.__version__
