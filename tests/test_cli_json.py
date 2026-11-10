"""
Tests for RepoNeedle CLI machine-readable JSON output (--json).
"""

import os
import sys
import json
import pytest
from pathlib import Path

from reponeedle.cli import main, build_parser


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Creates a temporary repository structure for CLI testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    src = repo / "src"
    src.mkdir()
    (src / "auth.py").write_text(
        "class AuthService:\n"
        "    def authenticate(self, token: str) -> bool:\n"
        "        return token == 'valid'\n",
        encoding="utf-8"
    )
    (src / "session.py").write_text(
        "from src.auth import AuthService\n\n"
        "class SessionManager:\n"
        "    def __init__(self):\n"
        "        self.auth = AuthService()\n",
        encoding="utf-8"
    )

    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_auth.py").write_text(
        "from src.auth import AuthService\n\n"
        "def test_auth():\n"
        "    service = AuthService()\n"
        "    assert service.authenticate('valid') is True\n",
        encoding="utf-8"
    )
    return repo


class TestCLIJsonOutput:
    """Test suite for --json flag in reponeedle CLI."""

    def test_json_flag_present_in_parser(self):
        parser = build_parser()
        args = parser.parse_args(["query", "--json"])
        assert args.json is True

    def test_json_output_schema_and_types(self, sample_repo: Path, capsys: pytest.CaptureFixture):
        exit_code = main(["authenticate token", "--repo", str(sample_repo), "--json"])
        assert exit_code == 0

        captured = capsys.readouterr()
        # Stderr should be empty on successful JSON run
        assert captured.err == ""

        # Stdout must be strictly valid JSON
        data = json.loads(captured.out)

        # Verify required top-level schema fields
        required_fields = [
            "schema_version",
            "status",
            "query",
            "repository",
            "ranker",
            "task_type",
            "abstained",
            "explanation",
            "budget_tokens",
            "total_tokens",
            "execution_time_ms",
            "confidence_score",
            "selected_files",
        ]
        for field in required_fields:
            assert field in data, f"Missing required JSON field: {field}"

        assert data["schema_version"] == "1.2.0"
        assert data["status"] == "success"
        assert data["query"] == "authenticate token"
        assert data["repository"] == str(sample_repo)
        assert data["ranker"] == "legacy"
        assert isinstance(data["task_type"], str)
        assert data["abstained"] is False
        assert isinstance(data["explanation"], str)
        assert isinstance(data["budget_tokens"], int)
        assert isinstance(data["total_tokens"], int)
        assert isinstance(data["execution_time_ms"], (int, float))
        assert isinstance(data["confidence_score"], (int, float))
        assert isinstance(data["selected_files"], list)
        assert len(data["selected_files"]) > 0

        # Verify selected_files item schema
        file_fields = ["rank", "path", "tier", "token_count", "score", "explanation"]
        for rank_idx, file_item in enumerate(data["selected_files"], start=1):
            for ff in file_fields:
                assert ff in file_item, f"Missing file field '{ff}' in item {file_item}"
            assert file_item["rank"] == rank_idx
            assert isinstance(file_item["path"], str)
            assert isinstance(file_item["tier"], str)
            assert isinstance(file_item["token_count"], int)
            assert isinstance(file_item["score"], (int, float))
            assert isinstance(file_item["explanation"], str)

    def test_no_ansi_or_rich_codes_in_json_stdout(self, sample_repo: Path, capsys: pytest.CaptureFixture):
        exit_code = main(["authenticate", "--repo", str(sample_repo), "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        stdout = captured.out

        # Ensure no ANSI escape sequences
        assert "\x1b" not in stdout
        assert "\033" not in stdout
        assert "[bold" not in stdout
        assert "[cyan" not in stdout
        assert "│" not in stdout
        assert "╭" not in stdout
        assert "Indexing repository..." not in stdout

    def test_json_with_include_context(self, sample_repo: Path, capsys: pytest.CaptureFixture):
        exit_code = main(["authenticate", "--repo", str(sample_repo), "--json", "--include-context"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert "rendered_context" in data
        assert isinstance(data["rendered_context"], str)
        assert "# File: src/auth.py" in data["rendered_context"]

    def test_json_without_include_context_omits_rendered_context(self, sample_repo: Path, capsys: pytest.CaptureFixture):
        exit_code = main(["authenticate", "--repo", str(sample_repo), "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)

        # rendered_context should not bloat response by default
        assert "rendered_context" not in data

    def test_json_with_output_file(self, sample_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture):
        out_file = tmp_path / "saved_context.md"
        exit_code = main([
            "authenticate",
            "--repo", str(sample_repo),
            "--json",
            "--output-file", str(out_file)
        ])
        assert exit_code == 0
        captured = capsys.readouterr()

        # Stdout must remain pure valid JSON with no progress or file save messages
        data = json.loads(captured.out)
        assert data["status"] == "success"

        # File must be written on disk
        assert out_file.exists()
        saved_text = out_file.read_text(encoding="utf-8")
        assert len(saved_text) > 0
        assert "src/auth.py" in saved_text

    def test_json_on_empty_repo(self, tmp_path: Path, capsys: pytest.CaptureFixture):
        empty_repo = tmp_path / "empty_repo"
        empty_repo.mkdir()

        exit_code = main(["find something", "--repo", str(empty_repo), "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert data["schema_version"] == "1.2.0"
        assert data["status"] == "abstained"
        assert data["abstained"] is True
        assert data["selected_files"] == []
        assert data["total_tokens"] == 0

    def test_legacy_mode_unchanged_when_json_not_passed(self, sample_repo: Path, capsys: pytest.CaptureFixture):
        exit_code = main(["authenticate", "--repo", str(sample_repo)])
        assert exit_code == 0
        captured = capsys.readouterr()
        stdout = captured.out

        # Legacy mode prints Rich tables, not pure JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(stdout)

        assert "Retrieved Context" in stdout
        assert "src/auth.py" in stdout

    def test_invalid_repo_returns_exit_code_1_and_stderr(self, tmp_path: Path, capsys: pytest.CaptureFixture):
        non_existent = tmp_path / "does_not_exist"
        exit_code = main(["query", "--repo", str(non_existent), "--json"])
        assert exit_code == 1
        captured = capsys.readouterr()

        assert captured.out == ""
        assert "does not exist or is not a directory" in captured.err
