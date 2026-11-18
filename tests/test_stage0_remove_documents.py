"""
V2 Stage 0: RepoNeedleEngine.remove_documents(), an in-memory removal path whose result equals a fresh build over
the remaining documents in their existing order.
"""

import builtins
import os

import pytest

from equivalence_fixture import FILES, write_files
from index_equivalence import assert_equivalent, compare_index_state, load_queries
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import FileDoc

QUERIES = load_queries()[::15]         # 15 queries spread over the categories


def fixture_docs():
    return [FileDoc(path=p, content=c, symbols=[], is_test="test" in p) for p, c in FILES.items()]


def fresh(docs):
    return RepoNeedleEngine.from_documents([d.model_copy(deep=True) for d in docs])


def assert_equals_fresh(engine, remaining_paths, label, mutations=()):
    by_path = {d.path: d for d in fixture_docs()}
    reference = fresh([by_path[p] for p in remaining_paths])
    assert_equivalent(engine, reference, label=label, mutations=mutations, queries=QUERIES, packing_queries=5)


def test_removal_matches_a_fresh_build_and_preserves_order():
    engine = fresh(fixture_docs())
    order = [d.path for d in engine.docs]
    removed = engine.remove_documents(["shop/pricing.py", "web/src/api.ts"])
    assert removed == ["shop/pricing.py", "web/src/api.ts"]
    remaining = [p for p in order if p not in removed]
    assert [d.path for d in engine.docs] == remaining and list(engine.path_to_doc) == remaining
    assert_equals_fresh(engine, remaining, "remove two documents", ["remove shop/pricing.py, web/src/api.ts"])


def test_returned_paths_follow_index_order_not_request_order():
    engine = fresh(fixture_docs())
    order = [d.path for d in engine.docs]
    request = ["web/src/api.ts", "shop/cart.py"]
    assert engine.remove_documents(request) == [p for p in order if p in request]


def test_empty_request_is_a_no_op():
    engine = fresh(fixture_docs())
    before = compare_index_state(engine, fresh(fixture_docs()))
    assert engine.remove_documents([]) == []
    assert engine.remove_documents(iter(())) == []
    assert compare_index_state(engine, fresh(fixture_docs())) == before
    assert not any(before.values())


def test_duplicates_in_the_request_are_removed_once():
    engine = fresh(fixture_docs())
    assert engine.remove_documents(["shop/cart.py", "shop/cart.py"]) == ["shop/cart.py"]
    assert "shop/cart.py" not in engine.path_to_doc


@pytest.mark.parametrize("request_paths", [["missing.py"], ["shop/cart.py", "missing.py"], ["SHOP/CART.PY"],
                                           ["shop\\cart.py"]])
def test_unknown_paths_raise_and_change_nothing(request_paths):
    engine = fresh(fixture_docs())
    with pytest.raises(KeyError, match="not indexed"):
        engine.remove_documents(request_paths)
    assert not any(compare_index_state(engine, fresh(fixture_docs())).values())


def test_removing_an_already_removed_path_raises():
    engine = fresh(fixture_docs())
    engine.remove_documents(["shop/cart.py"])
    with pytest.raises(KeyError):
        engine.remove_documents(["shop/cart.py"])


@pytest.mark.parametrize("bad", ["shop/cart.py", b"shop/cart.py", [1], [None]])
def test_invalid_argument_types_raise_type_error(bad):
    engine = fresh(fixture_docs())
    with pytest.raises(TypeError):
        engine.remove_documents(bad)
    assert len(engine.docs) == len(FILES)


def test_removing_every_document_equals_an_empty_engine():
    engine = fresh(fixture_docs())
    engine.remove_documents(list(engine.path_to_doc))
    assert engine.docs == [] and engine.path_to_doc == {}
    assert_equivalent(engine, RepoNeedleEngine(), label="remove every document", queries=QUERIES, packing_queries=5)
    result = engine.retrieve("cart total")
    assert result.abstained and result.ranked_files == []


