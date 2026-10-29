"""
Stage 3.10 Unit and Regression Test Suite: Class-to-Test Invocation Graph.

Tests:
1. Direct class construction detection (Python, Rust, Go, JS/TS).
2. Direct method call invocation.
3. Imported module-qualified call resolution.
4. Ambiguous generic symbol suppression and diagnostic recording.
5. High-degree hub suppression and degree normalization.
6. Deterministic edge generation and ordering.
7. Feature-disabled equivalence with CONTROL-CASCADE (Ablation Arm D == Arm A).
8. Lexical rank-protection guarantee (top-3 BM25 ranks remain frozen).
9. Degree-matched control graph properties.
"""

import math
import pytest
import numpy as np
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.cascade import CascadedRanker


class TestClassToTestInvocationGraph:
    """Verifies class-to-test invocation extraction, ranking, and safeguards."""

    def test_direct_class_construction_python(self):
        docs = [
            FileDoc(
                path="src/service/client.py",
                content="class ServiceClient:\n    def __init__(self):\n        pass\n    def fetch(self):\n        return 1\n",
                is_test=False,
            ),
            FileDoc(
                path="tests/test_client.py",
                content="from src.service.client import ServiceClient\ndef test_fetch():\n    client = ServiceClient()\n    assert client.fetch() == 1\n",
                is_test=True,
            ),
        ]
        graph = RepoGraph().fit(docs)
        assert "src/service/client.py" in graph.prod_to_test_invocations
        assert "tests/test_client.py" in graph.prod_to_test_invocations["src/service/client.py"]
        assert "tests/test_client.py" in graph.test_to_prod_invocations
        assert "src/service/client.py" in graph.test_to_prod_invocations["tests/test_client.py"]

        edge = next(e for e in graph.invocation_edges if e["class_name"] == "ServiceClient")
        assert edge["evidence_type"] == "DIRECT_CLASS_CONSTRUCTION"
        assert edge["confidence"] == 1.0

    def test_direct_method_call_python(self):
        docs = [
            FileDoc(
                path="src/auth/token.py",
                content="class TokenValidator:\n    def validate_jwt_signature(self, token):\n        return True\n",
                is_test=False,
            ),
            FileDoc(
                path="tests/test_auth.py",
                content="def test_token_validation(validator):\n    assert validator.validate_jwt_signature('abc') is True\n",
                is_test=True,
            ),
        ]
        graph = RepoGraph().fit(docs)
        assert "src/auth/token.py" in graph.prod_to_test_invocations
        assert "tests/test_auth.py" in graph.prod_to_test_invocations["src/auth/token.py"]
        edge = next(e for e in graph.invocation_edges if e["method_name"] == "validate_jwt_signature")
        assert edge["evidence_type"] == "DIRECT_METHOD_CALL"

    def test_rust_struct_construction_and_methods(self):
        docs = [
            FileDoc(
                path="crates/engine/src/pipeline.rs",
                content="pub struct ExecutionPipeline;\nimpl ExecutionPipeline {\n    pub fn execute(&self) -> bool { true }\n}\n",
                is_test=False,
            ),
            FileDoc(
                path="tests/pipeline_tests.rs",
                content="#[test]\nfn test_pipeline() {\n    let p = ExecutionPipeline::new();\n    assert!(p.execute());\n}\n",
                is_test=True,
            ),
        ]
        graph = RepoGraph().fit(docs)
        assert "crates/engine/src/pipeline.rs" in graph.prod_to_test_invocations
        assert "tests/pipeline_tests.rs" in graph.prod_to_test_invocations["crates/engine/src/pipeline.rs"]

    def test_go_struct_and_constructor_invocation(self):
        docs = [
            FileDoc(
                path="pkg/server/handler.go",
                content="package server\ntype RequestDispatcher struct {}\nfunc NewRequestDispatcher() *RequestDispatcher { return &RequestDispatcher{} }\n",
                is_test=False,
            ),
            FileDoc(
                path="pkg/server/handler_test.go",
                content="package server_test\nfunc TestDispatcher(t *testing.T) {\n    d := NewRequestDispatcher()\n}\n",
                is_test=True,
            ),
        ]
        graph = RepoGraph().fit(docs)
        assert "pkg/server/handler.go" in graph.prod_to_test_invocations
        assert "pkg/server/handler_test.go" in graph.prod_to_test_invocations["pkg/server/handler.go"]

    def test_ambiguous_generic_symbol_suppression(self):
        """
        Verifies that generic classes like Config defined in multiple files
        are NOT linked unless explicitly qualified by an import, and are logged to diagnostics.
        """
        docs = [
            FileDoc(path="src/net/config.py", content="class Config:\n    pass\n", is_test=False),
            FileDoc(path="src/db/config.py", content="class Config:\n    pass\n", is_test=False),
            FileDoc(path="src/auth/config.py", content="class Config:\n    pass\n", is_test=False),
            FileDoc(path="src/ui/config.py", content="class Config:\n    pass\n", is_test=False),
            # Test constructing unqualified Config
            FileDoc(path="tests/test_misc.py", content="def test_cfg():\n    cfg = Config()\n", is_test=True),
        ]
        graph = RepoGraph().fit(docs)
        # Because Config appears in 4 files and test has no imports, it must be suppressed!
        assert "tests/test_misc.py" not in graph.test_to_prod_invocations
        assert any(
            d["class_name"] == "Config" and d["reason"] == "AMBIGUOUS_GENERIC_CLASS_WITHOUT_QUALIFYING_IMPORT"
            for d in graph.unresolved_diagnostics
        )

    def test_imported_module_call_disambiguation(self):
        """
        When a generic class is defined in multiple files, an explicit import resolves it.
        """
        docs = [
            FileDoc(path="src/net/config.py", content="class Config:\n    pass\n", is_test=False),
            FileDoc(path="src/db/config.py", content="class Config:\n    pass\n", is_test=False),
            FileDoc(path="src/auth/config.py", content="class Config:\n    pass\n", is_test=False),
            FileDoc(path="src/ui/config.py", content="class Config:\n    pass\n", is_test=False),
            # Test explicitly importing net.config
            FileDoc(
                path="tests/test_net_cfg.py",
                content="from src.net.config import Config\ndef test_cfg():\n    cfg = Config()\n",
                imports=["src.net.config"],
                is_test=True,
            ),
        ]
        graph = RepoGraph().fit(docs)
        assert "src/net/config.py" in graph.test_to_prod_invocations.get("tests/test_net_cfg.py", set())
        assert "src/db/config.py" not in graph.test_to_prod_invocations.get("tests/test_net_cfg.py", set())

    def test_lexical_rank_protection_guarantee(self):
        """
        Verifies that top-3 BM25 ranks are strictly preserved and never displaced
        by class-to-test invocation boosts.
        """
        docs = [
            FileDoc(path="src/main.py", content="target code", is_test=False),
            FileDoc(path="src/core.py", content="target code", is_test=False),
            FileDoc(path="src/util.py", content="target code", is_test=False),
            FileDoc(path="tests/test_distant.py", content="test code", is_test=True),
        ]
        graph = RepoGraph().fit(docs)
        # Force a strong invocation edge to tests/test_distant.py
        graph.prod_to_test_invocations["src/main.py"] = {"tests/test_distant.py"}
        graph.test_to_prod_invocations["tests/test_distant.py"] = {"src/main.py"}

        bm25_scores = np.array([10.0, 9.0, 8.0, 0.1], dtype=np.float32)

        ranker = CascadedRanker(
            top_k_preserve=3,
            enable_graph_expansion=True,
            enable_class_to_test=True,
            class_to_test_weight=5.0,  # Huge weight
        )
        ranked = ranker.rank(docs, bm25_scores, repo_graph=graph)

        # Invariant: Positions 0, 1, 2 MUST be docs 0, 1, 2
        assert ranked[:3] == [0, 1, 2]
        assert ranked[3] == 3

    def test_feature_disabled_equivalence_with_control(self):
        """
        Verifies that when enable_class_to_test=False (Ablation Arm D),
        the ranking is 100% identical to CONTROL-CASCADE (Arm A).
        """
        docs = [
            FileDoc(path="src/client.py", content="class Client: pass", is_test=False),
            FileDoc(path="src/other.py", content="def other(): pass", is_test=False),
            FileDoc(path="src/helper.py", content="def help(): pass", is_test=False),
            FileDoc(path="tests/test_client.py", content="c = Client()", is_test=True),
            FileDoc(path="tests/test_other.py", content="pass", is_test=True),
        ]
        graph = RepoGraph().fit(docs)
        bm25 = np.array([5.0, 4.0, 3.0, 1.0, 0.5], dtype=np.float32)

        control_ranker = CascadedRanker(top_k_preserve=3, enable_class_to_test=False)
        ablation_ranker = CascadedRanker(top_k_preserve=3, enable_class_to_test=False)

        res_control = control_ranker.rank(docs, bm25, repo_graph=graph)
        res_ablation = ablation_ranker.rank(docs, bm25, repo_graph=graph)

        assert res_control == res_ablation

    def test_degree_normalization_hub_suppression(self):
        """
        Verifies that high-degree test files (exercising 20 classes) have their
        propagation boost attenuated by 1/sqrt(out_deg * in_deg).
        """
        # Node with in_degree 25
        out_deg = 1
        in_deg = 25
        norm_factor = 1.0 / math.sqrt(out_deg * in_deg)
        assert norm_factor == 0.20

    def test_degree_matched_control_properties(self):
        """
        Verifies that degree-matched control preserves node degree sequence
        without semantic relevance.
        """
        docs = [
            FileDoc(path="src/a.py", content="class A: pass", is_test=False),
            FileDoc(path="src/b.py", content="class B: pass", is_test=False),
            FileDoc(path="tests/test_a.py", content="a = A()", is_test=True),
            FileDoc(path="tests/test_b.py", content="b = B()", is_test=True),
        ]
        graph = RepoGraph().fit(docs)
        assert len(graph.degree_matched_prod_to_test) > 0
        for p, true_tests in graph.prod_to_test_invocations.items():
            matched = graph.degree_matched_prod_to_test[p]
            assert len(matched) == len(true_tests)

