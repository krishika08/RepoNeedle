"""
V2 Stage 2: mutation and equivalence tests for incremental index maintenance (Stage 2 brief, section 18).

For every mutation, two cached engines exist BEFORE it:
- engine A is refreshed in the same process (``refresh()``: the in-process BM25 update, dependency-scoped graph
  re-resolution against the previous generation);
- engine B is a warm restart from its own cache (a new engine object: dependency-scoped re-resolution from the
  persisted provider index, resolutions and reference counts).
Both are compared EXACTLY (complete index state, retrieval for a query sample, no tolerances) with a completely
fresh UNCACHED build of the same repository state, and an unchanged restart afterwards must reuse every resolution.
Work counters are asserted where the scenario determines them (proportional work, uniqueness transitions).
"""

import random

import pytest

from cache_support import cache_config, cached, capture_in_child, last, write
from index_equivalence import compare_captures
from reponeedle.models import AblationConfig
from stage2_support import (MUTATIONS, append, check, counters, no_index_misses, remove, replace_in,
                            reversed_discovery, state_matches, synthetic_files, write_tree)


@pytest.fixture
def repo(tmp_path):
    return write_tree(tmp_path / "repo", synthetic_files())


def _two_engines(tmp_path, repo, **kw):
    cfg_a, cfg_b = cache_config(tmp_path / "a"), cache_config(tmp_path / "b")
    return cached(repo, cfg_a, **kw), cfg_a, cfg_b, cached(repo, cfg_b, **kw)


def _resolved(engine):
    c = counters(engine)
    return c["function_graph"]["files_resolved"], c["repo_graph"]["files_resolved"]


def _edges(engine, source=None, target=None):
    return [(e.source_path, e.target_path, e.target_func, e.edge_type) for e in engine.function_graph.edges
            if (source is None or e.source_path == source) and (target is None or e.target_path == target)]


@pytest.mark.parametrize("name,mutate", MUTATIONS, ids=[n for n, _ in MUTATIONS])
def test_every_mutation_matches_a_fresh_build(tmp_path, repo, name, mutate):
    engine_a, cfg_a, cfg_b, _ = _two_engines(tmp_path, repo)
    mutate(repo)
    report = engine_a.refresh()
    assert report.state == "published", report.reason
    check(engine_a, repo, f"{name}: in-process refresh")
    no_index_misses(engine_a)
    engine_b = cached(repo, cfg_b)
    check(engine_b, repo, f"{name}: warm restart")
    no_index_misses(engine_b)
    unchanged = cached(repo, cfg_a)
    assert _resolved(unchanged) == (0, 0), counters(unchanged)
    assert state_matches(unchanged, repo)


def test_body_only_edit_re_resolves_only_that_file(tmp_path, repo):
    engine, cfg_a, cfg_b, _ = _two_engines(tmp_path, repo)
    replace_in(repo, "core/mod0.py", "return normalize(value) + 0", "return normalize(value) + 100")
    for e in (engine, cached(repo, cfg_b)):
        if e is engine:
            e.refresh()
        c = counters(e)
        for g in ("function_graph", "repo_graph"):
            assert c[g]["files_affected"] == 1 and c[g]["files_resolved"] == 1, (g, c[g])
            assert c[g]["provider_keys_changed"] == 0 and c[g]["files_reused"] == len(e.docs) - 1
        assert c["function_graph"]["calls_resolved"] < c["function_graph"]["calls_total"] / 5
        assert last(e)["global_structures"]["function_graph.call_resolution"] == "incremental"
        assert last(e)["global_structures"]["repo_graph.pagerank"] == "recomputed_in_full"
        check(e, repo, "body-only edit")


def test_a_second_definition_removes_unique_edges_and_deleting_it_restores_them(tmp_path, repo):
    """Uniqueness in both directions: one definition becoming two, and two becoming one again."""
    engine = cached(repo, cache_config(tmp_path))
    before = _edges(engine, source="legacy/mod3.py")
    assert ("legacy/mod3.py", "util/mod5.py", "helper_5", "unique_global_call") in before
    append(repo, "core/sub/mod3.py", "\n\ndef helper_5(value):\n    return value\n")
    r = engine.refresh()
    fg = r.work_counters["function_graph"]
    assert fg["provider_keys_changed"] >= 1 and fg["files_affected_by_dependencies"] >= 1
    assert ("legacy/mod3.py", "util/mod5.py", "helper_5", "unique_global_call") not in _edges(engine)
    check(engine, repo, "one definition became two")
    replace_in(repo, "core/sub/mod3.py", "def helper_5(value):", "def helper_5_gone(value):")
    engine.refresh()
    assert ("legacy/mod3.py", "util/mod5.py", "helper_5", "unique_global_call") in _edges(engine)
    check(engine, repo, "two definitions became one")
    no_index_misses(engine)


