"""
SCIP ingestion composed with Tree-sitter extraction (requires both optional extras). Each feature works
alone (tests/test_scip_graph.py runs without Tree-sitter); together, SCIP adds only edges that the
extracted graph does not already contain.
"""

import pytest

from scip_support import FIXTURES, require_protobuf
from tree_sitter_support import require_tree_sitter

require_protobuf()
require_tree_sitter("typescript")

from reponeedle.engine import RepoNeedleEngine  # noqa: E402
from reponeedle.models import AblationConfig, ScipConfig  # noqa: E402

REAL = FIXTURES / "real" / "typescript"


def _engine(parser="tree_sitter", scip=True):
    return RepoNeedleEngine.from_directory(
        str(REAL),
        ablation_config=AblationConfig(structural_parser=parser),
        scip_config=ScipConfig(index_path=str(REAL / "index.scip"), allow_project_root_mismatch=True) if scip else None,
    )


def _key(e):
    return (e.source_path, e.target_path, e.target_func)


def test_both_diagnostics_are_reported():
    engine = _engine()
    fg = engine.function_graph
    assert fg.diagnostics["structural_parser"]["files"]["tree_sitter"]
    assert fg.diagnostics["structural_parser"]["files"]["regex_fallback"] == {}
    assert engine.scip_diagnostics["status"] == "ingested"


def test_scip_never_duplicates_an_extracted_edge():
    fg = _engine().function_graph
    extracted = {_key(e) for e in fg.edges if e.edge_type != "scip_reference"}
    scip = [_key(e) for e in fg.edges if e.edge_type == "scip_reference"]
    assert scip and not (set(scip) & extracted)
    full = [(e.source_path, e.source_func, e.target_path, e.target_func, e.target_symbol, e.edge_type) for e in fg.edges]
    assert len(full) == len(set(full))


def test_tree_sitter_edges_are_unchanged_by_scip():
    with_scip = {(_key(e), e.edge_type, e.confidence) for e in _engine().function_graph.edges
                 if e.edge_type != "scip_reference"}
    without = {(_key(e), e.edge_type, e.confidence) for e in _engine(scip=False).function_graph.edges}
    assert with_scip == without


def test_scip_corroborates_tree_sitter_import_bound_edges():
    engine = _engine()
    edges = engine.scip_diagnostics["edges"]
    assert edges["already_present_from_extraction"] >= 1
    fg = engine.function_graph
    # cart.ts's `roundValue(sum)` (import alias) is a Tree-sitter verified edge; SCIP's reference agrees.
    assert ("src/models/cart.ts", "src/util/format.ts", "round") in {_key(e) for e in fg.edges if e.edge_type == "verified_call"}
    assert not any(_key(e) == ("src/models/cart.ts", "src/util/format.ts", "round") for e in fg.edges
                   if e.edge_type == "scip_reference")


@pytest.mark.parametrize("parser", ["regex", "tree_sitter"])
def test_composition_is_deterministic(parser):
    runs = [[(e.source_path, e.source_func, e.target_path, e.target_func, e.edge_type) for e in
             _engine(parser).function_graph.edges] for _ in range(2)]
    assert runs[0] == runs[1]
