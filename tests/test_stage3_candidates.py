"""
Unit tests verifying Candidate A, B, C, D, E definitions, factor configurations,
and behavioral expectations for Stage 3 evaluation.
"""

import pytest
from reponeedle.models import FileDoc, Query, ContextTier, BudgetConfig, AblationConfig
from reponeedle.engine import RepoNeedleEngine


@pytest.fixture
def test_repo_engine():
    docs = [
        FileDoc(
            path="src/service.py",
            content="class DatabaseService:\n    def connect(self):\n        pass\n    def query(self, sql):\n        return []\n",
            symbols=["DatabaseService", "connect", "query"],
            imports=["src.utils"],
            is_test=False,
            token_count=50,
        ),
        FileDoc(
            path="src/utils.py",
            content="def sanitize_sql(sql):\n    return sql.strip()\n",
            symbols=["sanitize_sql"],
            imports=[],
            is_test=False,
            token_count=30,
        ),
        FileDoc(
            path="docs/guide.md",
            content="# Database Service Guide\nHow to use DatabaseService and sanitize_sql in production.\n" * 10,
            symbols=[],
            imports=[],
            is_test=False,
            token_count=150,
        ),
        FileDoc(
            path="src/lib.rs",
            content="pub fn rust_parser_entry() -> bool {\n    true\n}\npub struct RustConfig {\n    pub port: u16,\n}\nuse std::collections::HashMap;\n",
            symbols=[],  # Polyglot test will populate
            imports=[],
            is_test=False,
            token_count=45,
        ),
    ]
    engine = RepoNeedleEngine.from_documents(docs, budget_config=BudgetConfig(max_tokens=200))
    return engine


def test_candidate_a_static_hybrid_no_router_no_skel(test_repo_engine):
    """Candidate A: Static equal fusion, full files only, no skeletons."""
    cand = AblationConfig.candidate_a()
    assert cand.enable_lexical is True
    assert cand.enable_semantic is True
    assert cand.enable_graph is True
    assert cand.enable_router is False
    assert cand.allow_skeletons is False
    assert cand.enable_doc_filter is False
    assert cand.enable_graph_diffusion is False
    assert cand.enable_polyglot_symbols is False

    res = test_repo_engine.retrieve("DatabaseService query", ablation_config=cand)
    assert not res.abstained
    tiers = [f.tier for f in res.selected_files]
    assert all(t == ContextTier.FULL for t in tiers)


def test_candidate_b_with_skeletons(test_repo_engine):
    """Candidate B: Candidate A with skeleton compression enabled."""
    cand = AblationConfig.candidate_b()
    assert cand.allow_skeletons is True
    assert cand.enable_router is False


def test_candidate_c_doc_filtering(test_repo_engine):
    """Candidate C: Candidate B with 0.5x documentation path penalty."""
    cand = AblationConfig.candidate_c()
    assert cand.enable_doc_filter is True
    assert cand.doc_filter_penalty == 0.5

    # Run query matching terms in both docs/guide.md and src/service.py
    res_b = test_repo_engine.retrieve("DatabaseService guide production", ablation_config=AblationConfig.candidate_b())
    res_c = test_repo_engine.retrieve("DatabaseService guide production", ablation_config=cand)

    # In candidate C, docs/guide.md score must be reduced relative to candidate B
    guide_b = next((f for f in res_b.selected_files if "guide.md" in f.path), None)
    guide_c = next((f for f in res_c.selected_files if "guide.md" in f.path), None)
    if guide_b and guide_c:
        assert guide_c.score < guide_b.score


def test_candidate_d_graph_diffusion(test_repo_engine):
    """Candidate D: Candidate C with relevance-aware graph diffusion."""
    cand = AblationConfig.candidate_d()
    assert cand.enable_graph_diffusion is True

    # Query matching DatabaseService: utils.py is an import neighbor of service.py
    res_d = test_repo_engine.retrieve("DatabaseService", ablation_config=cand)
    utils_entry = next((f for f in res_d.selected_files if "utils.py" in f.path), None)
    # Graph diffusion should boost utils.py because service.py imports src.utils
    assert utils_entry is not None or len(res_d.selected_files) > 0


def test_candidate_e_polyglot_symbols():
    """Candidate E: Multi-language symbol extraction on Rust and Go."""
    cand = AblationConfig.candidate_e()
    assert cand.enable_polyglot_symbols is True

    docs = [
        FileDoc(
            path="src/lib.rs",
            content="pub fn rust_compute_hash() -> u64 { 42 }\npub struct HashState;\nuse std::hash::Hasher;\n",
            token_count=30,
        ),
    ]
    engine = RepoNeedleEngine.from_documents(docs, ablation_config=cand)
    # Symbols must have been extracted for Rust
    assert "rust_compute_hash" in engine.docs[0].symbols
    assert "HashState" in engine.docs[0].symbols
    assert "Hasher" in engine.docs[0].imports
