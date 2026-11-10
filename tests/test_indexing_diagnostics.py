"""
Milestone 1C: configurable file-size limit and indexing diagnostics.

Covers the Python API, CLI and MCP surfaces:
- Default 500,000-byte limit, custom limits, exact-boundary behavior.
- Invalid limits rejected with clear exceptions.
- Skipped paths recorded deterministically, never file contents.
- Warnings go to stderr / logging, never to JSON stdout.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from reponeedle.cli import main
from reponeedle.engine import (
    DEFAULT_MAX_FILE_SIZE_BYTES,
    RepoNeedleEngine,
    validate_max_file_size_bytes,
)
from reponeedle.models import FileDoc, IndexingDiagnostics

SECRET_MARKER = "SECRET_TOKEN_DO_NOT_LEAK_8f3a2c"


def _write_exact(path: Path, size: int, marker: str = "") -> None:
    """Writes a Python file of exactly `size` bytes (binary write: no newline translation)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    head = f"# {marker}\n".encode("ascii") if marker else b"# filler\n"
    assert size >= len(head)
    path.write_bytes(head + b"x" * (size - len(head)))


@pytest.fixture
def sized_repo(tmp_path: Path) -> Path:
    """Repo with a normal file, one exactly at 1000 bytes and two over 1000 bytes."""
    repo = tmp_path / "sized_repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "auth.py").write_text(
        "class AuthService:\n    def authenticate(self, token):\n        return True\n",
        encoding="utf-8",
    )
    _write_exact(repo / "src" / "at_limit.py", 1000)
    _write_exact(repo / "vendor" / "huge_source.py", 1001, marker=SECRET_MARKER)
    _write_exact(repo / "generated" / "large_module.py", 5000, marker=SECRET_MARKER)
    return repo


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestLimitValidation:

    def test_default_constant(self):
        assert DEFAULT_MAX_FILE_SIZE_BYTES == 500_000

    @pytest.mark.parametrize("bad", [-1, -500_000, 0])
    def test_non_positive_rejected(self, bad, tmp_path: Path):
        with pytest.raises(ValueError, match="positive integer"):
            validate_max_file_size_bytes(bad)
        with pytest.raises(ValueError, match="positive integer"):
            RepoNeedleEngine.from_directory(str(tmp_path), max_file_size_bytes=bad)

    @pytest.mark.parametrize("bad", [1.5, "1000", None, True])
    def test_non_integer_rejected(self, bad, tmp_path: Path):
        with pytest.raises(TypeError, match="positive integer"):
            RepoNeedleEngine.from_directory(str(tmp_path), max_file_size_bytes=bad)

    def test_valid_limits_accepted(self):
        assert validate_max_file_size_bytes(1) == 1
        assert validate_max_file_size_bytes(10_000_000) == 10_000_000


# ---------------------------------------------------------------------------
# Python API
# ---------------------------------------------------------------------------