def test_removing_the_only_provider_of_an_imported_module():
    engine = fresh(fixture_docs())
    assert any(e.target_path == "shop/utils/strings.py" for e in engine.function_graph.edges)
    engine.remove_documents(["shop/utils/strings.py"])
    fg, rg = engine.function_graph, engine.repo_graph
    assert all("shop/utils/strings.py" not in (e.source_path, e.target_path) for e in fg.edges)
    assert "shop/utils/strings.py" not in fg.module_to_path.values()
    assert "shop/utils/strings.py" not in rg.module_to_path.values()
    assert "shop/utils/strings.py" not in rg.graph
    remaining = [p for p in FILES if p != "shop/utils/strings.py"]
    assert_equals_fresh(engine, [d.path for d in fresh(fixture_docs()).docs if d.path in remaining],
                        "remove the only provider of shop.utils.strings")


def test_removing_one_of_two_duplicate_definitions():
    engine = fresh(fixture_docs())
    engine.remove_documents(["legacy/utils.py"])
    order = [d.path for d in fresh(fixture_docs()).docs if d.path != "legacy/utils.py"]
    assert_equals_fresh(engine, order, "remove one of two normalize() definitions")


def test_removal_reads_no_files_without_scip(monkeypatch):
    engine = fresh(fixture_docs())

    def forbidden(*args, **kwargs):
        raise AssertionError("remove_documents() must not touch the filesystem")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(os, "stat", forbidden)
    monkeypatch.setattr(os, "walk", forbidden)
    engine.remove_documents(["shop/cart.py"])


def test_failed_refit_restores_the_previous_documents(monkeypatch):
    engine = fresh(fixture_docs())
    calls = {"n": 0}
    real_fit = engine.semantic_index.fit

    def failing_once(docs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated refit failure")
        return real_fit(docs)

    monkeypatch.setattr(engine.semantic_index, "fit", failing_once)
    with pytest.raises(RuntimeError, match="simulated"):
        engine.remove_documents(["shop/cart.py"])
    monkeypatch.undo()
    assert "shop/cart.py" in engine.path_to_doc
    assert not any(compare_index_state(engine, fresh(fixture_docs())).values()), "engine was not restored"


def test_directory_engine_after_removal_equals_a_fresh_scan(tmp_path):
    root = write_files(tmp_path / "repo", FILES)
    engine = RepoNeedleEngine.from_directory(str(root))
    engine.remove_documents(["shop/inventory.py"])
    (root / "shop" / "inventory.py").unlink()
    assert_equivalent(engine, RepoNeedleEngine.from_directory(str(root)), label="from_directory, removal + rescan",
                      mutations=["remove_documents(shop/inventory.py)", "delete file on disk"], queries=QUERIES,
                      packing_queries=5)


def test_removing_a_file_with_scip_relationships(tmp_path):
    from scip_support import require_protobuf
    require_protobuf()
    from test_scip_graph import _repo
    from reponeedle.models import ScipConfig

    root, index_path = _repo(tmp_path)
    cfg = ScipConfig(index_path=index_path)
    engine = RepoNeedleEngine.from_directory(str(root), scip_config=cfg)
    assert engine.function_graph.scip_relationships and any(
        e.edge_type == "scip_reference" for e in engine.function_graph.edges)
    # SCIP resolution checks document paths on disk during every refit, so delete first, as a user would.
    (root / "util.ts").unlink()
    engine.remove_documents(["util.ts"])
    assert all(e.target_path != "util.ts" for e in engine.function_graph.edges)
    assert engine.scip_diagnostics["documents"]["missing"] == ["util.ts"]
    reference = RepoNeedleEngine.from_directory(str(root), scip_config=cfg)
    assert_equivalent(engine, reference, label="remove a SCIP-covered file", queries=QUERIES, packing_queries=None)
