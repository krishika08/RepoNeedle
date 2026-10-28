"""
Unit tests verifying that the 5 controlled ablation switches operate orthogonally
and modify only the intended component behavior.
"""

import pytest
from reponeedle.models import FileDoc, Query, TaskType, ContextTier, BudgetConfig, AblationConfig
from reponeedle.engine import RepoNeedleEngine


@pytest.fixture
def sample_engine():
    docs = [
        FileDoc(
            path="src/calc.py",
            content="def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n",
            symbols=["add", "multiply"],
            imports=[],
            is_test=False,
            token_count=30,
        ),
        FileDoc(
            path="tests/test_calc.py",
            content="from src.calc import add\ndef test_add():\n    assert add(1, 2) == 3\n",
            symbols=["test_add"],
            imports=["src.calc"],
            is_test=True,
            token_count=35,
        ),
        FileDoc(
            path="src/advanced.py",
            content="class AdvancedCalculator:\n    '''Advanced mathematical engine.'''\n" + "".join(f"    def compute_{i}(self):\n        return {i} * 42\n" for i in range(100)),
            symbols=["AdvancedCalculator"] + [f"compute_{i}" for i in range(100)],
            imports=[],
            is_test=False,
            token_count=1500,
        ),
    ]
    engine = RepoNeedleEngine.from_documents(docs, budget_config=BudgetConfig(max_tokens=500))
    return engine


def test_switch_a_lexical_ablation(sample_engine):
    """Switch A (enable_lexical=False) must zero lexical scores while preserving semantic/graph."""
    q = "add two numbers calculator"
    
    # Baseline (Lexical enabled)
    res_full = sample_engine.retrieve(q, ablation_config=AblationConfig(enable_lexical=True))
    lex_scores_full = [f.lexical_score for f in res_full.selected_files]
    assert any(s > 0.0 for s in lex_scores_full), "Baseline must have positive lexical scores"

    # Ablated (Lexical disabled)
    res_ablated = sample_engine.retrieve(q, ablation_config=AblationConfig(enable_lexical=False))
    lex_scores_abl = [f.lexical_score for f in res_ablated.selected_files]
    assert all(s == 0.0 for s in lex_scores_abl), "Ablated lexical must yield exactly 0.0 lexical scores"
    # Semantic or graph should still be computed
    assert any(f.semantic_score > 0.0 or f.structural_score > 0.0 for f in res_ablated.selected_files)


def test_switch_b_semantic_ablation(sample_engine):
    """Switch B (enable_semantic=False) must zero semantic scores while preserving lexical/graph."""
    q = "add two numbers calculator"
    
    # Baseline
    res_full = sample_engine.retrieve(q, ablation_config=AblationConfig(enable_semantic=True))
    sem_scores_full = [f.semantic_score for f in res_full.selected_files]
    assert any(s > 0.0 for s in sem_scores_full), "Baseline must have positive semantic scores"

    # Ablated
    res_ablated = sample_engine.retrieve(q, ablation_config=AblationConfig(enable_semantic=False))
    sem_scores_abl = [f.semantic_score for f in res_ablated.selected_files]
    assert all(s == 0.0 for s in sem_scores_abl), "Ablated semantic must yield exactly 0.0 semantic scores"
    assert any(f.lexical_score > 0.0 for f in res_ablated.selected_files)


def test_switch_c_graph_ablation(sample_engine):
    """Switch C (enable_graph=False) must zero structural scores and test linkages."""
    q = "Write a regression test for add"
    
    res_full = sample_engine.retrieve(q, ablation_config=AblationConfig(enable_graph=True))
    res_no_graph = sample_engine.retrieve(q, ablation_config=AblationConfig(enable_graph=False))
    
    struct_scores_abl = [f.structural_score for f in res_no_graph.selected_files]
    assert all(s == 0.0 for s in struct_scores_abl), "Ablated graph must yield exactly 0.0 structural scores"


def test_switch_d_router_ablation(sample_engine):
    """Switch D (enable_router=False) must use static equal fusion and zero workflow boosts."""
    q = "Traceback (most recent call last):\n  File 'src/calc.py', line 2, in add\nZeroDivisionError"
    
    # Router enabled: should classify as trace2code and apply trace frame boosts
    res_routed = sample_engine.retrieve(q, ablation_config=AblationConfig(enable_router=True))
    assert res_routed.task_type == TaskType.TRACE2CODE
    boosts_routed = [f.workflow_boost for f in res_routed.selected_files]
    assert any(b > 0.0 for b in boosts_routed), "Router must produce workflow boosts"

    # Router disabled: should default to static fusion and zero workflow boost
    res_static = sample_engine.retrieve(q, ablation_config=AblationConfig(enable_router=False))
    assert res_static.task_type == TaskType.COMMENT2CONTEXT
    boosts_static = [f.workflow_boost for f in res_static.selected_files]
    assert all(b == 0.0 for b in boosts_static), "Static fusion must produce zero workflow boosts"


def test_switch_e_skeleton_compression_ablation(sample_engine):
    """Switch E (allow_skeletons=False) must prevent skeleton generation and require full files."""
    # Query matching advanced calculator: full file is 1500 tokens.
    # At budget 400, full file cannot fit, but its skeleton (~100 tokens) fits easily.
    q = "AdvancedCalculator mathematical engine compute_5"
    
    # With skeletons enabled
    res_skel = sample_engine.retrieve(q, budget_tokens=400, ablation_config=AblationConfig(allow_skeletons=True))
    tiers_skel = [f.tier for f in res_skel.selected_files]
    assert ContextTier.SKELETON in tiers_skel, "With skeletons enabled, oversized file must be packed as skeleton"

    # With skeletons disabled
    res_no_skel = sample_engine.retrieve(q, budget_tokens=400, ablation_config=AblationConfig(allow_skeletons=False))
    tiers_no_skel = [f.tier for f in res_no_skel.selected_files]
    assert ContextTier.SKELETON not in tiers_no_skel, "With skeletons disabled, tier must NEVER be skeleton"
    assert all(t == ContextTier.FULL for t in tiers_no_skel)
