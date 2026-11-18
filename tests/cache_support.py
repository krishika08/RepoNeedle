"""
Helpers for the Stage 1 persistent index-cache tests (not a test module).

Every cached engine is compared with a fresh UNCACHED ``from_directory()`` over the same files with the Stage 0
differential harness (tests/index_equivalence.py).
"""

import json
import os
import pickle
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from equivalence_fixture import FILES, write_files
from index_equivalence import assert_equivalent, compare_index_state, load_queries
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig

ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
SAMPLE = load_queries()[::15]       # 15 queries across the categories (the full corpus runs in dedicated tests)


def make_repo(tmp_path: Path, files: Optional[Dict[str, str]] = None, name: str = "repo") -> Path:
    return write_files(tmp_path / name, FILES if files is None else files)


def cache_config(tmp_path: Path, **kw) -> IndexCacheConfig:
    return IndexCacheConfig(cache_dir=str(tmp_path / "cache"), **kw)


def cached(repo: Path, cfg: IndexCacheConfig, **kw) -> RepoNeedleEngine:
    return RepoNeedleEngine.from_directory(str(repo), index_cache=cfg, **kw)


def fresh(repo: Path, **kw) -> RepoNeedleEngine:
    return RepoNeedleEngine.from_directory(str(repo), **kw)


def last(engine) -> dict:
    return engine.index_cache_diagnostics["last_update"]


def db_files(cfg: IndexCacheConfig) -> List[Path]:
    d = Path(cfg.cache_dir)
    return sorted(d.glob("*.sqlite3")) if d.exists() else []


def db_path(cfg: IndexCacheConfig) -> Path:
    files = db_files(cfg)
    assert len(files) == 1, files
    return files[0]


def write(repo: Path, rel: str, text: str) -> None:
    target = repo.joinpath(*rel.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def assert_same_as_fresh(engine, repo: Path, label: str, queries=SAMPLE, packing_queries: Optional[int] = 5,
                         **kw) -> None:
    assert_equivalent(engine, fresh(repo, **kw), label=label, queries=queries, packing_queries=packing_queries)


def index_state_matches(engine, repo: Path, **kw) -> bool:
    return not any(compare_index_state(engine, fresh(repo, **kw)).values())


def published_generation(cfg: IndexCacheConfig) -> Optional[int]:
    path = db_path(cfg)
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'current_generation'").fetchone()
        return int(row[0]) if row else None
    finally:
        conn.close()


def run_python(code: str, *args: str, env: Optional[dict] = None, timeout: int = 600,
               check: bool = True) -> subprocess.CompletedProcess:
    """Runs ``code`` in a fresh interpreter with this checkout and the tests directory importable."""
    full_env = {**os.environ, **(env or {}), "PYTHONPATH": os.pathsep.join([str(ROOT), str(TESTS)])}
    res = subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True, env=full_env,
                         timeout=timeout, cwd=str(ROOT))
    if check and res.returncode != 0:
        raise AssertionError(f"child failed ({res.returncode}):\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
    return res


CHILD_CAPTURE = r'''
import pickle, sys
from index_equivalence import capture_all, load_queries
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import IndexCacheConfig
repo, cache_dir, out, step = sys.argv[1:5]
cfg = None if cache_dir == "-" else IndexCacheConfig(cache_dir=cache_dir)
engine = RepoNeedleEngine.from_directory(repo, index_cache=cfg)
queries = load_queries()[::int(step)]
with open(out, "wb") as fh:
    pickle.dump({"capture": capture_all(engine, queries=queries, packing_queries=5),
                 "report": engine.index_cache_diagnostics["last_update"] if cfg else None}, fh)
'''

# RepoNeedle iterates sets of strings in several places (for example BM25 document frequencies, class-to-test
# invocation edges and change-impact explanations), so dict orders and some explanation texts depend on Python's
# per-process hash seed even WITHOUT a cache. Cross-process comparisons therefore run the cached engine and the
# uncached reference in separate child processes with the same PYTHONHASHSEED.
HASH_SEED = "0"


def capture_in_child(repo: Path, cfg: Optional[IndexCacheConfig], out: Path, step: int = 15,
                     seed: str = HASH_SEED) -> dict:
    """Builds the engine (cached with ``cfg``, or uncached when ``cfg`` is None) in a FRESH PROCESS."""
    run_python(CHILD_CAPTURE, str(repo), cfg.cache_dir if cfg else "-", str(out), str(step),
               env={"PYTHONHASHSEED": seed})
    with open(out, "rb") as fh:   # test-only transport between test processes; never used by the cache
        return pickle.load(fh)


def report_json(engine) -> str:
    return json.dumps(last(engine), sort_keys=True)
