"""
Milestone 1C: experimental abstention is opt-in.

Covers the Python API, CLI and MCP surfaces:
- Default retrieval never abstains on heuristic grounds.
- Explicit opt-in (BudgetConfig, per-call override, CLI flag, MCP argument) activates the
  existing, unchanged heuristic.
- TaskType.SELECTIVE does not bypass the opt-in requirement.
- Threshold configuration remains functional.
- Empty repositories abstain structurally, independent of the flag.
- RetrievalResult stays schema-compatible.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from reponeedle.cli import main, build_parser
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import (
    AbstentionDiagnostics,
    BudgetConfig,
    FileDoc,
    Query,
    RetrievalResult,
    TaskType,
)

OUT_OF_SCOPE = "Cargo.toml rust tokio async runtime memory leak"
IN_SCOPE = "How to login with user credentials"

LEGACY_RESULT_FIELDS = {
    "query", "task_type", "abstained", "confidence_score", "selected_files", "total_tokens",
    "budget_tokens", "candidate_count", "explanation", "execution_time_ms", "ranker",
    "ranked_files", "rendered_context",
}


def _docs():
    return [
        FileDoc(path="auth.py", content="class Auth:\n    def login(): pass\n", symbols=["Auth", "login"]),
        FileDoc(path="models.py", content="class User:\n    pass\n", symbols=["User"]),
        FileDoc(
            path="tests/test_auth.py",
            content="from auth import Auth\ndef test_login(): pass\n",
            symbols=["test_login"],
            is_test=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Python API
# ---------------------------------------------------------------------------

class TestEngineAbstentionOptIn:

    def test_budget_config_default_is_disabled(self):
        assert BudgetConfig().enable_experimental_abstention is False

    def test_default_retrieval_does_not_abstain_on_out_of_scope_query(self):
        engine = RepoNeedleEngine.from_documents(_docs())
        res = engine.retrieve(OUT_OF_SCOPE, budget_tokens=2000)

        assert res.abstained is False
        assert len(res.selected_files) > 0
        assert res.abstention is not None
        assert res.abstention.enabled is False
        assert res.abstention.status == "disabled"
        assert res.abstention.experimental is True
        assert res.abstention.calibrated is False
        # Heuristic verdict text must not leak into a non-opted-in explanation.
        assert "Confident repository match" not in res.explanation
        assert "Experimental abstention disabled" in res.explanation

    def test_budget_config_opt_in_activates_heuristic(self):
        engine = RepoNeedleEngine.from_documents(
            _docs(), budget_config=BudgetConfig(enable_experimental_abstention=True)
        )
        res = engine.retrieve(OUT_OF_SCOPE, budget_tokens=2000)

        assert res.abstained is True
        assert res.selected_files == []
        assert res.total_tokens == 0
        assert res.explanation.startswith("Abstained:")
        assert "Experimental" in res.explanation
        assert res.abstention.enabled is True
        assert res.abstention.status == "evaluated"
        assert res.abstention.experimental is True
        assert res.abstention.calibrated is False
        assert res.abstention.reason  # heuristic reason propagated

    def test_opt_in_does_not_abstain_on_in_scope_query(self):
        engine = RepoNeedleEngine.from_documents(
            _docs(), budget_config=BudgetConfig(enable_experimental_abstention=True)
        )
        res = engine.retrieve(IN_SCOPE, budget_tokens=2000)
        assert res.abstained is False
        assert len(res.selected_files) > 0
        assert res.abstention.status == "evaluated"
        assert "uncalibrated" in res.explanation

    def test_per_call_override_enables(self):
        engine = RepoNeedleEngine.from_documents(_docs())
        res = engine.retrieve(OUT_OF_SCOPE, budget_tokens=2000, enable_experimental_abstention=True)
        assert res.abstained is True
        assert res.abstention.status == "evaluated"

    def test_per_call_override_disables(self):
        engine = RepoNeedleEngine.from_documents(
            _docs(), budget_config=BudgetConfig(enable_experimental_abstention=True)
        )
        res = engine.retrieve(OUT_OF_SCOPE, budget_tokens=2000, enable_experimental_abstention=False)
        assert res.abstained is False
        assert res.abstention.status == "disabled"

    def test_query_alias_forwards_override(self):
        engine = RepoNeedleEngine.from_documents(_docs())
        res = engine.query(OUT_OF_SCOPE, enable_experimental_abstention=True)
        assert res.abstained is True

    def test_selective_task_type_does_not_bypass_opt_in(self):
        engine = RepoNeedleEngine.from_documents(_docs())

        res = engine.retrieve(OUT_OF_SCOPE, budget_tokens=2000, task_type=TaskType.SELECTIVE)
        assert res.abstained is False
        assert res.abstention.status == "disabled"

        res_q = engine.retrieve(Query(text=OUT_OF_SCOPE, task_type=TaskType.SELECTIVE, budget_tokens=2000))
        assert res_q.abstained is False
        assert res_q.abstention.status == "disabled"

    def test_selective_task_with_opt_in_abstains(self):
        engine = RepoNeedleEngine.from_documents(_docs())
        res = engine.retrieve(
            OUT_OF_SCOPE, task_type=TaskType.SELECTIVE, enable_experimental_abstention=True
        )
        assert res.abstained is True

    @pytest.mark.parametrize("ranker", ["legacy", "bm25", "arm101", "cascade", "change_impact"])
    def test_default_never_abstains_for_any_ranker(self, ranker):
        engine = RepoNeedleEngine.from_documents(_docs())
        res = engine.retrieve(OUT_OF_SCOPE, ranker=ranker)
        assert res.abstained is False
        assert res.abstention.status == "disabled"

    def test_confidence_score_is_identical_with_and_without_opt_in(self):
        """The heuristic formula is unchanged; only whether it decides the outcome differs."""
        engine = RepoNeedleEngine.from_documents(_docs())
        off = engine.retrieve(IN_SCOPE, budget_tokens=2000)
        on = engine.retrieve(IN_SCOPE, budget_tokens=2000, enable_experimental_abstention=True)
        assert off.confidence_score == pytest.approx(on.confidence_score)
        assert [f.path for f in off.selected_files] == [f.path for f in on.selected_files]

    def test_opt_in_decision_matches_raw_abstainer(self):
        """The engine's opt-in decision is exactly the SelectiveAbstainer verdict."""
        engine = RepoNeedleEngine.from_documents(_docs())
        fused = np.array([0.05, 0.04, 0.03], dtype=np.float32)
        raw_abstained, _, _ = engine.abstainer.evaluate_abstention(OUT_OF_SCOPE, fused)
        assert raw_abstained is True
        assert engine.retrieve(OUT_OF_SCOPE, enable_experimental_abstention=True).abstained is True


