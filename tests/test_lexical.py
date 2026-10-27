"""
Tests for BM25Index lexical search.
"""

import pytest
import numpy as np
from reponeedle.models import FileDoc
from reponeedle.core.lexical import BM25Index


def test_bm25_basic_scoring():
    docs = [
        FileDoc(path="auth.py", content="def login(username, password):\n    pass\n", symbols=["login"]),
        FileDoc(path="db.py", content="def connect_database():\n    pass\n", symbols=["connect_database"]),
        FileDoc(path="routes.py", content="def get_users():\n    pass\n", symbols=["get_users"]),
    ]
    index = BM25Index().fit(docs)
    scores = index.score("login username credentials")
    assert len(scores) == 3
    # auth.py should have the highest score
    assert np.argmax(scores) == 0
    assert scores[0] > scores[1]
    assert scores[0] > scores[2]


def test_bm25_empty():
    index = BM25Index().fit([])
    scores = index.score("anything")
    assert len(scores) == 0


def test_bm25_no_match():
    docs = [FileDoc(path="a.py", content="x = 1\n", symbols=["x"])]
    index = BM25Index().fit(docs)
    scores = index.score("completely unrelated query zzzqqq")
    assert scores[0] == 0.0
