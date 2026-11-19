"""
Repository identity and cache location (design section 5), with the permission, link and network-filesystem checks
of section 11.
"""

import hashlib
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from reponeedle.core.index_cache.errors import PersistenceUnavailable
from reponeedle.core.index_cache.schema import SCHEMA_MAJOR

_REMOTE_FS_TYPES = {"nfs", "nfs4", "cifs", "smb", "smbfs", "smb2", "smb3", "afs", "9p", "sshfs", "fuse.sshfs",
                    "davfs", "fuse.davfs2", "ncpfs", "glusterfs", "fuse.glusterfs", "ceph", "fuse.ceph", "lustre"}


@dataclass(frozen=True)
class CacheLocation:
    repo_root: str        # canonical repository root (realpath)
    repo_id: str          # sha256 hex of the namespaced, case-normalised canonical root
    cache_dir: Path
    db_path: Path
    configured: bool      # True when the user chose cache_dir explicitly


def canonical_root(repo_dir: str) -> str:
    return os.path.realpath(os.path.abspath(repo_dir))


def repo_identity(repo_root: str) -> str:
    return hashlib.sha256(b"reponeedle-index-v1\0" + os.path.normcase(repo_root).encode("utf-8", "surrogatepass")
                          ).hexdigest()


def default_cache_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return Path(base) / "reponeedle" / "index"
    if sys.platform == "darwin":
        return Path(os.path.expanduser("~/Library/Caches")) / "reponeedle" / "index"
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "reponeedle" / "index"


def locate(repo_dir: str, cache_dir: Optional[str]) -> CacheLocation:
    root = canonical_root(repo_dir)
    rid = repo_identity(root)
    directory = Path(os.path.abspath(cache_dir)) if cache_dir else default_cache_dir()
    return CacheLocation(root, rid, directory, directory / f"{rid[:32]}-s{SCHEMA_MAJOR}.sqlite3", cache_dir is not None)


def is_remote_filesystem(path: Path) -> bool:
    """Best-effort detection of network filesystems, on which SQLite locking is unreliable."""
    p = os.path.abspath(str(path))
    if sys.platform == "win32":
        if p.startswith("\\\\"):
            return True
        try:
            import ctypes

            drive = os.path.splitdrive(p)[0] + "\\"
            return ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(drive)) == 4  # DRIVE_REMOTE
        except Exception:
            return False
    if sys.platform.startswith("linux"):
        try:
            best, fstype = "", ""
            with open("/proc/mounts", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) >= 3:
                        mount = parts[1].replace("\\040", " ")
                        if (p == mount or p.startswith(mount.rstrip("/") + "/")) and len(mount) > len(best):
                            best, fstype = mount, parts[2]
            return fstype in _REMOTE_FS_TYPES
        except OSError:
            return False
    return False  # macOS and others: not detected (documented limitation)


def prepare_cache_dir(loc: CacheLocation, create: bool) -> None:
    """
    Creates (when allowed) and checks the cache directory. Raises PersistenceUnavailable when the directory is
    unsuitable: on a network filesystem, group/world-writable without being chosen explicitly, or when the database
    path is a link.
    """
    d = loc.cache_dir
    if create:
        try:
            d.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as exc:
            raise PersistenceUnavailable(f"cache directory cannot be created: {type(exc).__name__}") from exc
    if not d.is_dir():
        raise PersistenceUnavailable("cache directory does not exist")
    if is_remote_filesystem(d):
        raise PersistenceUnavailable("cache directory is on a network filesystem (SQLite locking is unreliable)")
    if os.name == "posix":
        mode = d.stat().st_mode
        if mode & (stat.S_IWGRP | stat.S_IWOTH) and not loc.configured:
            raise PersistenceUnavailable("default cache directory is group- or world-writable")
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(loc.db_path) + suffix)
        if os.path.islink(candidate):
            raise PersistenceUnavailable("cache database path is a symbolic link")


def restrict_permissions(loc: CacheLocation) -> None:
    """POSIX: database files are readable and writable by their owner only."""
    if os.name != "posix":
        return
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(loc.db_path) + suffix)
        try:
            if candidate.exists() and not candidate.is_symlink():
                os.chmod(candidate, 0o600)
        except OSError:
            pass
