"""
V2 Stage 1: persistent index cache lifecycle through the public API.

Every scenario ends with the cached engine compared, exactly, with a fresh UNCACHED from_directory() over the same
files (Stage 0 differential harness). The scenario numbers follow the Stage 1 requirements.
"""

import os
import sqlite3
from pathlib import Path

import pytest

from cache_support import (FILES, SAMPLE, assert_same_as_fresh, cache_config, cached, db_files, db_path, fresh,
                           last, make_repo, published_generation, write)
from reponeedle.core.index_cache import IndexCacheError, fingerprints, schema
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import AblationConfig, IndexCacheConfig


# ----------------------------------------------------------------------------------------------- 1-2 cold/warm

def test_cold_start_creates_a_database_and_matches_a_fresh_build(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["state"] == "published" and r["generation"] == 1
    assert r["files_persisted"] == r["files_indexed"] == len(engine.docs) > 0
    # Stage 2: every file has the nine per-file kinds (schema.KINDS), including its two resolution artifacts.
    assert r["files_reused"] == 0 and r["artifacts_written"] == len(schema.KINDS) * len(engine.docs)
    assert set(r["global_structures"].values()) == {"recomputed_in_full"}, r["global_structures"]
    assert len(db_files(cfg)) == 1
    assert_same_as_fresh(engine, repo, "cold cached build")


def test_warm_restart_reuses_every_artifact(tmp_path, monkeypatch):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    from reponeedle.core.function_graph import FunctionGraphEngine
    from reponeedle.core.graph import RepoGraph
    calls = []
    monkeypatch.setattr(RepoGraph, "extract_python_ast", staticmethod(lambda *a: calls.append("ast") or ([], [])))
    monkeypatch.setattr(FunctionGraphEngine, "extract_polyglot", lambda *a: calls.append("polyglot"))
    engine = cached(repo, cfg)
    assert calls == [], "a warm start must not re-run symbol or function extraction for unchanged files"
    monkeypatch.undo()
    r = last(engine)
    assert r["files_reused"] == len(engine.docs) and r["files_extracted"] == 0
    assert r["artifacts_written"] == 0 and r["artifacts_reused"] == len(schema.KINDS) * len(engine.docs)
    assert r["generation"] == 2 and r["added"] == r["deleted"] == r["modified"] == []
    assert_same_as_fresh(engine, repo, "warm cached restart")


def test_full_corpus_equivalence_of_a_warm_restart(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    assert_same_as_fresh(cached(repo, cfg), repo, "warm restart, full 225-query corpus", queries=None,
                         packing_queries=12)


# ------------------------------------------------------------------------------------------- 3-7 file changes

def test_one_changed_file(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    write(repo, "shop/pricing.py", FILES["shop/pricing.py"] + "\n\ndef surcharge(x):\n    return x + 1\n")
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["modified"] == ["shop/pricing.py"] and r["files_extracted"] == 1
    # The changed file's seven per-file artifacts and its two resolutions, plus the resolutions of files whose
    # dependency context changed (re-resolved files whose context is unchanged keep their artifact key).
    resolved = r["work_counters"]["function_graph"]["files_resolved"] + r["work_counters"]["repo_graph"]["files_resolved"]
    assert 9 <= r["artifacts_written"] <= 7 + resolved
    assert_same_as_fresh(engine, repo, "one changed file")


def test_multiple_changed_files_via_refresh(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    for rel in ("shop/cart.py", "web/src/api.ts", "README.md"):
        write(repo, rel, FILES[rel] + "\n// edited\n" if rel.endswith(".ts") else FILES[rel] + "\n# edited\n")
    r = engine.refresh()
    assert sorted(r.modified) == ["README.md", "shop/cart.py", "web/src/api.ts"]
    assert r.files_extracted == 3 and r.state == "published"
    assert_same_as_fresh(engine, repo, "refresh after three edits")


def test_new_deleted_and_renamed_files(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    write(repo, "shop/loyalty.py", "from shop.pricing import apply_discount\n\n\ndef loyalty(x):\n    return x\n")
    os.remove(repo / "legacy" / "importer.py")
    os.rename(repo / "shop" / "api" / "routes.py", repo / "shop" / "api" / "handlers.py")
    r = engine.refresh()
    assert r.added == ["shop/loyalty.py"]
    assert r.deleted == ["legacy/importer.py"]
    assert r.renamed == [("shop/api/routes.py", "shop/api/handlers.py")]
    assert_same_as_fresh(engine, repo, "refresh after add, delete and rename")
    restarted = cached(repo, cfg)
    assert last(restarted)["files_extracted"] == 0
    assert_same_as_fresh(restarted, repo, "restart after add, delete and rename")


# -------------------------------------------------------------------------------------------- 8-9 empty states

def test_empty_repository(tmp_path):
    repo, cfg = make_repo(tmp_path, files={}), cache_config(tmp_path)
    (repo).mkdir(exist_ok=True)
    engine = cached(repo, cfg)
    assert last(engine)["state"] == "published" and engine.docs == []
    assert_same_as_fresh(cached(repo, cfg), repo, "empty repository, warm")


def test_refresh_to_an_empty_repository_clears_every_index(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    previously = sorted(d.path for d in engine.docs)
    for rel in FILES:
        os.remove(repo.joinpath(*rel.split("/")))
    r = engine.refresh()
    assert engine.docs == [] and r.files_persisted == 0 and sorted(r.deleted) == previously
    assert_same_as_fresh(engine, repo, "refresh to an empty repository")


def test_in_memory_updates_and_removals_never_touch_the_cache(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    engine = cached(repo, cfg)
    path = db_path(cfg)
    before = (published_generation(cfg), path.read_bytes())
    engine.remove_documents(list(engine.path_to_doc))
    engine.update_documents([engine_doc for engine_doc in fresh(repo).docs[:2]])
    assert engine.index_cache_diagnostics["in_memory_changes_not_persisted"] is True
    assert (published_generation(cfg), path.read_bytes()) == before
    engine.refresh()
    assert engine.index_cache_diagnostics["in_memory_changes_not_persisted"] is False
    assert_same_as_fresh(engine, repo, "refresh after in-memory changes")


# ------------------------------------------------------------------------------------------ 10-15 fingerprints

def test_changed_gitignore(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    write(repo, ".gitignore", "legacy/\n*.md\n")
    engine = cached(repo, cfg)
    assert "legacy/utils.py" not in engine.path_to_doc and "README.md" not in engine.path_to_doc
    assert "legacy/utils.py" in last(engine)["deleted"]
    assert last(engine)["files_extracted"] == 0
    assert_same_as_fresh(engine, repo, "changed .gitignore")


def test_changed_max_files(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    engine = cached(repo, cfg, max_files=7)
    assert len(engine.docs) == 7 and engine.indexing_diagnostics.max_files_reached
    assert_same_as_fresh(engine, repo, "max_files=7", max_files=7)
    engine = cached(repo, cfg)
    assert last(engine)["files_reused"] == 7 and last(engine)["files_extracted"] == len(engine.docs) - 7
    assert_same_as_fresh(engine, repo, "max_files back to the default")


@pytest.mark.parametrize("change", ["decoding", "tokenizer_source", "extractor_version", "codec_source"])
def test_changed_fingerprint_inputs_invalidate_exactly_the_affected_artifacts(tmp_path, monkeypatch, change):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    first = cached(repo, cfg)
    n = len(first.docs)
    real_digest = fingerprints.module_source_digest
    if change == "decoding":
        monkeypatch.setattr(fingerprints, "DECODING", "utf-8/errors=strict")
        expected_kinds = {"doc_meta"}
    elif change == "tokenizer_source":
        monkeypatch.setattr(fingerprints, "module_source_digest",
                            lambda name: "changed" if name == "reponeedle.core.tokenizer" else real_digest(name))
        expected_kinds = {"doc_meta", "lexical", "semantic", "abstainer"}
    elif change == "extractor_version":
        monkeypatch.setitem(fingerprints.ARTIFACT_VERSIONS, "semantic", 99)
        expected_kinds = {"semantic"}
    else:
        monkeypatch.setattr(fingerprints, "module_source_digest",
                            lambda name: "changed" if name.endswith(".codecs") else real_digest(name))
        expected_kinds = set(schema.KINDS)        # every kind's fingerprint covers the codecs module
    engine = cached(repo, cfg)
    r = last(engine)
    # Re-extracted kinds are re-written; doc_meta values are unchanged, so dependent kinds stay reusable.
    assert r["artifacts_written"] == n * len(expected_kinds), (change, r)
    assert r["artifacts_reused"] == n * (len(schema.KINDS) - len(expected_kinds)), (change, r)
    assert_same_as_fresh(engine, repo, f"fingerprint change: {change}")


def test_changed_metadata_without_a_content_change(tmp_path):
    """enable_polyglot_symbols changes the symbols extracted from the SAME files."""
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    ablation = AblationConfig(enable_polyglot_symbols=True)
    engine = cached(repo, cfg, ablation_config=ablation)
    assert last(engine)["files_reused"] == 0
    assert_same_as_fresh(engine, repo, "polyglot symbols enabled", ablation_config=ablation)
    again = cached(repo, cfg, ablation_config=ablation)
    assert last(again)["files_reused"] == len(again.docs)
    assert_same_as_fresh(again, repo, "polyglot symbols, warm", ablation_config=ablation)


# --------------------------------------------------------------------------------------------- 16 persist_exclude

def test_changed_persist_exclude(tmp_path):
    repo = make_repo(tmp_path)
    cached(repo, cache_config(tmp_path))
    cfg = cache_config(tmp_path, persist_exclude=["shop/pricing.py", "web/**"])
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["files_persist_excluded"] == 4 and r["files_persisted"] == r["files_indexed"] - 4
    conn = sqlite3.connect(str(db_path(cfg)))
    paths = {row[0] for row in conn.execute("SELECT path FROM manifest UNION SELECT path FROM artifacts")}
    conn.close()
    assert not any(p == "shop/pricing.py" or p.startswith("web/") for p in paths)
    assert_same_as_fresh(engine, repo, "persist_exclude added")
    assert_same_as_fresh(cached(repo, cfg), repo, "persist_exclude, warm")


# ------------------------------------------------------------------------------------------ 17-20 failure modes

def test_existing_corrupt_cache_is_set_aside_and_rebuilt(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    path = db_path(cfg)
    path.write_bytes(b"not a database" * 100)
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["state"] == "published" and r["rebuilt_from_scratch"] and "set aside" in r["reason"]
    assert any(p.name.startswith(path.name + ".corrupt-") for p in path.parent.iterdir())
    assert_same_as_fresh(engine, repo, "rebuilt after corruption")


def test_existing_unsupported_schema(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    conn = sqlite3.connect(str(db_path(cfg)))
    conn.execute("PRAGMA user_version = 99")
    conn.close()
    with pytest.raises(IndexCacheError, match="unsupported schema version 99"):
        cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    engine = cached(repo, cfg)
    assert "unsupported schema version 99" in last(engine)["reason"]
    assert_same_as_fresh(engine, repo, "rebuilt after an unsupported schema")


def test_read_only_cache(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    before = db_path(cfg).read_bytes()
    write(repo, "shop/cart.py", FILES["shop/cart.py"] + "\n# edit\n")
    engine = cached(repo, cache_config(tmp_path, read_only=True))
    r = last(engine)
    assert r["state"] == "loaded_read_only" and r["files_extracted"] == 1
    assert db_path(cfg).read_bytes() == before
    assert_same_as_fresh(engine, repo, "read-only cache")


def test_read_only_without_a_cache_builds_in_memory(tmp_path):
    repo = make_repo(tmp_path)
    engine = cached(repo, cache_config(tmp_path, read_only=True))
    assert last(engine)["state"] in ("not_persisted", "disabled")
    assert not db_files(cache_config(tmp_path))
    assert_same_as_fresh(engine, repo, "read-only without a cache")


def test_cache_size_limit_reached(tmp_path):
    repo = make_repo(tmp_path)
    cfg = cache_config(tmp_path, max_db_bytes=4096, max_total_bytes=4096)
    engine = cached(repo, cfg)
    r = last(engine)
    assert r["state"] == "not_persisted" and "max_db_bytes" in r["reason"]
    conn = sqlite3.connect(str(db_path(cfg)))
    assert conn.execute("SELECT count(*) FROM manifest").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM artifacts").fetchone()[0] == 0
    conn.close()
    assert_same_as_fresh(engine, repo, "size limit reached")


# ----------------------------------------------------------------------------------------- policies and defaults

def test_rebuild_policy_always_ignores_a_valid_cache(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    cached(repo, cfg)
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="always"))
    r = last(engine)
    assert r["rebuilt_from_scratch"] and r["files_reused"] == 0 and r["generation"] == 2
    assert_same_as_fresh(engine, repo, "rebuild_policy=always")


def test_rebuild_policy_never_requires_a_valid_cache(tmp_path):
    repo = make_repo(tmp_path)
    with pytest.raises(IndexCacheError, match="missing"):
        cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    cached(repo, cache_config(tmp_path))
    engine = cached(repo, cache_config(tmp_path, rebuild_policy="never"))
    assert last(engine)["files_reused"] == len(engine.docs)


def test_no_cache_configuration_opens_nothing(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)

    def forbidden(*a, **k):
        raise AssertionError("no database may be opened without index_cache")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    engine = RepoNeedleEngine.from_directory(str(repo))
    assert engine.index_cache_diagnostics is None
    with pytest.raises(RuntimeError, match="index_cache"):
        engine.refresh()
    disabled = RepoNeedleEngine.from_directory(str(repo), index_cache=IndexCacheConfig(enabled=False,
                                                                                        cache_dir=str(tmp_path / "c")))
    assert disabled.index_cache_diagnostics is None and not (tmp_path / "c").exists()


@pytest.mark.parametrize("option", ["tree_sitter", "scip"])
def test_optional_components_take_the_uncached_route(tmp_path, option):
    from reponeedle.models import ScipConfig

    repo, cfg = make_repo(tmp_path), cache_config(tmp_path)
    kw = {"ablation_config": AblationConfig(structural_parser="tree_sitter")} if option == "tree_sitter" else \
        {"scip_config": ScipConfig(index_path=str(tmp_path / "missing.scip"), on_error="skip")}
    engine = cached(repo, cfg, **kw)
    r = last(engine)
    assert r["state"] == "disabled" and "not persisted (Stage 4)" in r["reason"]
    assert not db_files(cfg), "nothing may be written for configurations Stage 1 does not persist"
    assert_same_as_fresh(engine, repo, f"uncached route for {option}", **kw)


def test_settings_that_cannot_be_applied_disable_persistence(tmp_path, monkeypatch):
    from reponeedle.core.index_cache import connection

    repo = make_repo(tmp_path)
    monkeypatch.setattr(connection, "MIN_SQLITE_VERSION", (999, 0, 0))
    engine = cached(repo, cache_config(tmp_path))
    r = last(engine)
    assert r["state"] in ("disabled", "not_persisted") and "older than the minimum" in r["reason"]
    assert_same_as_fresh(engine, repo, "persistence unavailable")
    with pytest.raises(IndexCacheError):
        cached(repo, cache_config(tmp_path, rebuild_policy="never"))


def test_stat_validation_is_reported_as_content(tmp_path):
    repo, cfg = make_repo(tmp_path), cache_config(tmp_path, validation="stat")
    engine = cached(repo, cfg)
    assert last(engine)["validation"] == "content" and "runs as 'content'" in last(engine)["reason"]
    with pytest.raises(ValueError):
        engine.refresh(validation="mtime")


def test_database_is_outside_the_repository_by_default(tmp_path, monkeypatch):
    from reponeedle.core.index_cache import paths

    monkeypatch.setattr(paths, "default_cache_dir", lambda: tmp_path / "user-cache" / "reponeedle" / "index")
    repo = make_repo(tmp_path)
    engine = RepoNeedleEngine.from_directory(str(repo), index_cache=IndexCacheConfig())
    db = Path(engine.index_cache_diagnostics["database"])
    assert db.exists() and repo not in db.parents
    assert db.name.endswith("-s1.sqlite3") and len(db.name.split("-")[0]) == 32
