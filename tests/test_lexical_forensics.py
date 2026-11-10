"""
Milestone 2C: lexical forensics harness (benchmarks/run_lexical_forensics.py).

The forensic conclusions depend on each harness variant changing exactly one documented factor
relative to the production BM25Index; these tests pin that down. Production code is unchanged.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))

import run_lexical_forensics as L  # noqa: E402
from reponeedle.core.lexical import BM25Index  # noqa: E402
from reponeedle.core.tokenizer import CodeTokenizer  # noqa: E402
from reponeedle.models import FileDoc  # noqa: E402

PHASE3 = ROOT / "reports" / "experimental" / "phase3_lexical_retrieval"

DOCS = [
    FileDoc(path="src/auth/session.py", content="class SessionManager:\n    def refresh_token(self):\n        return 'session timeout'\n"),
    FileDoc(path="docs/guide.md", content="Session timeout guide. Configure the refresh token and the session."),
    FileDoc(path="tests/test_session.py", content="def test_timeout():\n    assert SessionManager().refresh_token()\n"),
    FileDoc(path="src/util.py", content="def helper():\n    return 42\n"),
]
QUERY = json.dumps({"review_comment": "make session timeout configurable", "path": "src/auth/session.py",
                    "diff_hunk_context": "@@ -1,3 +1,4 @@ refresh_token refresh_token session"})


class TestProductionTokenizerFacts:

    def test_plain_words_are_counted_twice(self):
        """Documented forensic finding: the production tokenizer emits plain words twice."""
        assert CodeTokenizer().tokenize_text("session").count("session") == 2

    def test_production_bm25_ignores_query_term_frequency(self):
        idx = BM25Index().fit(DOCS)
        assert np.array_equal(idx.score("session timeout"), idx.score("session session session timeout"))


class TestHarnessVariants:

    def test_baseline_variant_equals_production(self):
        assert np.array_equal(L.VariantBM25().fit(DOCS).score(QUERY), BM25Index().fit(DOCS).score(QUERY))

    def test_fit_tokens_equals_fit(self):
        for cfg in L.VARIANTS.values():
            tok = L.DedupeTokenizer() if cfg.get("dedupe") else CodeTokenizer()
            a = L.make_index(cfg).fit_tokens(DOCS, L.shared_tokens(DOCS, tok)).score(QUERY)
            b = L.make_index(cfg).fit(DOCS).score(QUERY)
            assert np.array_equal(a, b), cfg

    def test_dedupe_emits_each_token_once_per_word(self):
        toks = L.DedupeTokenizer().tokenize_text("session refresh_token SessionManager")
        assert toks == ["session", "refresh_token", "refresh", "token", "sessionmanager", "session", "manager"]

    def test_query_tf_variant_uses_query_counts(self):
        idx = L.VariantBM25(query_tf=True).fit(DOCS)
        assert not np.array_equal(idx.score("session timeout"), idx.score("session session session timeout"))

    def test_json_values_only_drops_keys_and_keeps_values(self):
        text = L.json_leaf_text(QUERY)
        assert "review_comment" not in text and "diff_hunk_context" not in text
        assert "make session timeout configurable" in text and "src/auth/session.py" in text

    def test_json_values_only_leaves_non_json_unchanged(self):
        assert L.json_leaf_text("plain text query") == "plain text query"
        assert L.json_leaf_text("[1, 2]") == "[1, 2]"

    def test_variants_change_one_factor_each(self):
        for name, cfg in L.VARIANTS.items():
            assert len(cfg) <= 1, name


@pytest.mark.skipif(not (PHASE3 / "protocol.json").exists(), reason="Phase 3 protocol not registered")
class TestProtocolIntegrity:

    def test_protocol_hash_matches(self):
        L.verify_protocol()

    def test_dev_only_data(self):
        dev, _ = L.dev_repos()
        for stage in ("lexical", "hybrid"):
            for p in (PHASE3 / stage).glob("shard_*.jsonl") if (PHASE3 / stage).exists() else []:
                for line in open(p, encoding="utf-8"):
                    assert json.loads(line)["repo"] in dev

    def test_selection_artifacts_hashed(self):
        for name in ("hybrid_candidates", "dev_selection"):
            path = PHASE3 / f"{name}.json"
            if path.exists():
                recorded = (PHASE3 / f"{name}.sha256").read_text(encoding="utf-8").split()[0]
                assert L.canonical_hash(json.loads(path.read_text(encoding="utf-8"))) == recorded
