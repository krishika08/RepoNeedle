"""
Functional tests for the three RepoNeedle MCP tools.
"""

import os
import json
import pytest
from pathlib import Path

pytest.importorskip("mcp")
from mcp.server.fastmcp.exceptions import ToolError

from reponeedle.mcp.server import create_mcp_server


@pytest.fixture
def repo_with_code(tmp_path: Path) -> Path:
    """Creates a sample multi-file project for MCP tool execution tests."""
    repo = tmp_path / "sample_project"
    repo.mkdir()

    src = repo / "src"
    src.mkdir()
    (src / "database.py").write_text(
        "class DatabaseConnection:\n"
        "    def connect(self) -> bool:\n"
        "        return True\n",
        encoding="utf-8",
    )
    (src / "models.py").write_text(
        "from src.database import DatabaseConnection\n\n"
        "class UserModel:\n"
        "    def __init__(self):\n"
        "        self.db = DatabaseConnection()\n"
        "    def get_user(self, user_id: int) -> dict:\n"
        "        return {'id': user_id, 'name': 'Alice'}\n",
        encoding="utf-8",
    )
    (src / "helpers.py").write_text(
        "def format_user_name(name: str) -> str:\n"
        "    return name.title()\n",
        encoding="utf-8",
    )

    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_database.py").write_text(
        "from src.database import DatabaseConnection\n\n"
        "def test_connection():\n"
        "    conn = DatabaseConnection()\n"
        "    assert conn.connect() is True\n",
        encoding="utf-8",
    )
    return repo


def extract_payload(res) -> dict:
    if isinstance(res, tuple):
        if len(res) > 1 and isinstance(res[1], dict) and "result" in res[1]:
            return res[1]["result"]
        return json.loads(res[0][0].text)
    if isinstance(res, list):
        return json.loads(res[0].text)
    return json.loads(res.text)


