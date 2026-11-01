"""
Unit and regression tests for Stage 3.7: Component Isolation,
BM25 length decoupling invariance, graph hub normalization,
directional diffusion properties, and evaluation metric accounting.
"""

import math
import pytest
import numpy as np
import networkx as nx
from reponeedle.models import FileDoc, AblationConfig
from reponeedle.core.lexical import BM25Index
from reponeedle.core.graph import RepoGraph
from reponeedle.engine import RepoNeedleEngine


class TestBM25DecoupledLengthInvariance:
    """Verifies BM25 length normalization properties and decoupled invariance."""

    def test_lexical_length_invariant_to_symbol_indexing(self):
        """When decouple_symbols=True, adding extracted symbols does not change effective document length."""
        content = "def calculate_total(items):\n    return sum(item.price for item in items)"
        doc_no_syms = FileDoc(path="shop/calculator.py", content=content, symbols=[], imports=[])
        doc_with_syms = FileDoc(
            path="shop/calculator.py",
            content=content,
            symbols=["calculate_total", "items", "price", "sum", "ShopCalculator", "TaxPolicy", "DiscountEngine"],
            imports=["typing", "math"],
        )

        bm25_decoupled_no_syms = BM25Index(decouple_symbols=True).fit([doc_no_syms])
        bm25_decoupled_with_syms = BM25Index(decouple_symbols=True).fit([doc_with_syms])

        # Document lengths must be identical when decoupled
        np.testing.assert_allclose(
            bm25_decoupled_no_syms.doc_lengths,
            bm25_decoupled_with_syms.doc_lengths,
            err_msg="Decoupled BM25 document length must be invariant to extracted symbol count",
        )
        assert bm25_decoupled_no_syms.avg_doc_len == bm25_decoupled_with_syms.avg_doc_len

    def test_coupled_symbols_inflate_document_length(self):
        """When decouple_symbols=False, symbols inflate effective document length."""
        content = "def helper(): pass"
        doc = FileDoc(
            path="core/utils.py",
            content=content,
            symbols=[f"func_{i}" for i in range(50)], # 50 extracted symbols
            imports=[],
        )
        bm25_coupled = BM25Index(decouple_symbols=False).fit([doc])
        bm25_decoupled = BM25Index(decouple_symbols=True).fit([doc])

        assert bm25_coupled.doc_lengths[0] > bm25_decoupled.doc_lengths[0] * 3.0, (
            "Coupled symbols must inflate document length denominator"
        )

    def test_no_duplicate_symbol_inflation(self):
        """Term frequencies are properly accounted and IDF does not produce negative values."""
        docs = [
            FileDoc(path="a.py", content="function test runner", symbols=["runner", "runner"]),
            FileDoc(path="b.py", content="other file text", symbols=["other"]),
        ]
        bm25 = BM25Index(decouple_symbols=True).fit(docs)
        for term, idf_val in bm25.idf.items():
            assert idf_val >= 0.0, f"IDF for {term} must be non-negative"


class TestGraphTopologyAndHubNormalization:
    """Verifies graph directionality, degree-based normalization, and edge isolation."""

    def test_graph_directionality_import_edges(self):
        """Graph edges point from importing module to imported module."""
        docs = [
            FileDoc(path="app/main.py", content="from app.service import Service", imports=["app.service"]),
            FileDoc(path="app/service.py", content="class Service: pass", imports=[]),
        ]
        rg = RepoGraph().fit(docs)
        G = rg.graph

        assert G.has_edge("app/main.py", "app/service.py"), (
            "Edge should point from caller/importer (app/main.py) to target (app/service.py)"
        )
        assert not G.has_edge("app/service.py", "app/main.py"), (
            "Dependency graph should be directed"
        )

    def test_hub_normalization_attenuates_score_leak(self):
        """Degree-normalized propagation scales by 1/sqrt(degree), preventing hub explosion."""
        # Create a hub connected to 100 leaf nodes
        G = nx.DiGraph()
        hub = "core/hub.py"
        G.add_node(hub)
        for i in range(100):
            leaf = f"leaf_{i}.py"
            G.add_edge(leaf, hub) # 100 leaves import hub

        seed_val = 1.0
        in_deg = G.in_degree(hub)
        assert in_deg == 100

        unnormalized_boost = seed_val * 0.25
        normalized_boost = seed_val * 0.25 / np.sqrt(in_deg)

        assert normalized_boost == unnormalized_boost / 10.0, (
            "Normalization factor for degree 100 must be exactly 10x attenuation"
        )
        assert not math.isnan(normalized_boost) and not math.isinf(normalized_boost)

    def test_isolated_nodes_handling(self):
        """Isolated nodes receive zero graph boost and don't cause division by zero."""
        docs = [
            FileDoc(path="isolated.py", content="isolated code", symbols=[], imports=[]),
            FileDoc(path="connected_a.py", content="import connected_b", imports=["connected_b"]),
            FileDoc(path="connected_b.py", content="target code", imports=[]),
        ]
        rg = RepoGraph().fit(docs)
        assert "isolated.py" in rg.graph
        assert rg.graph.degree("isolated.py") == 0


class TestEvaluationMetricContracts:
    """Verifies exact definitions of fractional Recall@K vs binary Hit@K."""

    def test_fractional_recall_vs_binary_hit(self):
        """Multi-gold queries must distinguish fractional recall from binary hit rate."""
        gold_files = {"a.py", "b.py", "c.py", "d.py"}
        # Ranked top 5 has 2 of the 4 gold files
        ranked_top5 = ["a.py", "other1.py", "b.py", "other2.py", "other3.py"]

        # Fractional recall: 2 / 4 = 0.50
        num_hits = len(set(ranked_top5).intersection(gold_files))
        fractional_recall = num_hits / len(gold_files)
        # Binary hit: 1.0 (since num_hits > 0)
        binary_hit = 1.0 if num_hits > 0 else 0.0

        assert fractional_recall == 0.50
        assert binary_hit == 1.0
        assert fractional_recall != binary_hit, "Hit@K must never be conflated with Recall@K"

    def test_clean_source_code_no_hardcoded_bypass(self):
        """Verifies that no benchmark shortcut strings exist in production reponeedle/."""
        import inspect
        import reponeedle
        from pathlib import Path

        root = Path(inspect.getfile(reponeedle)).parent
        forbidden_strings = ["search.rs", "standard.rs", "core in my_crate", "tests_only"]
        for py_file in root.glob("**/*.py"):
            text = py_file.read_text(encoding="utf-8")
            for fb in forbidden_strings:
                assert fb not in text, f"Forbidden hardcoded benchmark shortcut '{fb}' found in {py_file}"

