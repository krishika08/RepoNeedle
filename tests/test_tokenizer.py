"""
Tests for CodeTokenizer and token estimation.
"""

import pytest
from reponeedle.core.tokenizer import CodeTokenizer, split_identifier, estimate_tokens


def test_split_identifier():
    assert "get" in split_identifier("getHTTPResponse")
    assert "response" in split_identifier("getHTTPResponse")
    assert "api" in split_identifier("test_api_client_v2")
    assert "v2" in split_identifier("test_api_client_v2")
    assert split_identifier("") == []
    assert split_identifier(None) == []


def test_estimate_tokens():
    text = "def hello_world():\n    return 'Hello, World!'\n"
    tokens = estimate_tokens(text)
    assert tokens > 0
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0


def test_code_tokenizer_path():
    tokenizer = CodeTokenizer()
    tokens = tokenizer.tokenize_path("src/flask/sessions.py")
    assert "src" in tokens
    assert "flask" in tokens
    assert "sessions" in tokens
    assert "sessions.py" in tokens


def test_code_tokenizer_text():
    tokenizer = CodeTokenizer()
    text = "Fix AttributeError in SecureCookieSessionInterface when parsing cookies."
    tokens = tokenizer.tokenize_text(text)
    assert "attributeerror" in tokens
    assert "securecookiesessioninterface" in tokens
    assert "cookies" in tokens
    assert "the" not in tokens  # Stop word removed