class TestDirectoryIndexing:

    def test_default_limit_boundaries(self, tmp_path: Path):
        repo = tmp_path / "default_repo"
        _write_exact(repo / "exactly_default.py", DEFAULT_MAX_FILE_SIZE_BYTES)
        _write_exact(repo / "over_default.py", DEFAULT_MAX_FILE_SIZE_BYTES + 1)

        engine = RepoNeedleEngine.from_directory(str(repo))
        diag = engine.indexing_diagnostics
        indexed = {d.path for d in engine.docs}

        assert diag.max_file_size_bytes == 500_000
        assert "exactly_default.py" in indexed
        assert "over_default.py" not in indexed
        assert diag.skipped_paths == ["over_default.py"]
        assert diag.skipped_large_files == 1
        assert diag.indexed_files == 1

    def test_custom_limit(self, sized_repo: Path):
        engine = RepoNeedleEngine.from_directory(str(sized_repo), max_file_size_bytes=1000)
        diag = engine.indexing_diagnostics
        indexed = {d.path for d in engine.docs}

        assert diag.source == "directory"
        assert diag.max_file_size_bytes == 1000
        # File exactly at the limit is indexed; strictly larger files are skipped.
        assert "src/at_limit.py" in indexed
        assert "vendor/huge_source.py" not in indexed
        assert "generated/large_module.py" not in indexed
        assert diag.skipped_large_files == 2
        assert diag.skipped_paths == ["generated/large_module.py", "vendor/huge_source.py"]
        assert diag.indexed_files == len(engine.docs) == 2
        assert diag.skipped_unreadable_files == 0
        assert diag.max_files_reached is False

    def test_raising_limit_indexes_previously_skipped_files(self, sized_repo: Path):
        engine = RepoNeedleEngine.from_directory(str(sized_repo), max_file_size_bytes=10_000)
        assert engine.indexing_diagnostics.skipped_paths == []
        assert engine.indexing_diagnostics.indexed_files == 4

    def test_skipped_paths_are_repo_relative_forward_slash(self, sized_repo: Path):
        engine = RepoNeedleEngine.from_directory(str(sized_repo), max_file_size_bytes=1000)
        for p in engine.indexing_diagnostics.skipped_paths:
            assert "\\" not in p
            assert not Path(p).is_absolute()
            assert (sized_repo / p).is_file()

    def test_no_file_contents_in_diagnostics(self, sized_repo: Path):
        engine = RepoNeedleEngine.from_directory(str(sized_repo), max_file_size_bytes=1000)
        dumped = json.dumps(engine.indexing_diagnostics.model_dump())
        assert SECRET_MARKER not in dumped
        assert "xxxxxxxx" not in dumped

    def test_deterministic_diagnostics(self, sized_repo: Path):
        a = RepoNeedleEngine.from_directory(str(sized_repo), max_file_size_bytes=1000)
        b = RepoNeedleEngine.from_directory(str(sized_repo), max_file_size_bytes=1000)
        assert a.indexing_diagnostics.model_dump() == b.indexing_diagnostics.model_dump()

    def test_warning_logged_without_paths_or_contents(self, sized_repo: Path, caplog):
        with caplog.at_level(logging.WARNING, logger="reponeedle.engine"):
            RepoNeedleEngine.from_directory(str(sized_repo), max_file_size_bytes=1000)
        records = [r for r in caplog.records if r.name == "reponeedle.engine"]
        assert len(records) == 1
        msg = records[0].getMessage()
        assert "skipped 2 file(s)" in msg
        assert "max_file_size_bytes=1000" in msg
        assert SECRET_MARKER not in caplog.text
        assert "huge_source" not in caplog.text

    def test_no_warning_when_nothing_skipped(self, sized_repo: Path, caplog):
        with caplog.at_level(logging.WARNING, logger="reponeedle.engine"):
            RepoNeedleEngine.from_directory(str(sized_repo))
        assert [r for r in caplog.records if r.name == "reponeedle.engine"] == []

    def test_ignored_and_unsupported_files_not_reported(self, tmp_path: Path):
        repo = tmp_path / "ignore_repo"
        _write_exact(repo / "keep.py", 50)
        _write_exact(repo / "ignored_dir" / "big.py", 5000)
        (repo / "blob.bin").write_bytes(b"\0" * 5000)
        (repo / ".gitignore").write_text("ignored_dir/\n", encoding="utf-8")

        engine = RepoNeedleEngine.from_directory(str(repo), max_file_size_bytes=1000)
        assert engine.indexing_diagnostics.skipped_paths == []
        assert [d.path for d in engine.docs] == ["keep.py"]

    def test_max_files_reached_recorded(self, sized_repo: Path):
        engine = RepoNeedleEngine.from_directory(str(sized_repo), max_files=1, max_file_size_bytes=10_000)
        diag = engine.indexing_diagnostics
        assert diag.max_files == 1
        assert diag.max_files_reached is True
        assert diag.indexed_files == 1

    def test_empty_directory(self, tmp_path: Path):
        engine = RepoNeedleEngine.from_directory(str(tmp_path))
        diag = engine.indexing_diagnostics
        assert diag.indexed_files == 0
        assert diag.skipped_paths == []
        assert diag.max_files_reached is False


