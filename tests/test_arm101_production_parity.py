"""
Test suite for Stage 3.20 ARM-101 Production Parity.
Verifies that reponeedle.core.arm101.ARM101Ranker produces identical ranking outputs
to research.stage3_14.pilot_attenuation.ExperimentalLanguageRanker(policy="unattenuated").
"""

import pytest
from reponeedle.models import FileDoc, Query, TaskType
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.function_graph import FunctionGraphEngine as ProdFG
from reponeedle.core.arm101 import ARM101Ranker

from research.stage3_14.pilot_attenuation import ExperimentalLanguageRanker
from research.stage3_11.function_graph_engine import FunctionGraphEngine as ResearchFG
from reponeedle.core.graph import RepoGraph


@pytest.fixture
def python_fixture():
    return [
        FileDoc(path="auth/models.py", content="class User:\n    def __init__(self, name):\n        self.name = name\n    def get_id(self):\n        return self.name\n"),
        FileDoc(path="auth/login.py", content="from auth.models import User\ndef login(username):\n    u = User(username)\n    return u.get_id()\n"),
        FileDoc(path="auth/service.py", content="from auth.login import login\ndef authenticate(req):\n    return login(req.user)\n"),
        FileDoc(path="tests/test_login.py", content="from auth.login import login\ndef test_auth():\n    assert login('admin') == 'admin'\n", is_test=True),
        FileDoc(path="docs/guide.md", content="# User Authentication Guide\nDetailed explanation of login mechanisms.\n"),
    ]


@pytest.fixture
def rust_fixture():
    return [
        FileDoc(path="src/parser.rs", content="pub struct AstParser;\nimpl AstParser {\n    pub fn parse(input: &str) -> bool { true }\n}\n"),
        FileDoc(path="src/lib.rs", content="pub mod parser;\npub fn parse_doc(s: &str) -> bool {\n    parser::AstParser::parse(s)\n}\n"),
        FileDoc(path="src/main.rs", content="use mycrate::parse_doc;\nfn main() {\n    parse_doc(\"test\");\n}\n"),
        FileDoc(path="tests/test_parser.rs", content="use mycrate::parse_doc;\n#[test]\nfn test_parse() {\n    assert!(parse_doc(\"ok\"));\n}\n", is_test=True),
        FileDoc(path="README.md", content="# Rust Parser Crate\nDocumentation for AST parsing.\n"),
    ]


@pytest.fixture
def go_fixture():
    return [
        FileDoc(path="pkg/db/store.go", content="package db\ntype Store struct{}\nfunc (s *Store) QueryRow(q string) string {\n    return \"result\"\n}\n"),
        FileDoc(path="pkg/api/handler.go", content="package api\nimport \"pkg/db\"\nfunc HandleUser(s *db.Store) string {\n    return s.QueryRow(\"select user\")\n}\n"),
        FileDoc(path="pkg/api/handler_test.go", content="package api\nimport \"testing\"\nfunc TestHandleUser(t *testing.T) {\n    // test handle user\n}\n", is_test=True),
        FileDoc(path="cmd/server/main.go", content="package main\nimport \"pkg/api\"\nfunc main() {\n    // start server\n}\n"),
        FileDoc(path="doc/api.txt", content="API documentation for Go endpoints.\n"),
    ]


def test_python_parity(python_fixture):
    docs = python_fixture
    engine = RepoNeedleEngine.from_documents(docs)

    rg = RepoGraph()
    rg.fit(docs)
    rfg = ResearchFG(enable_verified_calls=True, enable_structural_edges=True)
    rfg.build_graph(docs)
    rranker = ExperimentalLanguageRanker(policy="unattenuated")

    for q in ["login user", "test auth", "User get_id"]:
        lex = engine.lexical_index.score(q)
        sem = engine.semantic_index.score(q)

        expected = rranker.rank(docs, lex, sem, rfg, rg)
        actual = engine.arm101_ranker.rank(docs, lex, sem, engine.function_graph, engine.repo_graph)
        assert expected == actual, f"Mismatch for query {q}"

        res = engine.retrieve(q, ranker="arm101", budget_tokens=8000)
        assert [docs[i].path for i in actual] == res.ranked_files


def test_rust_parity(rust_fixture):
    docs = rust_fixture
    engine = RepoNeedleEngine.from_documents(docs)

    rg = RepoGraph()
    rg.fit(docs)
    rfg = ResearchFG(enable_verified_calls=True, enable_structural_edges=True)
    rfg.build_graph(docs)
    rranker = ExperimentalLanguageRanker(policy="unattenuated")

    for q in ["AstParser parse", "test parse_doc"]:
        lex = engine.lexical_index.score(q)
        sem = engine.semantic_index.score(q)

        expected = rranker.rank(docs, lex, sem, rfg, rg)
        actual = engine.arm101_ranker.rank(docs, lex, sem, engine.function_graph, engine.repo_graph)
        assert expected == actual, f"Mismatch for query {q}"


def test_go_parity(go_fixture):
    docs = go_fixture
    engine = RepoNeedleEngine.from_documents(docs)

    rg = RepoGraph()
    rg.fit(docs)
    rfg = ResearchFG(enable_verified_calls=True, enable_structural_edges=True)
    rfg.build_graph(docs)
    rranker = ExperimentalLanguageRanker(policy="unattenuated")

    for q in ["Store database", "HandleUser test"]:
        lex = engine.lexical_index.score(q)
        sem = engine.semantic_index.score(q)

        expected = rranker.rank(docs, lex, sem, rfg, rg)
        actual = engine.arm101_ranker.rank(docs, lex, sem, engine.function_graph, engine.repo_graph)
        assert expected == actual, f"Mismatch for query {q}"


def test_empty_repo():
    engine = RepoNeedleEngine.from_documents([])
    res = engine.retrieve("query", ranker="arm101")
    assert res.abstained
    assert len(res.selected_files) == 0
    assert res.ranker == "arm101"
