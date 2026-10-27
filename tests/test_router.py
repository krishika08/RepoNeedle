"""
Tests for WorkflowRouter intent classification.
"""

import pytest
from reponeedle.models import Query, TaskType
from reponeedle.core.router import WorkflowRouter


def test_classify_trace2code():
    router = WorkflowRouter()
    trace_query = Query(
        text=(
            "Traceback (most recent call last):\n"
            '  File "src/flask/app.py", line 28, in wsgi_app\n'
            "KeyError: 'endpoint'\n"
        )
    )
    task, meta = router.classify_intent(trace_query)
    assert task == TaskType.TRACE2CODE
    assert "trace_frames" in meta
    assert len(meta["trace_frames"]) > 0


def test_classify_code2test():
    router = WorkflowRouter()
    query = Query(text="Find regression test suite and unit tests for SecureCookieSession.")
    task, _ = router.classify_intent(query)
    assert task == TaskType.CODE2TEST


def test_classify_edit2ripple():
    router = WorkflowRouter()
    query = Query(text="Modifying ctx.py. What files have ripple effect and affected callers?", anchor_files=["ctx.py"])
    task, _ = router.classify_intent(query)
    assert task == TaskType.EDIT2RIPPLE


def test_classify_comment2context():
    router = WorkflowRouter()
    query = Query(text="Add support for HTTP/2 streaming and multipart upload.")
    task, _ = router.classify_intent(query)
    assert task == TaskType.COMMENT2CONTEXT

