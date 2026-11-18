"""
V2 Stage 0: FunctionGraphEngine.build_graph() must not carry state from an earlier document collection.

Before the fix, module_to_path and package_to_files survived rebuilds, so call resolution on a smaller document set
could still map a module name to a removed file and create edges to it. Every comparison below is against a freshly
constructed FunctionGraphEngine built on the same ordered documents, using the exact, ordered comparison of the
index-equivalence harness.
"""

import pytest

from index_equivalence import capture_function_graph, diff
from reponeedle.core.function_graph import FunctionGraphEngine
from reponeedle.models import FileDoc

FILES = {
    "app/__init__.py": "",
    "app/zeta.py": "def helper(x):\n    return x + 1\n\n\ndef other():\n    return 2\n",
    "app/alpha.py": "from app.zeta import helper\n\n\ndef run():\n    return helper(1)\n",
    "app/omega.py": "import app.zeta\n\n\ndef go():\n    return app.zeta.helper(3)\n",
    "app/utils.py": "def normalize(v):\n    return v.strip()\n",
    "lib/utils.py": "def normalize(v):\n    return v.lower()\n\n\ndef shared():\n    return 1\n",
    "lib/pkg/mod.py": "from lib.utils import shared\n\n\ndef use():\n    return shared()\n",
    "app/pkg/mod.py": "def use():\n    return 0\n",
    "tests/test_zeta.py": "from app.zeta import helper\n\n\ndef test_helper():\n    assert helper(1) == 2\n",
    "tests/test_utils.py": "from app.utils import normalize\n\n\ndef test_norm():\n    assert normalize(' a ') == 'a'\n",
}


def make_docs(files=FILES):
    return [FileDoc(path=p, content=c, is_test=p.startswith("tests/")) for p, c in files.items()]


def without(docs, *paths):
    return [d for d in docs if d.path not in paths]


def assert_same_as_fresh(fg, docs, label, **engine_kw):
    fresh = FunctionGraphEngine(**engine_kw).build_graph(docs)
    found = []
    diff(capture_function_graph(fresh), capture_function_graph(fg), "function_graph", found)
    assert not found, f"{label}:\n" + "\n".join(found)


def assert_no_reference_to(fg, missing):
    present = set(fg.doc_paths)
    assert missing not in present
    assert all(p in present for p in fg.module_to_path.values()), fg.module_to_path
    assert all(p in present for paths in fg.package_to_files.values() for p in paths), fg.package_to_files
    assert all(e.source_path in present and e.target_path in present for e in fg.edges)
    assert all(src in present and dst in present for src, dst in fg.file_to_file_edges)
    assert set(fg.graph.nodes) == present
    assert all(k in present for k in fg.callers_map) and all(k in present for k in fg.callees_map)
    assert all(p in present for m in fg.callers_map.values() for p in m)


def test_rebuild_after_removing_a_module_leaves_no_stale_state():
    docs = make_docs()
    fg = FunctionGraphEngine().build_graph(docs)
    assert any(e.target_path == "app/zeta.py" for e in fg.edges), "fixture must have edges into app/zeta.py"

    smaller = without(docs, "app/zeta.py")
    fg.build_graph(smaller)
    assert "app.zeta" not in fg.module_to_path and "zeta" not in fg.module_to_path
    assert_no_reference_to(fg, "app/zeta.py")
    assert_same_as_fresh(fg, smaller, "rebuild without app/zeta.py")

    fg.build_graph(docs)
    assert_same_as_fresh(fg, docs, "rebuild with the original documents again")


def test_package_maps_drop_removed_files():
    docs = make_docs()
    fg = FunctionGraphEngine().build_graph(docs)
    assert "lib/pkg/mod.py" in fg.package_to_files["pkg"]
    smaller = without(docs, "lib/pkg/mod.py", "lib/utils.py")
    fg.build_graph(smaller)
    assert fg.package_to_files["pkg"] == ["app/pkg/mod.py"]
    assert "lib" not in fg.package_to_files
    assert_no_reference_to(fg, "lib/utils.py")
    assert_same_as_fresh(fg, smaller, "rebuild without lib/")


def test_duplicate_module_stem_is_last_wins_like_a_fresh_build():
    docs = make_docs()
    fg = FunctionGraphEngine().build_graph(docs)
    # Both app/utils.py and lib/utils.py register the short name "utils"; the later document wins.
    assert fg.module_to_path["utils"] == "lib/utils.py"
    reordered = [d for d in docs if d.path == "lib/utils.py"] + [d for d in docs if d.path != "lib/utils.py"]
    fg.build_graph(reordered)
    assert fg.module_to_path["utils"] == "app/utils.py"
    assert_same_as_fresh(fg, reordered, "rebuild in a different document order")
    fg.build_graph(without(docs, "lib/utils.py"))
    assert fg.module_to_path["utils"] == "app/utils.py"
    assert_same_as_fresh(fg, without(docs, "lib/utils.py"), "rebuild without one duplicate module")


