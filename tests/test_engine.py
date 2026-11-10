"""
Integration tests for RepoNeedleEngine end-to-end functionality.
"""

import pytest
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import FileDoc, Query, TaskType


def test_engine_end_to_end_retrieval():
    docs = [
        FileDoc(path="auth.py", content="class Auth:\n    def login(): pass\n", symbols=["Auth", "login"]),
        FileDoc(path="models.py", content="class User:\n    pass\n", symbols=["User"]),
        FileDoc(path="tests/test_auth.py", content="from auth import Auth\ndef test_login(): pass\n", symbols=["test_login"], is_test=True),
    ]
    engine = RepoNeedleEngine.from_documents(docs)

    # 1. Query for login
    res = engine.retrieve("How to login with user credentials", budget_tokens=2000)
    assert not res.abstained
    assert len(res.selected_files) > 0
    assert res.selected_files[0].path in ("auth.py", "models.py")

    # 2. Query for tests
    res_test = engine.retrieve("Find tests for Auth login", budget_tokens=2000)
    assert not res_test.abstained
    # test_auth.py should be retrieved
    paths = [f.path for f in res_test.selected_files]
    assert "tests/test_auth.py" in paths

    # 3. Out-of-repo counterfactual query should abstain when the experimental heuristic is
    #    explicitly enabled (opt-in since 1.2.0; see test_abstention_opt_in.py for the default).
    res_abs = engine.retrieve(
        "Cargo.toml rust tokio async runtime memory leak",
        budget_tokens=2000,
        enable_experimental_abstention=True,
    )
    assert res_abs.abstained
    assert len(res_abs.selected_files) == 0


def test_engine_empty_corpus():
    engine = RepoNeedleEngine.from_documents([])
    res = engine.retrieve("any query")
    assert res.abstained
    assert len(res.selected_files) == 0