class TestMCPTools:
    """Test suite for reponeedle_inspect, reponeedle_retrieve, and reponeedle_change_impact."""

    @pytest.mark.asyncio
    async def test_reponeedle_inspect_tool(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        res = await app.call_tool("reponeedle_inspect", {})
        data = extract_payload(res)

        assert data["status"] == "ready"
        assert data["indexed_file_count"] == 4
        assert len(data["indexed_path_examples"]) == 4
        assert ".py" in data["supported_file_types"]
        assert "change_impact" in data["active_rankers"]
        assert data["default_ranker"] == "legacy"
        assert data["budget_config"]["max_tokens"] == 4000
        assert data["index_initialization"]["status"] == "initialized"

    @pytest.mark.asyncio
    async def test_reponeedle_retrieve_success(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        res = await app.call_tool("reponeedle_retrieve", {"query": "connect database"})
        data = extract_payload(res)

        assert data["status"] == "success"
        assert data["abstained"] is False
        assert len(data["selected_files"]) > 0
        assert data["budget_tokens"] == 4000
        assert data["total_tokens"] <= 4000
        assert isinstance(data["rendered_context"], str)
        assert len(data["rendered_context"]) > 0
        assert "src/database.py" in [sf["path"] for sf in data["selected_files"]]

    @pytest.mark.asyncio
    async def test_reponeedle_retrieve_budget_enforcement(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        # Request a tiny budget of 150 tokens
        res = await app.call_tool("reponeedle_retrieve", {"query": "connect database", "budget_tokens": 150})
        data = extract_payload(res)

        assert data["status"] == "success"
        assert data["budget_tokens"] == 150
        assert data["total_tokens"] <= 150

    @pytest.mark.asyncio
    async def test_reponeedle_retrieve_different_rankers(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        rankers = ["legacy", "bm25", "cascade", "arm101", "change_impact"]

        for rk in rankers:
            res = await app.call_tool("reponeedle_retrieve", {"query": "database connection", "ranker": rk})
            data = extract_payload(res)
            assert data["status"] == "success"
            assert data["ranker"] == rk

    @pytest.mark.asyncio
    async def test_reponeedle_retrieve_invalid_ranker_raises_error(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        with pytest.raises(ToolError, match="Unknown ranker 'unknown_ranker'"):
            await app.call_tool("reponeedle_retrieve", {"query": "test", "ranker": "unknown_ranker"})

    @pytest.mark.asyncio
    async def test_reponeedle_retrieve_invalid_task_type_raises_error(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        with pytest.raises(ToolError, match="Unknown task_type 'unknown_task'"):
            await app.call_tool("reponeedle_retrieve", {"query": "test", "task_type": "unknown_task"})

    @pytest.mark.asyncio
    async def test_reponeedle_retrieve_empty_query_raises_error(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        with pytest.raises(ToolError, match="Query string cannot be empty"):
            await app.call_tool("reponeedle_retrieve", {"query": "   "})

    @pytest.mark.asyncio
    async def test_reponeedle_retrieve_with_anchor_files(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        res = await app.call_tool("reponeedle_retrieve", {
            "query": "Fix database connection timeout",
            "ranker": "change_impact",
            "anchor_files": ["src/database.py"]
        })
        data = extract_payload(res)

        assert data["status"] == "success"
        paths = [sf["path"] for sf in data["selected_files"]]
        assert "src/models.py" in paths

    @pytest.mark.asyncio
    async def test_reponeedle_change_impact_single_anchor(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        res = await app.call_tool("reponeedle_change_impact", {
            "anchor_files": ["src/database.py"],
            "query": "Assess database refactor"
        })
        data = extract_payload(res)

        assert data["status"] == "success"
        assert data["anchor_files"] == ["src/database.py"]
        assert len(data["affected_files"]) > 0
        assert isinstance(data["rendered_context"], str)
        assert len(data["rendered_context"]) > 0

        affected_paths = [af["path"] for af in data["affected_files"]]
        assert "src/models.py" in affected_paths
        assert "tests/test_database.py" in affected_paths

        # SFS validation
        for af in data["affected_files"]:
            if af["path"] == "src/database.py":
                assert "Suppressed query seed" in af["explanation"]

    @pytest.mark.asyncio
    async def test_reponeedle_change_impact_multiple_anchors(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        res = await app.call_tool("reponeedle_change_impact", {
            "anchor_files": ["src/database.py", "src/models.py"],
            "query": "Assess user database changes"
        })
        data = extract_payload(res)

        assert data["status"] == "success"
        assert len(data["anchor_files"]) == 2

    @pytest.mark.asyncio
    async def test_reponeedle_change_impact_empty_anchors_raises_error(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        with pytest.raises(ToolError, match="At least one anchor file is required"):
            await app.call_tool("reponeedle_change_impact", {"anchor_files": []})

    @pytest.mark.asyncio
    async def test_reponeedle_change_impact_invalid_anchor_raises_error(self, repo_with_code: Path):
        app = create_mcp_server(repo_dir=str(repo_with_code))
        with pytest.raises(ToolError, match="does not exist or is not a regular file"):
            await app.call_tool("reponeedle_change_impact", {"anchor_files": ["src/missing.py"]})

    @pytest.mark.asyncio
    async def test_reponeedle_retrieve_abstention(self, tmp_path: Path):
        """Verifies abstained result formatting when query has 0% overlap on toy repo
        and the experimental abstention heuristic is explicitly enabled (opt-in since 1.2.0)."""
        empty_repo = tmp_path / "toy_empty"
        empty_repo.mkdir()
        src = empty_repo / "src"
        src.mkdir()
        (src / "unrelated.py").write_text("class Unrelated:\n    pass\n", encoding="utf-8")

        app = create_mcp_server(repo_dir=str(empty_repo))
        res = await app.call_tool(
            "reponeedle_retrieve",
            {"query": "quantum gravity entanglement", "enable_experimental_abstention": True},
        )
        data = extract_payload(res)

        assert data["status"] == "abstained"
        assert data["abstained"] is True
        assert data["selected_files"] == []
        assert data["rendered_context"] == ""
        assert "Abstained" in data["explanation"]
