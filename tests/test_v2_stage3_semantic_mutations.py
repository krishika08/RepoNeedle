"""
V2 Stage 3: after every mutation, a cached engine (in-process ``refresh()`` and a warm restart) is exactly equivalent
to a fresh UNCACHED build (full differential harness on a query sample) AND its semantic index equals the Stage 2
reference fitted on the same documents (every structure, score arrays).

Each mutation runs with the default semantic configuration and with ``max_features=60``, where document-frequency
changes move features across the vocabulary cutoff (the tests assert that they really do).
"""

import random

import pytest

from cache_support import cache_config, cached, fresh, last, write
from index_equivalence import assert_equivalent
from stage2_support import (QUERIES, append, m_body_only, m_rename_file, m_rename_function, read, remove,
                            replace_in, reversed_discovery, synthetic_files, write_tree)
from stage3_support import assert_semantic_equal, engine_semantic

CONFIGS = {"default": {}, "max_features=60": {"max_features": 60}}
SEM_QUERIES = [q["text"] for q in QUERIES]


def check(engine, repo, label, config, **kw):
    with engine_semantic(config):
        reference_build = fresh(repo, **kw)
    assert_equivalent(engine, reference_build, label=label, queries=QUERIES, packing_queries=None)
    with engine_semantic(config, reference=True):
        stage2 = fresh(repo, **kw)
    assert_semantic_equal(engine.semantic_index, stage2.semantic_index, label, queries=SEM_QUERIES)


# ------------------------------------------------------------------------------------------- mutation catalogue

def m_feature_edit(repo):
    append(repo, "app/mod2.py", "\n\ndef quarterly_ledger_reconciliation(entries):\n    return entries\n")


def m_add(repo):
    write(repo, "app/added_feature.py", "def added_semantic_feature(value):\n    return helper_2(value)\n")


def m_delete(repo):
    remove(repo, "util/mod5.py")


def m_multiple(repo):
    write(repo, "zz/one.py", "def zz_one():\n    return 1\n")
    write(repo, "aa/two.py", "def aa_two():\n    return 2\n")
    remove(repo, "legacy/mod3.py")
    append(repo, "core/mod0.py", "\n# reconcile ledger entries\n")
    m_rename_function(repo)


def m_df_increase(repo):
    common = " ".join(["helper", "normalize", "value", "widget", "checkout"] * 4)
    for i in range(4):
        write(repo, f"dfup/m{i}.py", f'"""{common}"""\n')


def m_df_decrease(repo):
    for rel in ("core/mod0.py", "app/mod2.py", "util/mod1.py"):
        text = read(repo, rel)
        write(repo, rel, text.replace("normalize", "nrm").replace("helper", "hlp"))


def m_vocabulary_churn(repo):
    """Many repeated new features in several files: high document frequencies push old features out."""
    words = " ".join(f"churnword{i}" for i in range(12))
    for i in range(6):
        write(repo, f"churn/c{i}.py", f'"""{words}"""\n')


def m_ties(repo):
    for i in range(5):
        write(repo, f"ties/t{i}.txt", "abc abd abe abf abg " * (i + 1))


def m_first_seen_provider_deleted(repo, first_path):
    remove(repo, first_path)


def m_symbol_edit(repo):
    replace_in(repo, "core/mod0.py", "class Widget0:", "class RenamedWidgetZero:")


MUTATIONS = [("body_only", m_body_only), ("feature_edit", m_feature_edit), ("symbol_edit", m_symbol_edit),
             ("add", m_add), ("delete", m_delete), ("rename", m_rename_file), ("multiple", m_multiple),
             ("df_increase", m_df_increase), ("df_decrease", m_df_decrease),
             ("vocabulary_churn", m_vocabulary_churn), ("ties", m_ties)]


@pytest.mark.parametrize("config", list(CONFIGS), ids=list(CONFIGS))
@pytest.mark.parametrize("name", [n for n, _ in MUTATIONS])
def test_mutation_refresh_and_warm_restart(tmp_path, name, config):
    repo = write_tree(tmp_path / "repo", synthetic_files())
    cfg = cache_config(tmp_path)
    with engine_semantic(CONFIGS[config]):
        engine = cached(repo, cfg)
        dict(MUTATIONS)[name](repo)
        report = engine.refresh()
    assert report.global_structures["semantic"] == "recomputed_in_full"
    check(engine, repo, f"{name} / {config}: in-process refresh", CONFIGS[config])
    with engine_semantic(CONFIGS[config]):
        warm = cached(repo, cfg)
    assert last(warm)["work_counters"]["semantic"]["feature_cache_misses"] == 0
    check(warm, repo, f"{name} / {config}: warm restart", CONFIGS[config])


def test_cutoff_transitions_really_change_the_vocabulary(tmp_path):
    repo = write_tree(tmp_path / "repo", synthetic_files())
    cfg = cache_config(tmp_path)
    with engine_semantic({"max_features": 60}):
        engine = cached(repo, cfg)
        before = list(engine.semantic_index.vocabulary)
        m_vocabulary_churn(repo)
        stats = engine.refresh().work_counters["semantic"]
    assert stats["vocabulary_added"] > 0 and stats["vocabulary_added"] == stats["vocabulary_removed"]
    assert list(engine.semantic_index.vocabulary) != before and len(before) == 60
    check(engine, repo, "cutoff transition", {"max_features": 60})