def test_two_definitions_becoming_one_creates_unique_edges(tmp_path, repo):
    engine = cached(repo, cache_config(tmp_path))
    assert any(t == "directory_local_call" and f == "normalize" for _s, _t, f, t in _edges(engine))
    replace_in(repo, "core/mod0.py", "def normalize(value):", "def normalize_unused(value):")
    r = engine.refresh()
    assert r.work_counters["function_graph"]["files_affected_by_dependencies"] >= 3
    assert {s for s, t, f, kind in _edges(engine) if f == "normalize" and kind == "unique_global_call"} >= {
        "core/mod4.py", "app/mod2.py"}
    check(engine, repo, "normalize: two definitions became one")


def test_a_class_gaining_and_losing_a_method(tmp_path, repo):
    engine = cached(repo, cache_config(tmp_path))
    assert ("util/mod5.py", "core/mod0.py", "method_0_unique", "unique_global_call") in _edges(engine)
    replace_in(repo, "util/mod1.py", "    def checkout(self):",
               "    def method_0_unique(self):\n        return 0\n\n    def checkout(self):")
    engine.refresh()
    assert ("util/mod5.py", "core/mod0.py", "method_0_unique", "unique_global_call") not in _edges(engine)
    check(engine, repo, "class gained a method")
    replace_in(repo, "util/mod1.py", "    def method_0_unique(self):", "    def method_0_moved(self):")
    engine.refresh()
    assert ("util/mod5.py", "core/mod0.py", "method_0_unique", "unique_global_call") in _edges(engine)
    check(engine, repo, "class lost the method again")


def test_importers_change_without_their_providers(tmp_path, repo):
    engine = cached(repo, cache_config(tmp_path))
    replace_in(repo, "app/mod2.py", "import util.mod4", "import core.mod0")
    r = engine.refresh()
    assert r.work_counters["repo_graph"]["files_own_changed"] == 1
    check(engine, repo, "importer changed")


def test_unaffected_provider_change_does_not_expand_the_affected_set(tmp_path, repo):
    """A new function nobody calls changes keys no file consumes: only the provider is re-resolved."""
    engine = cached(repo, cache_config(tmp_path))
    append(repo, "util/mod1.py", "\n\ndef never_called_anywhere_xyz(v):\n    return v\n")
    r = engine.refresh()
    for g in ("function_graph", "repo_graph"):
        assert r.work_counters[g]["files_affected_by_dependencies"] == 0, (g, r.work_counters[g])
    check(engine, repo, "provider change with no consumers")


def test_unchanged_restart_resolves_nothing_and_replays_every_edge(tmp_path, repo):
    cfg = cache_config(tmp_path)
    first = cached(repo, cfg)
    engine = cached(repo, cfg)
    c = counters(engine)
    assert c["function_graph"]["calls_resolved"] == 0 and c["function_graph"]["files_resolved"] == 0
    assert c["function_graph"]["edges_replayed"] == len(first.function_graph.edges) > 0
    assert c["function_graph"]["edges_reused"] == c["function_graph"]["edges_replayed"]
    assert c["repo_graph"]["files_resolved"] == 0
    assert c["abstainer"]["documents_added"] == c["abstainer"]["documents_removed"] == 0
    labels = last(engine)["global_structures"]
    assert labels["function_graph.call_resolution"] == labels["repo_graph.import_edges"] == "incremental"
    assert labels["abstainer"] == "incremental" and labels["semantic"] == "recomputed_in_full"
    assert labels["repo_graph.pagerank"] == "recomputed_in_full"
    assert labels["bm25"] == "recomputed_in_full" and "warm restart" in last(engine)["fallbacks"]["bm25"]
    check(engine, repo, "unchanged restart")


def test_repeated_refresh_without_changes(tmp_path, repo):
    engine = cached(repo, cache_config(tmp_path))
    for i in range(3):
        r = engine.refresh()
        assert r.work_counters["function_graph"]["files_resolved"] == 0
        assert r.global_structures["bm25"] == "partially_incremental"
        assert r.work_counters["bm25"]["documents_changed"] == 0
    check(engine, repo, "three refreshes without changes")


def test_in_process_refresh_uses_partial_bm25_for_edits(tmp_path, repo):
    engine = cached(repo, cache_config(tmp_path))
    replace_in(repo, "util/mod5.py", "def caller_5(w):", "def caller_5_edited(w, extra_term_qq):")
    r = engine.refresh()
    assert r.global_structures["bm25"] == "partially_incremental"
    assert r.work_counters["bm25"]["documents_changed"] == 1
    assert r.work_counters["bm25"]["postings_rebuilt_full"] is False
    check(engine, repo, "partial BM25 after an edit")


