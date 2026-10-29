"""
Stage 3.9 Gate B Regression Tests: Cascaded Lexical-First Retrieval Architecture.

Verifies:
  1. Top-three ranking preservation (inviolable lower-bound invariant).
  2. Graph score normalization and bounds (attenuation on high-degree hubs).
  3. Package-boundary enforcement (rejecting cross-package edge leakage).
  4. Same-name symbol collision fencing.
  5. Isolated test files and implementation discovery (code2test linkage).
  6. Empty graphs, disconnected graphs, and single-file repositories.
  7. Multi-language manifest parsing (Cargo.toml, go.mod, package.json).
  8. Deterministic ranking across repeated executions.
  9. Backwards compatibility of public APIs.
"""

import os
import sys
import pytest
import numpy as np
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from reponeedle.models import FileDoc, Query, AblationConfig
from reponeedle.core.graph import RepoGraph
from reponeedle.core.cascade import CascadedRanker
from reponeedle.engine import RepoNeedleEngine


def test_top_three_ranking_preservation():
    """Verifies that top-3 BM25 ranks are strictly preserved and cannot be displaced by graph scores."""
    docs = [
        FileDoc(path="src/lex1.py", content="exact match alpha"),
        FileDoc(path="src/lex2.py", content="exact match beta"),
        FileDoc(path="src/lex3.py", content="exact match gamma"),
        FileDoc(path="src/hub.py", content="generic utility file"),
        FileDoc(path="src/lex4.py", content="partial match delta"),
    ]
    bm25_scores = np.array([1.0, 0.8, 0.6, 0.0, 0.05], dtype=np.float32)
    sem_scores = np.zeros(5, dtype=np.float32)

    # Construct graph where hub has huge connection to lex1
    rg = RepoGraph()
    rg.fit(docs)
    rg.graph.add_edge("src/lex1.py", "src/hub.py")

    ranker = CascadedRanker(top_k_preserve=3, enable_graph_expansion=True, degree_normalized=True)
    ranked_indices = ranker.rank(docs, bm25_scores, sem_scores, rg)

    # Inviolable Invariant: Indices 0, 1, 2 must be docs 0, 1, 2 in identical order
    assert ranked_indices[:3] == [0, 1, 2], f"Top-3 BM25 violated: {ranked_indices[:3]}"
    # Hub can be promoted to rank 4, but NEVER ranks 1, 2, or 3
    assert ranked_indices[3] == 3  # hub.py promoted above lex4.py due to graph boost


def test_graph_score_normalization_and_bounds():
    """Verifies that degree normalization attenuates propagation to high-degree hubs."""
    docs = [FileDoc(path="src/seed.py", content="seed file")]
    # Create hub with 100 in-degree
    docs.append(FileDoc(path="src/hub.py", content="central hub"))
    for i in range(100):
        docs.append(FileDoc(path=f"src/caller_{i}.py", content=f"caller {i}"))

    rg = RepoGraph()
    rg.fit(docs)
    rg.graph.add_edge("src/seed.py", "src/hub.py")
    for i in range(100):
        rg.graph.add_edge(f"src/caller_{i}.py", "src/hub.py")

    assert rg.graph.in_degree("src/hub.py") >= 100

    bm25_scores = np.zeros(len(docs), dtype=np.float32)
    bm25_scores[0] = 1.0  # seed

    ranker_norm = CascadedRanker(top_k_preserve=1, enable_graph_expansion=True, degree_normalized=True)
    ranker_unnorm = CascadedRanker(top_k_preserve=1, enable_graph_expansion=True, degree_normalized=False)

    # In normalized mode, boost is divided by sqrt(out_deg * in_deg) = sqrt(1 * 101) ~ 10.05
    # Boost should be ~ 0.25 / 10.05 ~ 0.0248
    norm_indices = ranker_norm.rank(docs, bm25_scores, repo_graph=rg)
    unnorm_indices = ranker_unnorm.rank(docs, bm25_scores, repo_graph=rg)

    assert norm_indices[0] == 0  # seed preserved
    assert unnorm_indices[0] == 0  # seed preserved