class TestAbstentionThreshold:

    def test_high_threshold_forces_abstention_when_enabled(self):
        engine = RepoNeedleEngine.from_documents(
            _docs(),
            budget_config=BudgetConfig(enable_experimental_abstention=True, abstention_threshold=0.99),
        )
        res = engine.retrieve(IN_SCOPE, budget_tokens=2000)
        assert res.abstained is True
        assert "below threshold 0.990" in res.explanation
        assert res.abstention.threshold == pytest.approx(0.99)

    def test_zero_threshold_allows_in_scope_retrieval(self):
        engine = RepoNeedleEngine.from_documents(
            _docs(),
            budget_config=BudgetConfig(enable_experimental_abstention=True, abstention_threshold=0.0),
        )
        res = engine.retrieve(IN_SCOPE, budget_tokens=2000)
        assert res.abstained is False
        assert res.abstention.threshold == 0.0

    def test_threshold_is_inert_without_opt_in(self):
        engine = RepoNeedleEngine.from_documents(
            _docs(), budget_config=BudgetConfig(abstention_threshold=0.99)
        )
        res = engine.retrieve(IN_SCOPE, budget_tokens=2000)
        assert res.abstained is False
        assert res.abstention.threshold == pytest.approx(0.99)
        assert engine.abstainer.confidence_threshold == pytest.approx(0.99)


class TestEmptyRepository:

    @pytest.mark.parametrize("opt_in", [False, True])
    def test_empty_repository_abstains_structurally(self, opt_in):
        engine = RepoNeedleEngine.from_documents([])
        res = engine.retrieve("any query", enable_experimental_abstention=opt_in)
        assert res.abstained is True
        assert res.selected_files == []
        assert res.abstention.status == "empty_repository"
        assert res.abstention.enabled is opt_in


class TestSchemaCompatibility:

    def test_legacy_fields_preserved(self):
        engine = RepoNeedleEngine.from_documents(_docs())
        res = engine.retrieve(IN_SCOPE)
        dumped = res.model_dump()
        assert LEGACY_RESULT_FIELDS.issubset(dumped.keys())
        assert set(dumped.keys()) - LEGACY_RESULT_FIELDS == {"abstention"}
        assert isinstance(res.confidence_score, float)
        assert res.packed_files is res.selected_files

    def test_retrieval_result_constructible_without_abstention(self):
        res = RetrievalResult(query="q", task_type=TaskType.COMMENT2CONTEXT)
        assert res.abstention is None
        assert res.abstained is False
        assert res.confidence_score == 1.0

    def test_abstention_diagnostics_defaults(self):
        diag = AbstentionDiagnostics()
        assert diag.enabled is False
        assert diag.status == "disabled"
        assert diag.experimental is True
        assert diag.calibrated is False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@pytest.fixture