@pytest.mark.parametrize("config", list(CONFIGS), ids=list(CONFIGS))
def test_deleting_the_first_seen_provider(tmp_path, config):
    """The first document in discovery order is where most features are first seen."""
    repo = write_tree(tmp_path / "repo", synthetic_files())
    cfg = cache_config(tmp_path)
    with engine_semantic(CONFIGS[config]):
        engine = cached(repo, cfg)
        first = engine.docs[0].path
        first_features = set(engine.semantic_index._doc_feature_cache[first][1])
        m_first_seen_provider_deleted(repo, first)
        engine.refresh()
    assert first_features and first not in {d.path for d in engine.docs}
    check(engine, repo, f"first-seen provider {first} deleted / {config}", CONFIGS[config])


@pytest.mark.parametrize("config", list(CONFIGS), ids=list(CONFIGS))
def test_discovery_order_reversal_and_restoration(tmp_path, config):
    repo = write_tree(tmp_path / "repo", synthetic_files())
    cfg = cache_config(tmp_path)
    with engine_semantic(CONFIGS[config]):
        engine = cached(repo, cfg)
        with reversed_discovery():
            engine.refresh()
            with engine_semantic(CONFIGS[config]):
                reversed_ref = fresh(repo)
            assert [d.path for d in engine.docs] == [d.path for d in reversed_ref.docs]
            check(engine, repo, f"reversed discovery / {config}", CONFIGS[config])
        engine.refresh()
    check(engine, repo, f"restored discovery / {config}", CONFIGS[config])


def test_empty_repository_and_back(tmp_path):
    files = synthetic_files()
    repo = write_tree(tmp_path / "repo", files)
    cfg = cache_config(tmp_path)
    engine = cached(repo, cfg)
    for rel in files:
        remove(repo, rel)
    engine.refresh()
    assert engine.docs == [] and engine.semantic_index.num_docs == 0
    check(engine, repo, "empty repository", {})
    write_tree(repo, files)
    engine.refresh()
    check(engine, repo, "repopulated", {})


@pytest.mark.parametrize("change", [({}, {"max_features": 40}), ({"max_features": 40}, {}),
                                    ({}, {"min_n": 2, "max_n": 4}), ({"min_n": 2, "max_n": 4}, {})])
def test_semantic_configuration_changes_between_builds(tmp_path, change):
    before, after = change
    repo = write_tree(tmp_path / "repo", synthetic_files())
    cfg = cache_config(tmp_path)
    with engine_semantic(before):
        first = cached(repo, cfg)
    with engine_semantic(after):
        engine = cached(repo, cfg)
    sem = last(engine)["work_counters"]["semantic"]
    n = len(first.docs)
    if ("min_n" in before) != ("min_n" in after):       # extraction configuration: artifacts are re-extracted
        assert sem["feature_cache_misses"] == n
    else:                                               # max_features is global: every artifact is reused
        assert sem["feature_cache_hits"] == n
    check(engine, repo, f"configuration {before} -> {after}", after)


def test_persist_exclude_transitions(tmp_path):
    repo = write_tree(tmp_path / "repo", synthetic_files())
    plain = cache_config(tmp_path)
    excluding = cache_config(tmp_path, persist_exclude=["core/**"])
    cached(repo, plain)
    engine = cached(repo, excluding)
    r = last(engine)
    assert r["files_persist_excluded"] > 0
    assert r["work_counters"]["semantic"]["feature_cache_misses"] == r["files_persist_excluded"]
    check(engine, repo, "persist_exclude added", {})
    append(repo, "core/mod0.py", "\n# excluded file edited\n")
    engine.refresh()
    check(engine, repo, "excluded file edited", {})
    engine = cached(repo, plain)
    check(engine, repo, "persist_exclude removed", {})


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_seeded_random_mutation_sequences(tmp_path, seed):
    rng = random.Random(seed)
    repo = write_tree(tmp_path / "repo", synthetic_files(seed))
    cfg = cache_config(tmp_path)
    config = {"max_features": rng.choice([30, 80, 15000])}
    with engine_semantic(config):
        engine = cached(repo, cfg)
    serial = 0
    for step in range(6):
        paths = sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*") if p.is_file())
        op = rng.choice(["edit", "add", "delete", "rename", "words"])
        serial += 1
        if op == "edit" and paths:
            append(repo, rng.choice(paths), f"\n# edit {serial} {rng.choice(['ledger', 'widget', 'reconcile'])}\n")
        elif op == "add":
            write(repo, f"r{rng.randint(0, 3)}/n{serial}.py", f"def gen_{serial}_{rng.randint(0, 99)}(x):\n    return x\n")
        elif op == "delete" and len(paths) > 3:
            remove(repo, rng.choice(paths))
        elif op == "rename" and paths:
            src = rng.choice(paths)
            target = repo.joinpath(*f"moved/{serial}_{src.replace('/', '_')}".split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            repo.joinpath(*src.split("/")).rename(target)
        else:
            write(repo, f"w/{serial}.md", " ".join(rng.choice(["alpha", "beta", "gamma", "delta"]) for _ in range(30)))
        with engine_semantic(config):
            if rng.random() < 0.5:
                engine.refresh()
            else:
                engine = cached(repo, cfg)
        check(engine, repo, f"seed {seed} step {step} ({op})", config)
