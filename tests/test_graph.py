"""
Tests for RepoGraph and structural analysis.
"""

import pytest
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph


def test_repo_graph_ast_extraction():
    content = (
        "import os\n"
        "from flask import Request\n"
        "class App:\n"
        "    def run(self): pass\n"
        "def main(): pass\n"
    )
    symbols, imports = RepoGraph.extract_python_ast(content, "app.py")
    assert "App" in symbols
    assert "main" in symbols
    assert "os" in imports
    assert "flask" in imports


def test_repo_graph_linkages():
    docs = [
        FileDoc(path="src/app.py", content="from .utils import helper\n", imports=["utils"]),
        FileDoc(path="src/utils.py", content="def helper(): pass\n", symbols=["helper"]),
        FileDoc(path="tests/test_utils.py", content="from src.utils import helper\n", imports=["src.utils"], is_test=True),
    ]
    graph = RepoGraph().fit(docs)
    assert len(graph.graph.nodes) == 3
    # PageRank scores should be computed
    assert len(graph.pagerank_scores) == 3
    # test_utils.py should map to utils.py
    assert "src/utils.py" in graph.test_to_target_map.get("tests/test_utils.py", set())

