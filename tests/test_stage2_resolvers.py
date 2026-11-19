"""
V2 Stage 2: the optimised graph resolvers and the dependency model they expose.

1. Differential: ``FunctionGraphEngine.build_graph`` (indexed lookups, per-file resolution and replay) and
   ``RepoGraph.fit`` (per-file import resolution, cached class-to-test facts, indexed method and edge lookups) are
   compared EXACTLY with verbatim copies of the pre-Stage-2 implementations (tests/reference_v120_*.py) on the
   equivalence fixture, the synthetic Stage 2 repository and seeded random document sets, for every configuration
   that changes resolution. Tracked and untracked builds must also be identical.
2. Soundness of the dependency context (the property every reuse decision relies on): for any two repository
   states, a file whose own inputs are unchanged and whose consumed keys have the same values must resolve to
   exactly the same edges. Checked for every file over seeded random mutation sequences.
3. Provider events describe the lookup structures: the value of every consumed key is a function of its ordered
   provider list.
"""

import random

import pytest

from equivalence_fixture import FILES
from index_equivalence import capture_function_graph, capture_repo_graph, diff
from reference_v120_function_graph import FunctionGraphEngine as ReferenceFunctionGraph
from reference_v120_graph import RepoGraph as ReferenceRepoGraph
from reponeedle.core.function_graph import FunctionGraphEngine
from reponeedle.core.graph import RepoGraph
from reponeedle.core.index_cache.dependencies import ContextDigests, provider_lists
from reponeedle.engine import RepoNeedleEngine, _build_file_doc
from stage2_support import synthetic_files


def _docs(files, order_seed=None):
    items = list(files.items())
    if order_seed is not None:
        random.Random(order_seed).shuffle(items)
    out = []
    for rel, text in items:
        ext = "." + rel.rsplit(".", 1)[-1] if "." in rel.rsplit("/", 1)[-1] else ""
        out.append(_build_file_doc(rel, ext, text, None))
    return out


def _random_files(seed: int):
    """Random small Python/TS/Go documents with heavily shared names (many uniqueness and winner cases)."""
    rng = random.Random(seed)
    names = ["alpha", "beta", "gamma", "delta", "normalize", "render_view", "load"]
    classes = ["Cart", "Ledger", "Store"]
    methods = ["checkout", "rebalance_ledger", "persist_all", "refresh_state"]
    files = {}
    for i in range(rng.randint(6, 14)):
        pkg = rng.choice(["a", "b", "a/c", "src/a", "lib"])
        lines = []
        for _ in range(rng.randint(0, 3)):
            lines.append(f"from {rng.choice(['a', 'b', 'a.c', 'lib'])}.m{rng.randint(0, 9)} import {rng.choice(names)}")
        if rng.random() < 0.5:
            lines.append(f"import {rng.choice(['a', 'b'])}.m{rng.randint(0, 9)}")
        for _ in range(rng.randint(1, 4)):
            lines += [f"def {rng.choice(names)}(x):", f"    return {rng.choice(names)}(x)", ""]
        if rng.random() < 0.6:
            cls = rng.choice(classes)
            lines += [f"class {cls}:"]
            for m in rng.sample(methods, rng.randint(1, 3)):
                lines += [f"    def {m}(self):", f"        return self.{rng.choice(methods)}()", ""]
        lines += ["def run(o):", f"    o.{rng.choice(methods)}()", f"    m{rng.randint(0, 9)}.{rng.choice(names)}(o)",
                  f"    {rng.choice(classes)}.{rng.choice(methods)}(o)", f"    return {rng.choice(names)}(o)", ""]
        name = f"{pkg}/m{rng.randint(0, 9)}.py" if rng.random() < 0.9 else f"tests/test_m{rng.randint(0, 9)}.py"
        files[name] = "\n".join(lines) + "\n"
    files["web/x.ts"] = f"import {{ f }} from './y';\nfunction {rng.choice(names)}() {{ return f(); }}\n"
    files["web/y.ts"] = "export function f() { return 1; }\n"
    files["go/a.go"] = "package a\n\nfunc Run() {\n\tfmt.Println(\"x\")\n}\n"
    files["go/b.go"] = "package a\n\nfunc Other() {\n\tRun()\n}\n"
    return files


