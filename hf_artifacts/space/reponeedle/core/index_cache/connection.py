"""
SQLite connection lifecycle (design section 10.1).

- ``isolation_level=None``: Python never opens a transaction implicitly, so the code issues every BEGIN itself and
  no PRAGMA can end up inside a transaction.
- Every setting is applied outside any transaction and READ BACK. A connection whose effective settings differ from
  the required ones is refused (PersistenceUnavailable): persistence is then disabled for the run, never weakened.
- Writer: WAL, synchronous=FULL for the connection's whole lifetime, foreign keys, busy timeout, secure_delete (freed
  pages are overwritten with zeros, see the persist_exclude purge), incremental auto-vacuum on new databases, and
  fullfsync/checkpoint_fullfsync on macOS (plain fsync does not flush the drive cache there).
- Reader: query_only, busy timeout; ``mode=ro`` for read-only caches.
"""

import sqlite3
import sys
from pathlib import Path

from reponeedle.core.index_cache.errors import PersistenceUnavailable
from reponeedle.core.index_cache.schema import APPLICATION_ID, DDL, SCHEMA_VERSION

# Lowest SQLite version exercised by the test suite and CI (recorded in the Stage 1 report). Older libraries are
# not known to behave as the protocol requires, so persistence is disabled on them.
MIN_SQLITE_VERSION = (3, 37, 0)


def check_sqlite_version() -> None:
    if sqlite3.sqlite_version_info < MIN_SQLITE_VERSION:
        raise PersistenceUnavailable(
            f"SQLite {sqlite3.sqlite_version} is older than the minimum tested version "
            f"{'.'.join(map(str, MIN_SQLITE_VERSION))}")


def _pragma(conn: sqlite3.Connection, name: str):
    row = conn.execute(f"PRAGMA {name}").fetchone()
    return row[0] if row else None


def _verify(conn: sqlite3.Connection, expected: dict) -> None:
    actual = {name: _pragma(conn, name) for name in expected}
    if isinstance(actual.get("journal_mode"), str):
        actual["journal_mode"] = actual["journal_mode"].lower()
    if actual != expected:
        raise PersistenceUnavailable(f"SQLite settings could not be applied: expected {expected}, got {actual}")


def open_writer(path: Path, busy_timeout_s: float) -> sqlite3.Connection:
    """Opens (and if needed creates) the database for writing, with verified settings."""
    check_sqlite_version()
    try:
        conn = sqlite3.connect(str(path), isolation_level=None, timeout=busy_timeout_s, check_same_thread=True)
    except sqlite3.Error as exc:
        raise PersistenceUnavailable(f"cannot open the cache database: {type(exc).__name__}") from exc
    try:
        busy_ms = int(busy_timeout_s * 1000)
        new = _pragma(conn, "page_count") == 0
        if new:
            conn.execute("PRAGMA auto_vacuum = INCREMENTAL")      # only effective before the first table
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {busy_ms}")
        conn.execute("PRAGMA secure_delete = ON")
        expected = {"journal_mode": "wal", "synchronous": 2, "foreign_keys": 1, "busy_timeout": busy_ms,
                    "secure_delete": 1}
        if sys.platform == "darwin":
            conn.execute("PRAGMA fullfsync = ON")
            conn.execute("PRAGMA checkpoint_fullfsync = ON")
            expected.update(fullfsync=1, checkpoint_fullfsync=1)
        _verify(conn, expected)
        if new:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                for statement in DDL.split(";"):
                    if statement.strip():
                        conn.execute(statement)
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            if _pragma(conn, "auto_vacuum") != 2:
                raise PersistenceUnavailable("incremental auto-vacuum could not be enabled")
        return conn
    except PersistenceUnavailable:
        conn.close()
        raise
    except sqlite3.Error as exc:
        conn.close()
        raise PersistenceUnavailable(f"cannot configure the cache database: {type(exc).__name__}: {exc}") from exc


def open_reader(path: Path, busy_timeout_s: float, read_only: bool) -> sqlite3.Connection:
    """Opens an existing database for reading. The caller loads a generation inside ONE read transaction."""
    check_sqlite_version()
    target = (path.resolve().as_uri() + "?mode=ro") if read_only else str(path)
    conn = sqlite3.connect(target, uri=read_only, isolation_level=None, timeout=busy_timeout_s)
    try:
        busy_ms = int(busy_timeout_s * 1000)
        conn.execute(f"PRAGMA busy_timeout = {busy_ms}")
        conn.execute("PRAGMA query_only = ON")
        _verify(conn, {"busy_timeout": busy_ms, "query_only": 1})
        return conn
    except BaseException:
        conn.close()
        raise
