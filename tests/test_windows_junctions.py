"""
Windows NTFS junction traversal. ``os.walk(followlinks=False)`` relies on ``os.path.islink``,
which is False for junctions, so junctions need explicit handling during indexing.

Windows only: these tests skip elsewhere, so this module is deliberately NOT part of the strict
no-skip Linux CI job. Platform-neutral directory-link tests live in test_indexing_security.py.
"""

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="NTFS junctions are Windows-only")

from reponeedle import RepoNeedleEngine  # noqa: E402
import reponeedle.engine as eng  # noqa: E402

SENTINEL = "SENTINEL_JUNCTION_OUTSIDE_31c7"


def _junction(link: Path, target: Path):
    import _winapi
    _winapi.CreateJunction(str(target), str(link))


@pytest.fixture
def layout(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text(f"TOKEN = '{SENTINEL}'\n", encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("def app():\n    return 1\n", encoding="utf-8")
    return repo, outside


def test_junction_is_detected_as_directory_link(layout):
    repo, outside = layout
    _junction(repo / "j", outside)
    assert not os.path.islink(repo / "j")  # why os.walk alone would descend into it
    assert eng.is_directory_link(str(repo / "j"))
    assert not eng.is_directory_link(str(repo / "src"))


def test_junction_detection_without_isjunction(layout, monkeypatch):
    """Python 3.10/3.11 have no os.path.isjunction; detection reads the reparse tag via os.lstat
    and must not depend on it."""
    repo, outside = layout
    _junction(repo / "j", outside)
    monkeypatch.delattr(os.path, "isjunction", raising=False)
    assert eng.is_directory_link(str(repo / "j"))
    assert not eng.is_directory_link(str(repo / "src"))


def test_junction_to_outside_is_not_traversed(layout):
    repo, outside = layout
    _junction(repo / "linked", outside)
    engine = RepoNeedleEngine.from_directory(str(repo))
    diag = engine.indexing_diagnostics
    assert [d.path for d in engine.docs] == ["src/app.py"]
    assert diag.skipped_directory_paths == ["linked"]
    assert diag.skipped_directories_outside_repository == 1
    assert diag.symlink_outside_repository_paths == []
    assert SENTINEL not in diag.model_dump_json()
    assert SENTINEL not in engine.retrieve("TOKEN secret", budget_tokens=8000).rendered_context


def test_junction_cycle_to_repository_root_is_bounded(layout):
    repo, _ = layout
    _junction(repo / "src" / "up", repo)
    engine = RepoNeedleEngine.from_directory(str(repo))
    assert [d.path for d in engine.docs] == ["src/app.py"]
    diag = engine.indexing_diagnostics
    assert diag.skipped_directory_paths == ["src/up"]
    assert diag.skipped_directories_outside_repository == 0
    assert diag.skipped_unreadable_files == 0
