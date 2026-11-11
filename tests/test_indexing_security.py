"""
Release blocker B1: indexing must never read files whose canonical location is outside the
repository root (symlinks; junctions on Windows), and anchors must apply the same containment.

Symlink-dependent tests run on Linux CI. Where symlink creation is not permitted they skip, unless
REPONEEDLE_FAIL_ON_SKIP=1 (the Linux MCP/security CI job), where a skip fails the run.
Directory-link tests fall back to NTFS junctions on Windows, which need no special privilege.
"""

import json
import os
import sys
from pathlib import Path

import pytest

from reponeedle import RepoNeedleEngine
from reponeedle.cli import main as cli_main, resolve_and_validate_anchors
from reponeedle.engine import is_path_within_root, relpath_escapes_root, resolve_within_root

SENTINEL = "SENTINEL_OUTSIDE_SECRET_5b1f9e"


def _file_symlink(link: Path, target: Path):
    try:
        os.symlink(str(target), str(link))
    except (OSError, NotImplementedError):
        pytest.skip("file symlink creation not permitted in this environment")


def _dir_link(link: Path, target: Path):
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        if sys.platform == "win32":
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
            return "junction"
        pytest.skip("directory symlink creation not permitted in this environment")


@pytest.fixture
def layout(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text(f"API_TOKEN = '{SENTINEL}'\n", encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("def handler():\n    return 'session token refresh'\n", encoding="utf-8")
    (repo / "src" / "real_module.py").write_text("def inside_helper():\n    return 'inside'\n", encoding="utf-8")
    return repo, outside


def _assert_sentinel_unreachable(engine):
    blob = json.dumps(engine.indexing_diagnostics.model_dump())
    assert SENTINEL not in blob
    assert all(SENTINEL not in d.content for d in engine.docs)
    res = engine.retrieve("API_TOKEN secret token", budget_tokens=8000)
    assert SENTINEL not in res.rendered_context
    assert SENTINEL not in json.dumps(res.model_dump(), default=str)


class TestContainmentHelpers:

    def test_within_root_is_component_aware(self, tmp_path: Path):
        root = tmp_path / "repo"
        root.mkdir()
        (tmp_path / "repo2").mkdir()
        assert is_path_within_root(str(root / "a" / "b.py"), str(root))
        assert is_path_within_root(str(root), str(root))
        assert not is_path_within_root(str(tmp_path / "repo2" / "x.py"), str(root))  # shared prefix, other dir
        assert not is_path_within_root(str(tmp_path / "x.py"), str(root))

    @pytest.mark.parametrize("rel,escapes", [
        ("../x.py", True), ("..", True), (os.path.join("..", "a", "b"), True),
        ("..cache/x.py", False), ("...weird/x.py", False), ("a/../b.py", False), ("src/app.py", False),
    ])
    def test_relpath_escapes_root(self, rel, escapes):
        assert relpath_escapes_root(rel) is escapes

    def test_resolve_within_root_regular_file(self, layout):
        repo, _ = layout
        real_root = os.path.realpath(str(repo))
        assert resolve_within_root(str(repo / "src" / "app.py"), real_root) == os.path.realpath(str(repo / "src" / "app.py"))


class TestIndexingContainment:

    def test_file_symlink_to_outside_is_not_indexed(self, layout):
        repo, outside = layout
        _file_symlink(repo / "src" / "creds.py", outside / "secret.py")
        engine = RepoNeedleEngine.from_directory(str(repo))
        diag = engine.indexing_diagnostics
        assert "src/creds.py" not in {d.path for d in engine.docs}
        assert {"src/app.py", "src/real_module.py"} <= {d.path for d in engine.docs}
        assert diag.skipped_symlink_outside_repository == 1
        assert diag.symlink_outside_repository_paths == ["src/creds.py"]
        _assert_sentinel_unreachable(engine)

    def test_directory_link_to_outside_is_not_indexed(self, layout):
        repo, outside = layout
        kind = _dir_link(repo / "linked", outside)
        engine = RepoNeedleEngine.from_directory(str(repo))
        diag = engine.indexing_diagnostics
        assert not any(d.path.startswith("linked/") for d in engine.docs)
        # Directory links (symlinks and junctions alike) are never traversed: only the link's own
        # in-repository path is recorded, so names of files outside the repository are not listed.
        assert diag.skipped_directory_paths == ["linked"], kind
        assert diag.skipped_directories == 1
        assert diag.skipped_directories_outside_repository == 1
        assert diag.symlink_outside_repository_paths == []
        _assert_sentinel_unreachable(engine)

    def test_nested_directories_are_indexed_normally(self, layout):
        repo, _ = layout
        deep = repo / "pkg" / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "leaf.py").write_text("def leaf():\n    return 'leaf'\n", encoding="utf-8")
        (repo / "pkg" / "a" / "mid.py").write_text("def mid():\n    return 1\n", encoding="utf-8")
        engine = RepoNeedleEngine.from_directory(str(repo))
        paths = sorted(d.path for d in engine.docs)
        assert paths == ["pkg/a/b/c/leaf.py", "pkg/a/mid.py", "src/app.py", "src/real_module.py"]
        assert engine.indexing_diagnostics.skipped_directories == 0
        assert engine.indexing_diagnostics.skipped_directory_paths == []

    def test_directory_link_inside_repository_indexed_once_by_real_path(self, layout, caplog):
        """Policy: a directory link resolving inside the repository is not traversed; its target's
        files are indexed exactly once, under their real path. No warning is emitted."""
        repo, _ = layout
        _dir_link(repo / "alias_dir", repo / "src")
        with caplog.at_level("WARNING", logger="reponeedle.engine"):
            engine = RepoNeedleEngine.from_directory(str(repo))
        paths = sorted(d.path for d in engine.docs)
        assert paths == ["src/app.py", "src/real_module.py"]
        diag = engine.indexing_diagnostics
        assert diag.skipped_directory_paths == ["alias_dir"]
        assert diag.skipped_directories_outside_repository == 0
        assert not [r for r in caplog.records if "directory link" in r.getMessage()]

    def test_directory_link_cycle_to_ancestor_is_bounded(self, layout):
        repo, _ = layout
        _dir_link(repo / "src" / "up", repo)  # cycle: repo/src/up -> repo
        engine = RepoNeedleEngine.from_directory(str(repo))
        paths = sorted(d.path for d in engine.docs)
        assert paths == ["src/app.py", "src/real_module.py"]  # each file once; no src/up/... copies
        diag = engine.indexing_diagnostics
        assert diag.skipped_directory_paths == ["src/up"]
        assert diag.skipped_directories_outside_repository == 0
        assert diag.skipped_unreadable_files == 0

    def test_directory_link_cycle_through_parent_does_not_escape(self, layout, tmp_path: Path):
        """repo/src/out -> tmp_path (contains both the repository and the outside directory)."""
        repo, _ = layout
        _dir_link(repo / "src" / "out", tmp_path)
        engine = RepoNeedleEngine.from_directory(str(repo))
        assert sorted(d.path for d in engine.docs) == ["src/app.py", "src/real_module.py"]
        diag = engine.indexing_diagnostics
        assert diag.skipped_directory_paths == ["src/out"]
        assert diag.skipped_directories_outside_repository == 1
        assert diag.symlink_outside_repository_paths == []  # outside names never listed
        _assert_sentinel_unreachable(engine)

    def test_mutual_directory_link_cycle(self, layout):
        repo, _ = layout
        (repo / "d1").mkdir()
        (repo / "d2").mkdir()
        (repo / "d1" / "one.py").write_text("ONE = 1\n", encoding="utf-8")
        (repo / "d2" / "two.py").write_text("TWO = 2\n", encoding="utf-8")
        _dir_link(repo / "d1" / "to_d2", repo / "d2")
        _dir_link(repo / "d2" / "to_d1", repo / "d1")
        engine = RepoNeedleEngine.from_directory(str(repo))
        paths = sorted(d.path for d in engine.docs)
        assert paths == ["d1/one.py", "d2/two.py", "src/app.py", "src/real_module.py"]
        assert engine.indexing_diagnostics.skipped_directory_paths == ["d1/to_d2", "d2/to_d1"]

    def test_broken_directory_link_is_safe(self, layout):
        repo, _ = layout
        gone = repo / "gone_target"
        gone.mkdir()
        _dir_link(repo / "dangling", gone)
        gone.rmdir()
        engine = RepoNeedleEngine.from_directory(str(repo))
        assert sorted(d.path for d in engine.docs) == ["src/app.py", "src/real_module.py"]
        assert not any(p.startswith("dangling/") for p in engine.indexing_diagnostics.skipped_directory_paths)

    def test_link_detection_error_fails_closed(self, layout, monkeypatch):
        """If a directory entry cannot be inspected (os.lstat raises), it is treated as a link:
        not traversed, and recorded."""
        import reponeedle.engine as eng
        repo, _ = layout
        (repo / "uninspectable").mkdir()
        (repo / "uninspectable" / "hidden.py").write_text("HIDDEN = 1\n", encoding="utf-8")
        real_lstat = os.lstat

        def failing_lstat(path, *args, **kwargs):
            if os.path.basename(os.fspath(path)) == "uninspectable":
                raise PermissionError("simulated lstat failure")
            return real_lstat(path, *args, **kwargs)

        monkeypatch.setattr(eng.os, "lstat", failing_lstat)
        assert eng.is_directory_link(str(repo / "uninspectable")) is True
        engine = RepoNeedleEngine.from_directory(str(repo))
        assert "uninspectable/hidden.py" not in {d.path for d in engine.docs}
        assert engine.indexing_diagnostics.skipped_directory_paths == ["uninspectable"]

    def test_revisited_physical_directory_is_skipped(self, layout, monkeypatch):
        """Cycle guard independent of link detection: a directory whose physical identity
        (st_dev, st_ino) was already traversed is not entered again. SIMULATED: os.stat is patched
        so that one directory reports the repository root's identity, as a bind mount of the root
        would. No real bind mount is created (that needs root privileges)."""
        import reponeedle.engine as eng
        repo, _ = layout
        (repo / "mount_like").mkdir()
        (repo / "mount_like" / "dup.py").write_text("DUP = 1\n", encoding="utf-8")
        real_stat = os.stat
        root_stat = real_stat(str(repo))

        def fake_stat(path, *args, **kwargs):
            if os.path.basename(os.fspath(path)) == "mount_like":
                return root_stat  # same identity as the repository root, as a bind mount would have
            return real_stat(path, *args, **kwargs)

        monkeypatch.setattr(eng.os, "stat", fake_stat)
        engine = RepoNeedleEngine.from_directory(str(repo))
        assert "mount_like/dup.py" not in {d.path for d in engine.docs}
        assert engine.indexing_diagnostics.skipped_directory_paths == ["mount_like"]
        assert engine.indexing_diagnostics.skipped_directories_outside_repository == 0

    def test_symlink_inside_repository_still_works(self, layout):
        """Policy: links that resolve inside the repository are indexed under the link path."""
        repo, _ = layout
        _file_symlink(repo / "src" / "alias.py", repo / "src" / "real_module.py")
        engine = RepoNeedleEngine.from_directory(str(repo))
        paths = {d.path for d in engine.docs}
        assert {"src/alias.py", "src/real_module.py"} <= paths
        assert engine.indexing_diagnostics.skipped_symlink_outside_repository == 0

    def test_broken_symlink_and_loop_are_safe(self, layout):
        repo, _ = layout
        _file_symlink(repo / "src" / "broken.py", repo / "src" / "does_not_exist.py")
        _file_symlink(repo / "src" / "loop_a.py", repo / "src" / "loop_b.py")
        _file_symlink(repo / "src" / "loop_b.py", repo / "src" / "loop_a.py")
        engine = RepoNeedleEngine.from_directory(str(repo))
        diag = engine.indexing_diagnostics
        assert {"src/broken.py", "src/loop_a.py", "src/loop_b.py"} <= set(diag.unreadable_paths)
        assert "src/app.py" in {d.path for d in engine.docs}

    def test_cli_json_never_contains_sentinel(self, layout, capsys):
        repo, outside = layout
        _file_symlink(repo / "src" / "creds.py", outside / "secret.py")
        assert cli_main(["API_TOKEN secret", "--repo", str(repo), "--json", "--include-context"]) == 0
        out = capsys.readouterr()
        data = json.loads(out.out)
        assert SENTINEL not in out.out and SENTINEL not in out.err
        assert data["indexing"]["symlink_outside_repository_paths"] == ["src/creds.py"]


class TestAnchorContainment:

    def test_anchor_symlink_to_outside_is_rejected(self, layout):
        repo, outside = layout
        _file_symlink(repo / "src" / "creds.py", outside / "secret.py")
        with pytest.raises(ValueError, match="outside repository root"):
            resolve_and_validate_anchors(str(repo), ["src/creds.py"])

    def test_anchor_symlink_inside_is_accepted(self, layout):
        repo, _ = layout
        _file_symlink(repo / "src" / "alias.py", repo / "src" / "real_module.py")
        assert resolve_and_validate_anchors(str(repo), ["src/alias.py"]) == ["src/alias.py"]

    def test_anchor_name_starting_with_dotdot_is_accepted(self, layout):
        repo, _ = layout
        (repo / "..cache").mkdir()
        (repo / "..cache" / "state.py").write_text("STATE = 1\n", encoding="utf-8")
        assert resolve_and_validate_anchors(str(repo), ["..cache/state.py"]) == ["..cache/state.py"]

    def test_parent_traversal_still_rejected(self, layout, tmp_path: Path):
        repo, _ = layout
        (tmp_path / "sibling.py").write_text("x = 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="outside repository root"):
            resolve_and_validate_anchors(str(repo), ["../sibling.py"])

    def test_mcp_path_validation_accepts_dotdot_name(self, layout):
        from reponeedle.mcp.config import validate_and_normalize_path
        repo, _ = layout
        (repo / "..cache").mkdir()
        (repo / "..cache" / "state.py").write_text("STATE = 1\n", encoding="utf-8")
        assert validate_and_normalize_path(str(repo), "..cache/state.py") == "..cache/state.py"
        with pytest.raises(ValueError):
            validate_and_normalize_path(str(repo), "../outside/secret.py")


class TestMCPContainment:

    @pytest.fixture(autouse=True)
    def _require_mcp(self):
        pytest.importorskip("mcp")

    @pytest.mark.asyncio
    async def test_mcp_retrieve_and_inspect_never_expose_sentinel(self, layout):
        from reponeedle.mcp.server import create_mcp_server
        repo, outside = layout
        _dir_link(repo / "linked", outside)
        try:
            _file_symlink(repo / "src" / "creds.py", outside / "secret.py")
        except pytest.skip.Exception:
            if sys.platform != "win32":
                raise
        app = create_mcp_server(repo_dir=str(repo))
        for name, args in [("reponeedle_retrieve", {"query": "API_TOKEN secret token", "budget_tokens": 8000}),
                           ("reponeedle_inspect", {})]:
            res = await app.call_tool(name, args)
            assert SENTINEL not in json.dumps(res, default=str)
