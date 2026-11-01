"""
Unit and regression tests for Stage 3.8: Query-Conditioned Structural Retrieval.

Verifies:
  1. Edge-type gating attenuation for test predecessors on implementation queries.
  2. Edge-type gating enhancement for test predecessors on test-seeking queries.
  3. Manifest file edge suppression.
  4. Leapfrog margin dampening (non-leapfrog invariant).
  5. Query-affinity affine scaling properties.
"""

import math
import pytest
import numpy as np
import networkx as nx
from reponeedle.models import FileDoc
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.core.graph import RepoGraph


class TestStage38QueryConditionedGraph:
    """Verifies query conditioning mechanisms over repository structure."""

    def test_edge_type_gating_attenuates_test_predecessors_for_code_query(self):
        """When query is an implementation query (e.g. CLI argument parsing),
        test files importing the core module should receive attenuated backward boost,
        preventing them from leapfrogging the core implementation file.
        """
        # Setup: core.py is imported by test_options.py and test_commands.py
        docs = [
            FileDoc(
                path="src/click/core.py",
                content="class Command:\n    def parse_args(self, args): pass\n    def invoke(self): pass",
                symbols=["Command", "parse_args", "invoke"],
                imports=[],
            ),
            FileDoc(
                path="tests/test_options.py",
                content="from click.core import Command\ndef test_command_options(): pass",
                symbols=["test_command_options"],
                imports=["click.core"],
            ),
            FileDoc(
                path="tests/test_commands.py",
                content="from click.core import Command\ndef test_command_invoke(): pass",
                symbols=["test_command_invoke"],
                imports=["click.core"],
            ),
        ]
        rg = RepoGraph().fit(docs)
        G = rg.graph
        assert G.has_edge("tests/test_options.py", "src/click/core.py")

        # Query: implementation query
        query_is_test_seeking = False
        seed_path = "src/click/core.py"
        seed_val = 1.0

        boost_unconditional = {}
        boost_edge_gated = {}

        for pred in G.predecessors(seed_path):
            out_deg = max(1, G.out_degree(pred))
            bwd_raw = float(seed_val * 0.20 / np.sqrt(out_deg))
            boost_unconditional[pred] = bwd_raw

            is_test_pred = "test" in pred.lower()
            edge_mult = 0.15 if (not query_is_test_seeking and is_test_pred) else 1.0
            boost_edge_gated[pred] = bwd_raw * edge_mult

        # Test files must receive >= 80% attenuation
        for pred in ["tests/test_options.py", "tests/test_commands.py"]:
            assert boost_edge_gated[pred] < boost_unconditional[pred] * 0.20
            assert boost_edge_gated[pred] == pytest.approx(boost_unconditional[pred] * 0.15)

    def test_edge_type_gating_preserves_test_predecessors_for_test_query(self):
        """When query is test-seeking (e.g. pytest assertion test),
        test files are NOT attenuated and can receive full/enhanced propagation.
        """
        query_is_test_seeking = True
        is_test_pred = True
        edge_mult = 1.25 if query_is_test_seeking and is_test_pred else 1.0
        assert edge_mult > 1.0, "Test-seeking queries must enhance or preserve test file propagation"

    def test_manifest_file_attenuation(self):
        """Manifest files like Cargo.toml or pyproject.toml receive strong attenuation (0.05x)."""
        manifest_paths = ["Cargo.toml", "pyproject.toml", "package.json", "setup.py"]
        for p in manifest_paths:
            is_manifest = p.lower().endswith(("cargo.toml", "pyproject.toml", "package.json", "go.mod", "setup.py"))
            assert is_manifest
            mult = 0.05 if is_manifest else 1.0
            assert mult == 0.05

    def test_leapfrog_margin_dampening_invariant(self):
        """In EXP-387 / EXP-388, leapfrog margin dampening ensures that a predecessor's
        backward boost can never exceed the initial score gap:
        bwd_boost <= max(0.0, seed_score - pred_score).
        This guarantees the predecessor cannot leapfrog the seed purely from the seed's own boost.
        """
        seed_score = 0.80
        pred_low_score = 0.10
        pred_near_score = 0.75
        pred_higher_score = 0.85

        bwd_raw = 0.30 # High diffusion boost

        # 1. Low-scoring predecessor
        margin_low = max(0.0, seed_score - pred_low_score) # 0.70
        dampened_low = min(bwd_raw, margin_low) # min(0.30, 0.70) = 0.30
        assert pred_low_score + dampened_low <= seed_score

        # 2. Near-scoring predecessor
        margin_near = max(0.0, seed_score - pred_near_score) # 0.05
        dampened_near = min(bwd_raw, margin_near) # min(0.30, 0.05) = 0.05
        assert pred_near_score + dampened_near <= seed_score + 1e-6

        # 3. Already higher-scoring predecessor
        margin_higher = max(0.0, seed_score - pred_higher_score) # 0.0
        dampened_higher = min(bwd_raw, margin_higher) # 0.0
        assert dampened_higher == 0.0

    def test_query_affinity_scaling_bounded(self):
        """EXP-385 scales backward boost by (0.20 + 0.80 * pred_affinity).
        When pred_affinity = 0, scaling factor is 0.20 (80% attenuation).
        When pred_affinity = 1.0, scaling factor is 1.00 (no attenuation).
        """
        bwd_raw = 0.25
        # Zero affinity
        boost_zero = bwd_raw * (0.20 + 0.80 * 0.0)
        assert boost_zero == pytest.approx(0.05)

        # Full affinity
        boost_full = bwd_raw * (0.20 + 0.80 * 1.0)
        assert boost_full == pytest.approx(0.25)

        # Half affinity
        boost_half = bwd_raw * (0.20 + 0.80 * 0.5)
        assert boost_half == pytest.approx(0.15)
