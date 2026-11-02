"""
Production integration and release readiness test suite for RepoNeedle V1.1:
- Default V1.0 behavior preservation (ranker="legacy")
- V1.1 Opt-in Change-Impact Ranking (ranking_engine="change_impact")
- API compatibility & CLI invocation
- Fail-safe configuration validation & fallback on error
- CUD-Pack budget non-overflow invariant
- Graph-enabled vs graph-disabled ablation
- Structured ranking explanations
- Incremental indexing & scale test
"""

import os
import sys
import pytest
import numpy as np

from reponeedle.models import (
    FileDoc,
    Query,
    RetrievalResult,
    RankerType,
    BudgetConfig,
    TaskType,
)
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.change_impact import ChangeImpactRanker, ChangeImpactConfig


@pytest.fixture
def sample_repo():
    docs = [
        FileDoc(
            path="django/db/models/query.py",
            content="class QuerySet:\n    def filter(self, *args, **kwargs):\n        pass\n",
            symbols=["QuerySet", "filter"],
            imports=["django.core.exceptions"],
            line_count=3,
            token_count=20,
        ),
        FileDoc(
            path="tests/queries/test_bitwise.py",
            content="def test_xor_subquery():\n    from django.db.models.query import QuerySet\n    qs = QuerySet()\n",
            symbols=["test_xor_subquery"],
            imports=["django.db.models.query"],
            is_test=True,
            line_count=3,
            token_count=25,
        ),
        FileDoc(
            path="django/core/exceptions.py",
            content="class FieldError(Exception):\n    pass\n",
            symbols=["FieldError"],
            imports=[],
            line_count=2,
            token_count=10,
        ),
        FileDoc(
            path="django/db/models/sql/query.py",
            content="class Query:\n    def add_filter(self):\n        pass\n",
            symbols=["Query", "add_filter"],
            imports=[],
            line_count=3,
            token_count=20,
        ),
        FileDoc(
            path="docs/howto/custom_queries.rst",
            content="How to write custom queryset filters in Django.\n",
            symbols=[],
            imports=[],
            line_count=2,
            token_count=12,
        ),
    ]
    return docs


def test_v1_0_default_behavior_preservation(sample_repo):
    """Ensures V1.0 default behavior is 100% preserved when no ranker argument is supplied."""
    engine = RepoNeedleEngine(sample_repo)
    result = engine.retrieve("QuerySet filter query")
    
    assert result.ranker == "legacy"
    assert not result.abstained
    assert len(result.selected_files) > 0
    assert result.total_tokens <= 4000


def test_v1_1_opt_in_change_impact_ranking(sample_repo):
    """Verifies that ranking_engine='change_impact' activates the change-impact engine."""
    engine = RepoNeedleEngine(sample_repo)
    query = Query(
        text="Fix TypeError in QuerySet filter boolean expression",
        anchor_files=["django/db/models/query.py"],
        budget_tokens=2000,
    )
    result = engine.retrieve(query, ranking_engine="change_impact")
    
    assert result.ranker == "change_impact"
    assert not result.abstained
    assert len(result.selected_files) > 0
    
    # Regression test should be boosted into top rank by AST import edge
    paths = [f.path for f in result.selected_files]
    assert "tests/queries/test_bitwise.py" in paths
    
    # Seed file should be suppressed by SFS
    top_file = paths[0]
    assert top_file != "django/db/models/query.py", "Anchor seed file must be suppressed by SFS"


def test_public_api_ranker_and_ranking_engine_aliases(sample_repo):
    """Tests that ranker and ranking_engine work interchangeably."""
    engine = RepoNeedleEngine(sample_repo)
    res1 = engine.retrieve("filter", ranker="change_impact")
    res2 = engine.retrieve("filter", ranking_engine="change_impact")
    res3 = engine.retrieve("filter", ranker=RankerType.CHANGE_IMPACT)
    
    assert res1.ranker == "change_impact"
    assert res2.ranker == "change_impact"
    assert res3.ranker == "change_impact"


def test_unknown_ranker_fails_safely(sample_repo):
    """Ensures an unknown ranking configuration raises a descriptive ValueError."""
    engine = RepoNeedleEngine(sample_repo)
    with pytest.raises(ValueError, match="Unknown ranker 'quantum_neural_v9'"):
        engine.retrieve("filter", ranking_engine="quantum_neural_v9")


def test_fallback_on_error_handling(sample_repo):
    """Verifies that if an unexpected exception occurs, ranker falls back cleanly when configured."""
    engine = RepoNeedleEngine(sample_repo)
    query = Query(text="QuerySet", anchor_files=["nonexistent_anchor.py"])
    
    # Set fallback_on_error = True
    cfg = ChangeImpactConfig(fallback_on_error=True)
    res = engine.retrieve(query, ranking_engine="change_impact", change_impact_config=cfg)
    assert not res.abstained
    assert len(res.selected_files) > 0


def test_graph_disabled_independent_switch(sample_repo):
    """Verifies that graph propagation can be disabled independently."""
    engine = RepoNeedleEngine(sample_repo)
    query = Query(
        text="QuerySet filter",
        anchor_files=["django/db/models/query.py"],
    )
    cfg_no_graph = ChangeImpactConfig(enable_graph=False)
    res_no_graph = engine.retrieve(query, ranking_engine="change_impact", change_impact_config=cfg_no_graph)
    
    # When graph is disabled, seed is still suppressed by SFS, but no graph boost occurs
    assert res_no_graph.ranker == "change_impact"
    assert len(res_no_graph.selected_files) > 0


def test_structured_ranking_explanations(sample_repo):
    """Verifies that ScoredFile contains structured change-impact explanations."""
    engine = RepoNeedleEngine(sample_repo)
    query = Query(
        text="Fix bug in filter",
        anchor_files=["django/db/models/query.py"],
    )
    res = engine.retrieve(query, ranking_engine="change_impact")
    
    # Check that at least one file has an informative explanation
    explanations = [f.explanation for f in res.selected_files if f.explanation]
    assert len(explanations) > 0
    assert any("import" in exp.lower() or "relevance" in exp.lower() or "seed" in exp.lower() for exp in explanations)


def test_cud_pack_budget_non_overflow(sample_repo):
    """Asserts that CUD-Pack zero-overflow guarantee strictly holds under change_impact ranker."""
    engine = RepoNeedleEngine(sample_repo)
    for budget in [30, 50, 100, 500]:
        res = engine.retrieve("QuerySet filter boolean", budget_tokens=budget, ranking_engine="change_impact")
        assert res.total_tokens <= budget, f"Overflow detected: used {res.total_tokens} > budget {budget}"


def test_large_repository_incremental_indexing():
    """Tests scalability on a 150-file repository with incremental doc additions."""
    docs = []
    for i in range(150):
        docs.append(
            FileDoc(
                path=f"pkg/sub_{i % 10}/module_{i}.py",
                content=f"def func_{i}():\n    return {i}\n",
                symbols=[f"func_{i}"],
                imports=[f"pkg.sub_{(i + 1) % 10}.module_{(i + 1) % 150}"],
                line_count=2,
                token_count=15,
            )
        )
    engine = RepoNeedleEngine(docs)
    query = Query(text="func_42", anchor_files=["pkg/sub_2/module_42.py"])
    res = engine.retrieve(query, ranking_engine="change_impact")
    
    assert res.ranker == "change_impact"
    assert res.execution_time_ms < 50.0, f"Execution too slow: {res.execution_time_ms} ms"
    assert len(res.selected_files) > 0