CORPORA = [("equivalence_fixture", FILES, None), ("synthetic", synthetic_files(), None),
           ("synthetic_shuffled", synthetic_files(), 3)] + [
    (f"random_{s}", _random_files(s), s) for s in range(12)]


@pytest.mark.parametrize("name,files,order", CORPORA, ids=[c[0] for c in CORPORA])
@pytest.mark.parametrize("structural,min_conf", [(True, 0.6), (False, 0.6), (True, 0.8), (True, 0.0)])
def test_function_graph_matches_the_1_2_0_resolver(name, files, order, structural, min_conf):
    docs = _docs(files, order)
    ref = ReferenceFunctionGraph(enable_structural_edges=structural, min_confidence=min_conf).build_graph(docs)
    for track in (False, True):
        new = FunctionGraphEngine(enable_structural_edges=structural, min_confidence=min_conf).build_graph(
            docs, track=track)
        out = []
        diff(capture_function_graph(ref), capture_function_graph(new), "function_graph", out)
        assert out == [], (name, track, out)


@pytest.mark.parametrize("name,files,order", CORPORA, ids=[c[0] for c in CORPORA])
@pytest.mark.parametrize("class_to_test", [False, True])
def test_repo_graph_matches_the_1_2_0_implementation(name, files, order, class_to_test):
    docs = _docs(files, order)
    ref = ReferenceRepoGraph()
    ref.enable_class_to_test = class_to_test
    ref.fit(docs)
    for track in (False, True):
        new = RepoGraph()
        new.enable_class_to_test = class_to_test
        new.fit(docs, track=track)
        new.fit(docs, track=track)              # a refit on the same instance (cached facts) is identical too
        out = []
        diff(capture_repo_graph(ref), capture_repo_graph(new), "repo_graph", out)
        assert out == [], (name, track, out)


def test_rebuilds_on_one_instance_after_changes_match_the_reference():
    """Per-document caches (extraction, class-to-test facts) never leak a previous build's state."""
    fg, rg = FunctionGraphEngine(), RepoGraph()
    for seed in range(6):
        docs = _docs(_random_files(seed), seed)
        fg.build_graph(docs, track=bool(seed % 2))
        rg.fit(docs, track=bool(seed % 2))
        out = []
        diff(capture_function_graph(ReferenceFunctionGraph().build_graph(docs)), capture_function_graph(fg), "fg", out)
        ref = ReferenceRepoGraph()
        ref.fit(docs)
        diff(capture_repo_graph(ref), capture_repo_graph(rg), "rg", out)
        assert out == [], (seed, out)


def test_default_engine_build_is_unchanged_on_the_fixture():
    engine = RepoNeedleEngine(docs=_docs(FILES))
    ref_fg = ReferenceFunctionGraph().build_graph(engine.docs)
    out = []
    diff(capture_function_graph(ref_fg), capture_function_graph(engine.function_graph), "fg", out)
    assert out == []


# --------------------------------------------------------------------------------------- dependency soundness

def _mutate(files, rng):
    files = dict(files)
    paths = sorted(files)
    op = rng.choice(["edit", "add", "delete", "rename", "dup"])
    if op == "edit" and paths:
        p = rng.choice(paths)
        files[p] = files[p] + f"\n\ndef {rng.choice(['alpha', 'zeta', 'normalize', 'checkout'])}(x):\n    return x\n"
    elif op == "add":
        files[f"new{rng.randint(0, 99)}/m{rng.randint(0, 9)}.py"] = "def beta(x):\n    return gamma(x)\n"
    elif op == "delete" and len(paths) > 2:
        del files[rng.choice(paths)]
    elif op == "rename" and paths:
        p = rng.choice(paths)
        files[f"moved/{p}"] = files.pop(p)
    elif paths:
        p = rng.choice(paths)
        files[p.replace(".py", "_dup.py") if p.endswith(".py") else p + ".py"] = files[p]
    return files


def _graph_state(docs):
    fg = FunctionGraphEngine().build_graph(docs, track=True)
    rg = RepoGraph()
    rg.fit(docs, track=True)
    return fg, rg