def test_max_files_changes(tmp_path, repo):
    engine, cfg_a, cfg_b, _ = _two_engines(tmp_path, repo)
    small = cached(repo, cfg_a, max_files=9)
    check(small, repo, "max_files=9", max_files=9)
    back = cached(repo, cfg_a)
    check(back, repo, "max_files back to default")
    no_index_misses(back)


def test_persist_exclude_toggle(tmp_path, repo):
    cfg = cache_config(tmp_path)
    cached(repo, cfg)
    excl = cache_config(tmp_path, persist_exclude=["util/**"])
    engine = cached(repo, excl)
    labels, fallbacks = last(engine)["global_structures"], last(engine)["fallbacks"]
    assert labels["function_graph.call_resolution"] == "fallback_full" and "persist_exclude" in \
        fallbacks["function_graph.call_resolution"]
    check(engine, repo, "persist_exclude on")
    again = cached(repo, cfg)
    assert last(again)["global_structures"]["function_graph.call_resolution"] == "fallback_full"
    check(again, repo, "persist_exclude off (no resolutions were persisted meanwhile)")
    third = cached(repo, cfg)
    assert _resolved(third) == (0, 0)
    check(third, repo, "persist_exclude off, warm")


def test_empty_repository_round_trip(tmp_path, repo):
    engine = cached(repo, cache_config(tmp_path))
    for rel in list(synthetic_files()):
        remove(repo, rel)
    engine.refresh()
    check(engine, repo, "emptied")
    write(repo, "core/one.py", "def only():\n    return 1\n")
    engine.refresh()
    check(engine, repo, "one file again")


def test_discovery_order_change_without_content_change(tmp_path, repo):
    cfg = cache_config(tmp_path)
    engine = cached(repo, cfg)
    with reversed_discovery():
        r = engine.refresh()
        assert r.global_structures["bm25"] == "recomputed_in_full"
        check(engine, repo, "reversed discovery order (refresh)")
        restarted = cached(repo, cfg)
        check(restarted, repo, "reversed discovery order (restart)")
        no_index_misses(restarted)
    back = cached(repo, cfg)
    check(back, repo, "original order again")
    no_index_misses(back)


def test_polyglot_symbols_mutations(tmp_path, repo):
    """With polyglot symbols every RepoGraph branch (Rust mod/use, Go packages, TS relative imports) has imports."""
    kw = {"ablation_config": AblationConfig(enable_polyglot_symbols=True)}
    engine, cfg_a, cfg_b, _ = _two_engines(tmp_path, repo, **kw)
    for name, mutate in MUTATIONS:
        if name in ("rust_crate", "go_package", "manifests", "rename_file", "add_files_positions"):
            mutate(repo)
            engine.refresh()
            check(engine, repo, f"polyglot {name}: refresh", **kw)
            no_index_misses(engine)
    check(cached(repo, cfg_b, **kw), repo, "polyglot: restart after all", **kw)


@pytest.mark.parametrize("seed", range(3))
def test_seeded_random_mutation_sequences(tmp_path, repo, seed):
    rng = random.Random(seed)
    cfg_a, cfg_b = cache_config(tmp_path / "a"), cache_config(tmp_path / "b")
    engine = cached(repo, cfg_a)
    cached(repo, cfg_b)
    applied = []
    ops = list(MUTATIONS)
    rng.shuffle(ops)
    for name, mutate in ops[:10]:
        try:
            mutate(repo)
        except (AssertionError, FileNotFoundError):
            continue                     # the text or file was changed by an earlier step
        applied.append(name)
        engine.refresh()
        assert state_matches(engine, repo), applied
        no_index_misses(engine)
        if len(applied) % 3 == 0:
            restarted = cached(repo, cfg_b)
            assert state_matches(restarted, repo), applied
            no_index_misses(restarted)
    check(engine, repo, f"random sequence {seed}: {applied}")


def test_full_query_corpus_after_mutations(tmp_path, repo):
    cfg = cache_config(tmp_path)
    cached(repo, cfg)
    for name in ("second_definition", "move_module", "rust_crate", "test_targets"):
        dict(MUTATIONS)[name](repo)
    check(cached(repo, cfg), repo, "restart after four mutations, full 225-query corpus", queries=None)


def test_cross_process_restart_after_provider_changes(tmp_path, repo):
    cfg = cache_config(tmp_path)
    cached(repo, cfg)
    for name in ("second_definition", "delete_one_of_two", "winning_provider"):
        dict(MUTATIONS)[name](repo)
    child = capture_in_child(repo, cfg, tmp_path / "warm.pickle", step=25)
    assert child["report"]["work_counters"]["function_graph"]["context_mismatches_outside_dependency_index"] == 0
    reference = capture_in_child(repo, None, tmp_path / "fresh.pickle", step=25)["capture"]
    compare_captures(child["capture"], reference, label="restart in a fresh process after provider changes")
