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
* ``--out`` paths inside the snapshot are refused.
"""

import hashlib
import io
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def resolve_commit(rev: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", f"{rev}^{{commit}}"],
                          capture_output=True, text=True, check=True).stdout.strip()


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
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            for member in tar.getmembers():          # git archive output; refuse anything escaping the directory
                if member.name.startswith(("/", "\\")) or ".." in Path(member.name).parts:
                    raise ValueError(f"unexpected archive member {member.name!r}")
            try:
                tar.extractall(self.path, filter="data")
            except TypeError:                        # Python without extraction filters
                tar.extractall(self.path)
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