class TestDocumentIndexing:

    def test_from_documents_source(self):
        engine = RepoNeedleEngine.from_documents([FileDoc(path="a.py", content="x = 1\n")])
        diag = engine.indexing_diagnostics
        assert diag.source == "documents"
        assert diag.indexed_files == 1
        assert diag.max_file_size_bytes is None
        assert diag.skipped_paths == []

    def test_update_documents_refreshes_count(self):
        engine = RepoNeedleEngine.from_documents([FileDoc(path="a.py", content="x = 1\n")])
        engine.update_documents([FileDoc(path="b.py", content="y = 2\n")])
        assert engine.indexing_diagnostics.indexed_files == 2

    def test_model_defaults(self):
        diag = IndexingDiagnostics()
        assert diag.indexed_files == 0
        assert diag.skipped_large_files == 0
        assert diag.skipped_paths == []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLIIndexing:

    def test_json_includes_indexing_diagnostics(self, sized_repo: Path, capsys):
        exit_code = main([
            "authenticate", "--repo", str(sized_repo), "--json", "--max-file-size-bytes", "1000",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)  # stdout is strictly valid JSON

        idx = data["indexing"]
        assert idx["max_file_size_bytes"] == 1000
        assert idx["skipped_large_files"] == 2
        assert idx["skipped_paths"] == ["generated/large_module.py", "vendor/huge_source.py"]
        assert idx["indexed_files"] == 2
        assert SECRET_MARKER not in captured.out
        assert SECRET_MARKER not in captured.err

    def test_json_default_limit_reported(self, sized_repo: Path, capsys):
        assert main(["authenticate", "--repo", str(sized_repo), "--json"]) == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["indexing"]["max_file_size_bytes"] == 500_000
        assert data["indexing"]["skipped_paths"] == []
        assert captured.err == ""

    @pytest.mark.parametrize("bad", ["0", "-5"])
    def test_invalid_limit_exits_1(self, sized_repo: Path, capsys, bad):
        exit_code = main(["authenticate", "--repo", str(sized_repo), "--json", f"--max-file-size-bytes={bad}"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Error:" in captured.err
        assert "positive integer" in captured.err

    def test_rich_mode_notice_goes_to_stderr(self, sized_repo: Path, capsys):
        exit_code = main(["authenticate", "--repo", str(sized_repo), "--max-file-size-bytes", "1000"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Indexing notice" in captured.err
        assert "vendor/huge_source.py" in captured.err
        assert "Indexing notice" not in captured.out
        assert SECRET_MARKER not in captured.err

    def test_subprocess_json_stdout_clean_and_warning_on_stderr(self, sized_repo: Path):
        proc = subprocess.run(
            [sys.executable, "-m", "reponeedle.cli", "authenticate", "--repo", str(sized_repo),
             "--json", "--max-file-size-bytes", "1000"],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data["indexing"]["skipped_large_files"] == 2
        assert "skipped 2 file(s)" in proc.stderr
        assert SECRET_MARKER not in proc.stdout
        assert SECRET_MARKER not in proc.stderr


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


class TestMCPIndexing:

    @pytest.fixture(autouse=True)
    def _require_mcp(self):
        pytest.importorskip("mcp")

    @pytest.mark.asyncio
    async def test_inspect_reports_indexing_statistics(self, sized_repo: Path):
        from reponeedle.mcp.server import create_mcp_server
        app = create_mcp_server(repo_dir=str(sized_repo), max_file_size_bytes=1000)
        data = _extract_payload(await app.call_tool("reponeedle_inspect", {}))

        idx = data["indexing"]
        assert idx["source"] == "directory"
        assert idx["max_file_size_bytes"] == 1000
        assert idx["skipped_large_files"] == 2
        assert idx["skipped_paths"] == ["generated/large_module.py", "vendor/huge_source.py"]
        assert idx["indexed_files"] == data["indexed_file_count"] == 2
        assert SECRET_MARKER not in json.dumps(data)

    @pytest.mark.asyncio
    async def test_inspect_default_limit(self, sized_repo: Path):
        from reponeedle.mcp.server import create_mcp_server
        app = create_mcp_server(repo_dir=str(sized_repo))
        data = _extract_payload(await app.call_tool("reponeedle_inspect", {}))
        assert data["indexing"]["max_file_size_bytes"] == 500_000
        assert data["indexing"]["skipped_paths"] == []

    def test_startup_stderr_reports_exclusions(self, sized_repo: Path, capsys):
        from reponeedle.mcp.server import create_mcp_server
        create_mcp_server(repo_dir=str(sized_repo), max_file_size_bytes=1000)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Indexing exclusions: 2 file(s) over 1000 bytes" in captured.err

    @pytest.mark.parametrize("bad", [0, -1])
    def test_create_server_rejects_invalid_limit(self, sized_repo: Path, bad):
        from reponeedle.mcp.server import create_mcp_server
        with pytest.raises(ValueError, match="positive integer"):
            create_mcp_server(repo_dir=str(sized_repo), max_file_size_bytes=bad)

    def test_server_main_rejects_invalid_limit(self, sized_repo: Path, capsys):
        from reponeedle.mcp.server import main as mcp_main
        assert mcp_main(["--repo", str(sized_repo), "--max-file-size-bytes", "-5"]) == 1
        assert "positive integer" in capsys.readouterr().err

    def test_server_config_validates_limit(self):
        from pydantic import ValidationError
        from reponeedle.mcp.config import MCPServerConfig
        assert MCPServerConfig().max_file_size_bytes == 500_000
        with pytest.raises(ValidationError):
            MCPServerConfig(max_file_size_bytes=0)
