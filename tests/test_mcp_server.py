"""
Integration and security tests for RepoNeedle Native MCP Server.
"""

import os
import sys
import json
import pytest
import asyncio
import tempfile
import subprocess
from pathlib import Path

pytest.importorskip("mcp")

from reponeedle.mcp.config import validate_and_normalize_path, MCPServerConfig
from reponeedle.mcp.server import create_mcp_server, build_parser, main


@pytest.fixture
def mcp_test_repo(tmp_path: Path) -> Path:
    """Creates a temporary repository structure for MCP server testing."""
    repo = tmp_path / "mcp_repo"
    repo.mkdir()

    src = repo / "src"
    src.mkdir()
    (src / "service.py").write_text(
        "class Service:\n"
        "    def run(self) -> str:\n"
        "        return 'service running'\n",
        encoding="utf-8",
    )
    (src / "client.py").write_text(
        "from src.service import Service\n\n"
        "class Client:\n"
        "    def __init__(self):\n"
        "        self.svc = Service()\n",
        encoding="utf-8",
    )

    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_service.py").write_text(
        "from src.service import Service\n\n"
        "def test_run():\n"
        "    s = Service()\n"
        "    assert s.run() == 'service running'\n",
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


class TestMCPServerLifecycleAndSecurity:
    """Test suite for server creation, tool discovery, and security boundaries."""

    def test_parser_options(self):
        parser = build_parser()
        args = parser.parse_args(["--repo", "/my/path", "--budget", "8000", "--transport", "stdio", "--no-skeletons"])
        assert args.repo == "/my/path"
        assert args.budget == 8000
        assert args.transport == "stdio"
        assert args.no_skeletons is True

    def test_create_server_valid_repo(self, mcp_test_repo: Path):
        app = create_mcp_server(repo_dir=str(mcp_test_repo), budget=4000)
        assert app.name == "reponeedle"

    def test_create_server_invalid_repo_raises_value_error(self, tmp_path: Path):
        fake_path = tmp_path / "non_existent_dir"
        with pytest.raises(ValueError, match="does not exist or is not a directory"):
            create_mcp_server(repo_dir=str(fake_path))

    @pytest.mark.asyncio
    async def test_tool_discovery(self, mcp_test_repo: Path):
        app = create_mcp_server(repo_dir=str(mcp_test_repo))
        tools = await app.list_tools()
        tool_names = [t.name for t in tools]

        assert "reponeedle_retrieve" in tool_names
        assert "reponeedle_change_impact" in tool_names
        assert "reponeedle_inspect" in tool_names
        assert len(tool_names) == 3

    def test_security_path_validation_empty_path(self, mcp_test_repo: Path):
        with pytest.raises(ValueError, match="File path cannot be empty"):
            validate_and_normalize_path(str(mcp_test_repo), "")

    def test_security_path_validation_non_existent_file(self, mcp_test_repo: Path):
        with pytest.raises(ValueError, match="does not exist or is not a regular file"):
            validate_and_normalize_path(str(mcp_test_repo), "src/phantom.py")

    def test_security_path_validation_path_traversal(self, mcp_test_repo: Path, tmp_path: Path):
        outside_file = tmp_path / "secret.env"
        outside_file.write_text("SECRET_KEY=123", encoding="utf-8")

        with pytest.raises(ValueError, match="resolves outside repository root"):
            validate_and_normalize_path(str(mcp_test_repo), str(outside_file))

        with pytest.raises(ValueError, match="resolves outside repository root"):
            validate_and_normalize_path(str(mcp_test_repo), "../secret.env")

    def test_security_path_validation_symlink_escape(self, mcp_test_repo: Path, tmp_path: Path):
        outside_file = tmp_path / "external.txt"
        outside_file.write_text("External file content", encoding="utf-8")

        symlink_path = mcp_test_repo / "src" / "symlink_escape.py"
        try:
            os.symlink(str(outside_file), str(symlink_path))
        except (OSError, NotImplementedError):
            pytest.skip("Symlink creation not permitted in this environment")

        with pytest.raises(ValueError, match="resolves outside repository root"):
            validate_and_normalize_path(str(mcp_test_repo), "src/symlink_escape.py")

    @pytest.mark.asyncio
    async def test_engine_reuse_across_multiple_calls(self, mcp_test_repo: Path):
        """Verifies the engine is initialized once and reused across tool invocations."""
        app = create_mcp_server(repo_dir=str(mcp_test_repo))

        # Call inspect
        res_inspect = await app.call_tool("reponeedle_inspect", {})
        data_inspect = extract_payload(res_inspect)
        assert data_inspect["status"] == "ready"
        init_time = data_inspect["index_initialization"]["init_time_ms"]

        # Call retrieve
        res_ret = await app.call_tool("reponeedle_retrieve", {"query": "run service"})
        data_ret = extract_payload(res_ret)
        assert data_ret["status"] == "success"

        # Call inspect again: init_time must remain unchanged
        res_inspect_2 = await app.call_tool("reponeedle_inspect", {})
        data_inspect_2 = extract_payload(res_inspect_2)
        assert data_inspect_2["index_initialization"]["init_time_ms"] == init_time

    def test_stdio_protocol_integration(self, mcp_test_repo: Path):
        """Tests live subprocess STDIO transport handshake and clean JSON-RPC message exchange."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "reponeedle.mcp", "--repo", str(mcp_test_repo)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        init_msg = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }) + "\n"

        stdout_data, stderr_data = proc.communicate(input=init_msg, timeout=15)
        assert proc.returncode in (0, None)

        # Stdout must contain ONLY valid JSON-RPC protocol line
        lines = [line.strip() for line in stdout_data.strip().splitlines() if line.strip()]
        assert len(lines) >= 1
        resp = json.loads(lines[0])

        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert "result" in resp
        assert resp["result"]["serverInfo"]["name"] == "reponeedle"

        # Stderr should contain startup diagnostics, not stdout
        assert "[reponeedle-mcp]" in stderr_data