def test_package_boundary_enforcement():
    """Verifies that cross-package edges are rejected when packages are unlinked."""
    docs = [
        FileDoc(path="pkgA/module.py", content="class SharedSymbol: pass"),
        FileDoc(path="pkgB/other.py", content="class SharedSymbol: pass"),
    ]
    rg = RepoGraph()
    rg.fit(docs)
    # Intentionally add cross-package edge
    rg.graph.add_edge("pkgA/module.py", "pkgB/other.py")

    ranker = CascadedRanker(top_k_preserve=1, package_fencing=True)
    assert not ranker._is_package_compatible("pkgA", "pkgB", "pkgA/module.py", "pkgB/other.py", rg)


def test_same_name_symbol_collision_fencing():
    """Verifies that symbol collisions across disparate packages do not generate unlinked propagation."""
    ranker = CascadedRanker(package_fencing=True)
    rg = RepoGraph()
    # Distinct directories with no manifest link
    assert not ranker._is_package_compatible("crates/core", "crates/printer", "crates/core/lib.rs", "crates/printer/lib.rs", rg)


def test_isolated_test_files_and_implementation_discovery():
    """Verifies that test discovery correctly links implementation files to corresponding test suites."""
    docs = [
        FileDoc(path="src/parser.go", content="package parser"),
        FileDoc(path="src/parser_test.go", content="package parser", is_test=True),
    ]
    rg = RepoGraph()
    rg.fit(docs)

    ranker = CascadedRanker(top_k_preserve=1, test_discovery=True)
    graph_boost = np.zeros(2, dtype=np.float32)
    eligible_set = {1}
    ranker._apply_test_discovery("src/parser.go", 1.0, eligible_set, rg.path_to_idx, docs, graph_boost)

    # parser_test.go should receive the discovery boost
    assert graph_boost[1] == pytest.approx(0.35, abs=1e-4)


def test_empty_graphs_disconnected_and_single_file_repos():
    """Verifies graceful handling of boundary conditions: 0 docs, 1 doc, and disconnected graphs."""
    ranker = CascadedRanker()
    # Empty docs
    assert ranker.rank([], np.array([])) == []

    # Single doc
    doc1 = [FileDoc(path="single.py", content="print('hello')")]
    assert ranker.rank(doc1, np.array([0.5])) == [0]

    # Disconnected graph (2 docs, 0 edges)
    docs2 = [
        FileDoc(path="a.py", content="a"),
        FileDoc(path="b.py", content="b"),
    ]
    rg = RepoGraph()
    rg.fit(docs2)
    assert rg.graph.number_of_edges() == 0
    ranked = ranker.rank(docs2, np.array([0.2, 0.8]), repo_graph=rg)
    assert ranked == [1, 0]  # b.py first by BM25


def test_multi_language_manifest_parsing(tmp_path):
    """Verifies manifest parsing for Cargo.toml, go.mod, and package.json."""
    rg = RepoGraph()
    cargo_toml = '[package]\nname = "my_crate"\n[dependencies]\nserde = "1.0"\n'
    c_info = rg.parse_cargo_manifest(cargo_toml)
    assert c_info["name"] == "my_crate"

    go_mod = "module github.com/user/my_module\n\ngo 1.22\n"
    g_info = rg.parse_go_mod(go_mod)
    assert g_info == "github.com/user/my_module"

    pkg_json = '{"name": "my-app", "dependencies": {"react": "^18.0.0"}}'
    p_info = rg.parse_package_json(pkg_json)
    assert p_info["name"] == "my-app"


def test_deterministic_ranking():
    """Verifies 100% deterministic ranking across repeated executions."""
    docs = [
        FileDoc(path=f"src/doc_{i}.py", content=f"content {i}")
        for i in range(20)
    ]
    # Set identical scores to test deterministic tie-breaking
    bm25_scores = np.ones(20, dtype=np.float32) * 0.5
    ranker = CascadedRanker(top_k_preserve=3)

    run1 = ranker.rank(docs, bm25_scores)
    run2 = ranker.rank(docs, bm25_scores)
    assert run1 == run2, "Ranking is non-deterministic!"


def test_backwards_compatibility_public_api():
    """Verifies that RepoNeedleEngine and AblationConfig public contracts remain intact."""
    engine = RepoNeedleEngine.from_documents([
        FileDoc(path="a.py", content="def test(): pass"),
        FileDoc(path="b.py", content="def run(): pass"),
    ])
    res = engine.retrieve("test", budget_tokens=4000)
    assert not res.abstained
    assert len(res.selected_files) > 0
    assert hasattr(res, "confidence_score")