def cli_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "cli_repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "auth.py").write_text(
        "class AuthService:\n    def authenticate(self, token: str) -> bool:\n        return token == 'valid'\n",
        encoding="utf-8",
    )
    (repo / "src" / "session.py").write_text(
        "from src.auth import AuthService\n\nclass SessionManager:\n    pass\n",
        encoding="utf-8",
    )
    return repo


class TestCLIAbstentionFlag:

    def test_parser_flag_defaults_false(self):
        parser = build_parser()
        assert parser.parse_args(["q"]).enable_experimental_abstention is False
        assert parser.parse_args(["q", "--enable-experimental-abstention"]).enable_experimental_abstention is True

    def test_json_default_does_not_abstain(self, cli_repo: Path, capsys):
        assert main(["quantum gravity entanglement", "--repo", str(cli_repo), "--json"]) == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert captured.err == ""
        assert data["status"] == "success"
        assert data["abstained"] is False
        assert data["abstention"]["enabled"] is False
        assert data["abstention"]["status"] == "disabled"
        assert data["abstention"]["experimental"] is True
        assert data["abstention"]["calibrated"] is False

    def test_json_with_flag_abstains(self, cli_repo: Path, capsys):
        exit_code = main([
            "quantum gravity entanglement", "--repo", str(cli_repo), "--json",
            "--enable-experimental-abstention",
        ])
        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert data["status"] == "abstained"
        assert data["abstained"] is True
        assert data["selected_files"] == []
        assert data["abstention"]["enabled"] is True
        assert data["abstention"]["status"] == "evaluated"

    def test_json_selective_task_without_flag_does_not_abstain(self, cli_repo: Path, capsys):
        assert main([
            "quantum gravity entanglement", "--repo", str(cli_repo), "--json", "--task", "selective",
        ]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["abstained"] is False
        assert data["abstention"]["status"] == "disabled"

    def test_rich_mode_with_flag_labels_experimental(self, cli_repo: Path, capsys):
        assert main([
            "quantum gravity entanglement", "--repo", str(cli_repo), "--enable-experimental-abstention",
        ]) == 0
        out = capsys.readouterr().out
        assert "System Abstained (experimental heuristic)" in out
        assert "EXPERIMENTAL" in out


# ---------------------------------------------------------------------------
# MCP
# ---------------------------------------------------------------------------

def _extract_payload(res) -> dict:
    if isinstance(res, tuple):
        if len(res) > 1 and isinstance(res[1], dict) and "result" in res[1]:
            return res[1]["result"]
        return json.loads(res[0][0].text)
    if isinstance(res, list):
        return json.loads(res[0].text)
    return json.loads(res.text)


class TestMCPAbstentionOptIn:

    @pytest.fixture(autouse=True)
    def _require_mcp(self):
        pytest.importorskip("mcp")

    @pytest.mark.asyncio
    async def test_retrieve_default_does_not_abstain(self, cli_repo: Path):
        from reponeedle.mcp.server import create_mcp_server
        app = create_mcp_server(repo_dir=str(cli_repo))
        data = _extract_payload(await app.call_tool(
            "reponeedle_retrieve", {"query": "quantum gravity entanglement"}
        ))
        assert data["status"] == "success"
        assert data["abstained"] is False
        assert data["abstention"]["enabled"] is False
        assert data["abstention"]["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_retrieve_explicit_false_and_true(self, cli_repo: Path):
        from reponeedle.mcp.server import create_mcp_server
        app = create_mcp_server(repo_dir=str(cli_repo))

        off = _extract_payload(await app.call_tool(
            "reponeedle_retrieve",
            {"query": "quantum gravity entanglement", "enable_experimental_abstention": False},
        ))
        assert off["abstained"] is False

        on = _extract_payload(await app.call_tool(
            "reponeedle_retrieve",
            {"query": "quantum gravity entanglement", "enable_experimental_abstention": True},
        ))
        assert on["status"] == "abstained"
        assert on["rendered_context"] == ""
        assert on["abstention"]["status"] == "evaluated"
        assert on["abstention"]["calibrated"] is False

    @pytest.mark.asyncio
    async def test_selective_task_without_opt_in_does_not_abstain(self, cli_repo: Path):
        from reponeedle.mcp.server import create_mcp_server
        app = create_mcp_server(repo_dir=str(cli_repo))
        data = _extract_payload(await app.call_tool(
            "reponeedle_retrieve", {"query": "quantum gravity entanglement", "task_type": "selective"}
        ))
        assert data["abstained"] is False

    @pytest.mark.asyncio
    async def test_inspect_reports_abstention_status(self, cli_repo: Path):
        from reponeedle.mcp.server import create_mcp_server
        app = create_mcp_server(repo_dir=str(cli_repo))
        data = _extract_payload(await app.call_tool("reponeedle_inspect", {}))
        assert data["abstention"]["default_enabled"] is False
        assert data["abstention"]["experimental"] is True
        assert data["abstention"]["calibrated"] is False
        assert data["abstention"]["threshold"] == pytest.approx(0.12)