@pytest.mark.parametrize("seed", range(8))
def test_equal_own_inputs_and_context_imply_equal_edges(seed):
    """
    The invariant behind every reuse: if a file's own inputs and the current values of every key its previous
    resolution consumed are unchanged, its resolution is unchanged. Checked for every file of every step.
    """
    rng = random.Random(seed)
    files = _random_files(seed)
    prev_docs = _docs(files, seed)
    prev = _graph_state(prev_docs)
    checked = 0
    for step in range(8):
        files = _mutate(files, rng)
        docs = _docs(files, seed * 100 + step)
        cur = _graph_state(docs)
        prev_by_path = {d.path: d for d in prev_docs}
        for graph_prev, graph_cur in zip(prev, cur):
            digests_prev, digests_cur = ContextDigests(graph_prev.key_value), ContextDigests(graph_cur.key_value)
            for doc in docs:
                old = prev_by_path.get(doc.path)
                if old is None or (old.content, old.imports, old.symbols) != (doc.content, doc.imports, doc.symbols):
                    continue
                r_prev = graph_prev.file_resolutions[doc.path]
                r_cur = graph_cur.file_resolutions[doc.path]
                if digests_prev.context(r_prev.consumed) == digests_cur.context(r_prev.consumed):
                    assert r_prev.edges == r_cur.edges, (seed, step, doc.path)
                    assert r_prev.consumed == r_cur.consumed, (seed, step, doc.path)
                    checked += 1
        prev_docs, prev = docs, cur
    assert checked > 20


@pytest.mark.parametrize("seed", range(6))
def test_key_values_are_functions_of_their_ordered_provider_lists(seed):
    """
    Two documents sets with equal ordered provider lists for a key give the key the same value; so comparing
    provider lists (the dependency index) never misses a value change of a consumed key.
    """
    rng = random.Random(seed)
    states = []
    files = _random_files(seed)
    for step in range(6):
        docs = _docs(files, seed + step)
        fg, rg = _graph_state(docs)
        lists = {"fg": provider_lists(fg.provides(d) for d in docs), "rg": provider_lists(rg.provides(d) for d in docs)}
        states.append((fg, rg, lists))
        files = _mutate(files, rng)
    compared = 0
    for a in states:
        for b in states:
            for g, ga, gb in (("fg", a[0], b[0]), ("rg", a[1], b[1])):
                consumed = {k for res in ga.file_resolutions.values() for k in res.consumed}
                for k in consumed:
                    if a[2][g].get(k) == b[2][g].get(k):
                        assert ga.key_value(k) == gb.key_value(k), (g, k)
                        compared += 1
    assert compared > 100


def test_consumed_keys_are_typed_and_values_serialisable():
    import json

    from reponeedle.models import AblationConfig

    # Polyglot symbols give TS/Go/Rust files their imports, so every RepoGraph branch (paths, crates, symbols) runs.
    ablation = AblationConfig(enable_polyglot_symbols=True)
    docs = [_build_file_doc(rel, "." + rel.rsplit(".", 1)[-1], text, ablation) for rel, text in synthetic_files().items()]
    fg, rg = _graph_state(docs)
    prefixes = {"fg": ("fg.module:", "fg.def:", "fg.cmeth:", "fg.func:", "fg.meth:"),
                "rg": ("rg.module:", "rg.path:", "rg.symbol:", "rg.package:", "rg.crate:", "rg.cdeps:", "rg.entry:")}
    seen = set()
    for g, graph in (("fg", fg), ("rg", rg)):
        for res in graph.file_resolutions.values():
            assert list(res.consumed) == sorted(set(res.consumed))
            for k in res.consumed:
                assert k.startswith(prefixes[g]), k
                json.dumps(graph.key_value(k))
                seen.add(k.split(":", 1)[0] + ":")
    # The synthetic repository exercises every lookup family of both resolvers.
    assert {"fg.module:", "fg.def:", "fg.cmeth:", "fg.func:", "fg.meth:"} <= seen
    assert {"rg.module:", "rg.path:", "rg.symbol:", "rg.package:", "rg.crate:", "rg.cdeps:", "rg.entry:"} <= seen
    edge_types = {e.edge_type for e in fg.edges}
    assert {"verified_call", "unique_global_call", "directory_local_call", "structural_method_call"} <= edge_types


def test_untracked_builds_record_no_resolutions():
    docs = _docs(FILES)
    fg = FunctionGraphEngine().build_graph(docs)
    rg = RepoGraph()
    rg.fit(docs)
    assert fg.file_resolutions == {} and rg.file_resolutions == {}
    assert fg.resolution_stats["files_resolved"] == len(docs)
