"""
Tests for SubwordSemanticIndex.
"""

import pytest
import numpy as np
from reponeedle.models import FileDoc
from reponeedle.core.semantic import SubwordSemanticIndex


def test_semantic_subword_matching():
    docs = [
        FileDoc(path="auth.py", content="class AuthenticationManager:\n    def verify_token(self): pass\n", symbols=["AuthenticationManager", "verify_token"]),
        FileDoc(path="calc.py", content="def calculate_matrix_sum(): pass\n", symbols=["calculate_matrix_sum"]),
    ]
    index = SubwordSemanticIndex().fit(docs)
    # Query with morphological variant "authenticator" and "tokens"
    scores = index.score("authenticator tokens")
    assert scores[0] > scores[1]
    assert scores[0] > 0.0


def test_semantic_empty():
    index = SubwordSemanticIndex().fit([])
    scores = index.score("test")
    assert len(scores) == 0

