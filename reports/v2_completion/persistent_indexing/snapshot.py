"""
Pinned repository snapshot shared by the persistent-indexing research scripts. Measurement support only.

The first 4A measurements ran against the live working tree while the research scripts and their JSON outputs were
being written into it (``.py`` and ``.json`` are indexed extensions), so two scripts saw different file sets (884 vs
885 files). Every script now measures an export of one commit instead:

* ``git -c core.autocrlf=false archive <commit>`` is extracted into a fresh temporary directory outside the
  repository, so untracked files, local edits and the scripts' own outputs are never measured, and line endings are
  the committed bytes on every platform;
* the indexed file set (discovery order, path, UTF-8 bytes of the decoded text the indexes see) is recorded with a
  digest, so two runs can be checked to have measured exactly the same input;
* ``--out`` paths inside the snapshot are refused;
* every archive member is validated before anything is written (``safe_members``): only regular files and
  directories with relative, '/'-separated paths that stay inside the destination are extracted. Links, devices and
  FIFOs are refused. This holds with or without ``tarfile`` extraction filters, so the fallback for Python versions
  without filters is no less safe.
"""

import hashlib
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import List

ROOT = Path(__file__).resolve().parents[3]


def resolve_commit(rev: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", f"{rev}^{{commit}}"],
                          capture_output=True, text=True, check=True).stdout.strip()


def safe_members(tar: tarfile.TarFile, dest: Path) -> List[tarfile.TarInfo]:
    """Validates every member of ``tar`` for extraction under ``dest``; raises ValueError on the first unsafe one."""
    dest_real = os.path.realpath(dest)
    members = []
    for m in tar.getmembers():
        name = m.name
        if not (m.isreg() or m.isdir()):
            raise ValueError(f"archive member {name!r} is not a regular file or directory (links are refused)")
        if (not name or name.startswith("/") or "\\" in name or ":" in name or "\x00" in name
                or any(part in ("..", "") for part in name.rstrip("/").split("/"))):
            raise ValueError(f"unsafe archive member path {name!r}")
        target = os.path.realpath(os.path.join(dest_real, *PurePosixPath(name).parts))
        if os.path.commonpath([dest_real, target]) != dest_real:
            raise ValueError(f"archive member {name!r} resolves outside the destination")
        members.append(m)
    return members


def extract_archive(data: bytes, dest: Path, use_filter: bool = True) -> None:
    """Extracts a tar archive after validating all members; ``use_filter`` adds tarfile's 'data' filter if present."""
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        members = safe_members(tar, dest)
        if use_filter and hasattr(tarfile, "data_filter"):
            tar.extractall(dest, members=members, filter="data")
        else:
            for m in members:                         # never extract set-uid/set-gid or world-writable modes
                m.mode &= 0o755
            tar.extractall(dest, members=members)


class Snapshot:
    """Context manager: exports ``rev`` to a temporary directory and removes it afterwards."""

    def __init__(self, rev: str = "HEAD"):
        self.commit = resolve_commit(rev)
        self.tree = subprocess.run(["git", "-C", str(ROOT), "rev-parse", f"{self.commit}^{{tree}}"],
                                   capture_output=True, text=True, check=True).stdout.strip()
        self.path = None

    def __enter__(self) -> "Snapshot":
        self.path = Path(tempfile.mkdtemp(prefix="rn_snapshot_"))
        data = subprocess.run(["git", "-C", str(ROOT), "-c", "core.autocrlf=false", "archive", "--format=tar",
                               self.commit], capture_output=True, check=True).stdout
        extract_archive(data, self.path)
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)

    def describe(self, docs, with_list: bool = False) -> dict:
        """The exact file set a measurement used: discovery order, path and UTF-8 bytes of the indexed text.

        ``file_set_sha256`` covers paths and byte counts in discovery order; ``file_set_sorted_sha256`` covers the
        same entries sorted by path (discovery order is filesystem-dependent, the set is not)."""
        files = [[d.path, len(d.content.encode("utf-8"))] for d in docs]

        def digest(rows):
            return hashlib.sha256("\n".join(f"{p}\t{n}" for p, n in rows).encode("utf-8")).hexdigest()

        out = {"commit": self.commit, "tree": self.tree, "files": len(files),
               "source_bytes": sum(n for _, n in files), "file_set_sha256": digest(files),
               "file_set_sorted_sha256": digest(sorted(files))}
        if with_list:
            out["file_list"] = files
        return out


def package_matches_commit(commit: str) -> bool:
    """True when the imported ``reponeedle`` package (this checkout) equals the snapshot commit's package code."""
    diff = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", commit, "--", "reponeedle"])
    untracked = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "reponeedle"],
                               capture_output=True, text=True).stdout.strip()
    return diff.returncode == 0 and not untracked


def check_out_path(out, snapshot_dir) -> None:
    if out is None:
        return
    out = Path(out).resolve()
    if snapshot_dir is not None and Path(snapshot_dir).resolve() in out.parents:
        raise SystemExit(f"--out must not be inside the measured snapshot: {out}")