def test_duplicate_function_definitions_follow_global_uniqueness():
    docs = make_docs()
    fg = FunctionGraphEngine().build_graph(docs)
    unique_normalize = [e for e in fg.edges if e.target_func == "normalize" and e.edge_type == "unique_global_call"]

    fg.build_graph(without(docs, "lib/utils.py"))
    assert_same_as_fresh(fg, without(docs, "lib/utils.py"), "remove one of two duplicate definitions")
    fg.build_graph(docs)
    assert_same_as_fresh(fg, docs, "restore the duplicate definition")
    assert [e for e in fg.edges if e.target_func == "normalize" and e.edge_type == "unique_global_call"] \
        == unique_normalize


def test_adding_a_second_global_definition_matches_a_fresh_build():
    docs = make_docs()
    fg = FunctionGraphEngine().build_graph(docs)
    extra = docs + [FileDoc(path="extra/dup.py", content="def helper(x):\n    return x\n")]
    fg.build_graph(extra)
    assert_same_as_fresh(fg, extra, "add a second definition of helper")
    fg.build_graph(docs)
    assert_same_as_fresh(fg, docs, "remove the second definition again")


def test_repeated_rebuilds_are_idempotent():
    docs = make_docs()
    fg = FunctionGraphEngine()
    for _ in range(3):
        fg.build_graph(docs)
    assert_same_as_fresh(fg, docs, "three consecutive rebuilds")
    fg.build_graph([])
    assert_same_as_fresh(fg, [], "rebuild with no documents")
    assert fg.module_to_path == {} and fg.package_to_files == {} and fg.edges == []


def test_extraction_caches_are_reused_across_rebuilds(monkeypatch):
    docs = make_docs()
    fg = FunctionGraphEngine().build_graph(docs)
    calls = []
    real = FunctionGraphEngine.extract_polyglot

    def counting(self, content, filepath):
        calls.append(filepath)
        return real(self, content, filepath)

    monkeypatch.setattr(FunctionGraphEngine, "extract_polyglot", counting)
    fg.build_graph(without(docs, "app/zeta.py"))
    assert calls == [], "unchanged documents must hit the extraction cache"
    changed = [FileDoc(path=d.path, content=d.content + "\n# edited\n", is_test=d.is_test) if d.path == "app/alpha.py"
               else d for d in docs]
    fg.build_graph(changed)
    assert calls == ["app/alpha.py"]
    assert_same_as_fresh(fg, changed, "rebuild after editing one document")


def test_scip_state_does_not_survive_when_scip_is_disabled():
    docs = make_docs()
    fg = FunctionGraphEngine().build_graph(docs)
    fg.diagnostics["scip"] = {"status": "ingested"}           # what a previous SCIP build leaves behind
    fg.scip_relationships = ["relationship from an earlier build"]
    fg.build_graph(docs)
    assert "scip" not in fg.diagnostics and fg.scip_relationships == []
    assert_same_as_fresh(fg, docs, "rebuild without SCIP")


def test_scip_load_failure_diagnostic_is_kept_across_rebuilds(tmp_path):
    from reponeedle.engine import RepoNeedleEngine
    from reponeedle.models import ScipConfig

    cfg = ScipConfig(index_path=str(tmp_path / "missing.scip"), repo_root=str(tmp_path), on_error="skip")
    engine = RepoNeedleEngine.from_documents(make_docs(), scip_config=cfg)
    assert engine.scip_diagnostics["status"] == "skipped"
    engine.update_documents([FileDoc(path="app/new.py", content="def f():\n    return 1\n")])
    assert engine.scip_diagnostics["status"] == "skipped"
    engine.remove_documents(["app/new.py"])
    assert engine.scip_diagnostics["status"] == "skipped"


def test_tree_sitter_rebuilds_match_a_fresh_build():
    from tree_sitter_support import load_docs, require_tree_sitter

    require_tree_sitter("typescript")
    docs = load_docs("typescript")
    assert len(docs) >= 2
    fg = FunctionGraphEngine(structural_parser="tree_sitter").build_graph(docs)
    smaller = docs[1:]
    fg.build_graph(smaller)
    assert_no_reference_to(fg, docs[0].path)
    assert_same_as_fresh(fg, smaller, "Tree-sitter rebuild without one file", structural_parser="tree_sitter")
    fg.build_graph(docs)
    assert_same_as_fresh(fg, docs, "Tree-sitter rebuild with all files", structural_parser="tree_sitter")


@pytest.mark.parametrize("structural_parser", ["regex", "tree_sitter"])
def test_tree_sitter_diagnostics_reset_per_build(structural_parser):
    if structural_parser == "tree_sitter":
        from tree_sitter_support import require_tree_sitter
        require_tree_sitter("typescript")
    docs = make_docs()
    fg = FunctionGraphEngine(structural_parser=structural_parser).build_graph(docs)
    fg.build_graph(without(docs, "app/zeta.py"))
    assert_same_as_fresh(fg, without(docs, "app/zeta.py"), "diagnostics after a rebuild",
                         structural_parser=structural_parser)
