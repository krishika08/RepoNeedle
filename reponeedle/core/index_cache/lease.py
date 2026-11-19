"""
Cross-process cache-use leases (V2 Stage 2 hardening of size-limit eviction).

Every RepoNeedle process that opens a cache database (to load it or to write it) first takes a SHARED lease on the
database's lock file (``<database>.lease``) and holds it until its connections are closed. Eviction
(``store.enforce_total_limit``) deletes a database only while holding an EXCLUSIVE lease on it, acquired without
waiting; if any process holds a shared lease the database is skipped and the size limit may stay exceeded.

The leases are operating-system file locks, so they are released automatically when a process exits or is killed
(no PID records, nothing to go stale):
- POSIX: ``fcntl.flock`` (LOCK_SH / LOCK_EX) on the lock file;
- Windows: ``LockFileEx`` on the lock file's first byte, shared or exclusive, through ``ctypes``.

Only the standard library is used. Lock files are never deleted: removing a lock file that another process is about
to lock would let two processes hold "exclusive" locks on different files with the same name.
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional

from reponeedle.core.index_cache.errors import PersistenceUnavailable

LEASE_SUFFIX = ".lease"

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    import msvcrt

    _LOCKFILE_FAIL_IMMEDIATELY = 0x1
    _LOCKFILE_EXCLUSIVE_LOCK = 0x2
    _ERROR_LOCK_VIOLATION = 33
    _ERROR_IO_PENDING = 997

    class _OVERLAPPED(ctypes.Structure):
        _fields_ = [("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p), ("Offset", wintypes.DWORD),
                    ("OffsetHigh", wintypes.DWORD), ("hEvent", wintypes.HANDLE)]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _LockFileEx = _kernel32.LockFileEx
    _LockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                            ctypes.POINTER(_OVERLAPPED)]
    _LockFileEx.restype = wintypes.BOOL
    _UnlockFileEx = _kernel32.UnlockFileEx
    _UnlockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                              ctypes.POINTER(_OVERLAPPED)]
    _UnlockFileEx.restype = wintypes.BOOL

    def _try_lock(fd: int, exclusive: bool) -> bool:
        handle = msvcrt.get_osfhandle(fd)
        flags = _LOCKFILE_FAIL_IMMEDIATELY | (_LOCKFILE_EXCLUSIVE_LOCK if exclusive else 0)
        if _LockFileEx(handle, flags, 0, 1, 0, ctypes.byref(_OVERLAPPED())):
            return True
        err = ctypes.get_last_error()
        if err in (_ERROR_LOCK_VIOLATION, _ERROR_IO_PENDING):
            return False
        raise OSError(err, "LockFileEx failed")

    def _unlock(fd: int) -> None:
        _UnlockFileEx(msvcrt.get_osfhandle(fd), 0, 1, 0, ctypes.byref(_OVERLAPPED()))
else:
    import errno
    import fcntl

    def _try_lock(fd: int, exclusive: bool) -> bool:
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            return True
        except OSError as exc:
            if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
                return False
            raise

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


def lease_path(db_path: Path) -> Path:
    return Path(str(db_path) + LEASE_SUFFIX)


class CacheLease:
    """A shared or exclusive lease on one cache database. Use as a context manager or call ``release()``."""

    def __init__(self, db_path: Path):
        self.path = lease_path(db_path)
        self._fd: Optional[int] = None
        self.exclusive = False

    def _open(self, create: bool) -> bool:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        try:
            self._fd = os.open(str(self.path), os.O_RDWR | (os.O_CREAT if create else 0) | nofollow, 0o600)
            return True
        except FileNotFoundError:
            return False
        except PermissionError:
            if create:
                raise
        try:   # read-only clients: a lock through a read-only descriptor is enough for a shared lease
            self._fd = os.open(str(self.path), os.O_RDONLY | nofollow)
            return True
        except FileNotFoundError:
            return False

    def acquire_shared(self, timeout_s: float, create: bool = True) -> bool:
        """
        Waits up to ``timeout_s`` for a shared lease (an evictor holds the exclusive lease only briefly). Returns
        False when the lock file does not exist and ``create`` is False (nothing to protect). Raises
        PersistenceUnavailable when the lease cannot be obtained in time.
        """
        if os.path.islink(self.path):
            raise PersistenceUnavailable("cache lease file is a symbolic link")
        try:
            if not self._open(create):
                return False
        except OSError as exc:
            raise PersistenceUnavailable(f"cache lease file cannot be opened: {type(exc).__name__}") from exc
        deadline = time.monotonic() + timeout_s
        delay = 0.005
        while True:
            try:
                if _try_lock(self._fd, exclusive=False):
                    return True
            except OSError as exc:
                self._close()
                raise PersistenceUnavailable(f"cache lease cannot be taken: {exc}") from exc
            if time.monotonic() >= deadline:
                self._close()
                raise PersistenceUnavailable("cache lease not obtained in time (the database is being evicted)")
            time.sleep(delay)
            delay = min(0.1, delay * 2)

    def try_exclusive(self) -> bool:
        """Takes the exclusive lease without waiting. False when any other process holds a lease."""
        try:
            if not self._open(create=True):
                return False
            if _try_lock(self._fd, exclusive=True):
                self.exclusive = True
                return True
        except OSError:
            pass
        self._close()
        return False

    def _close(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            finally:
                self._fd = None

    def release(self) -> None:
        if self._fd is not None:
            try:
                _unlock(self._fd)
            except OSError:
                pass
            self._close()
        self.exclusive = False

    @property
    def held(self) -> bool:
        return self._fd is not None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
        return False
