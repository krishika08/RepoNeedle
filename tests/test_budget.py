"""
Tests for BudgetOptimizer context packing and skeleton generation.
"""

import pytest
from reponeedle.models import FileDoc, BudgetConfig, ContextTier
from reponeedle.core.budget import BudgetOptimizer


def test_budget_packing_within_limit():
    optimizer = BudgetOptimizer(BudgetConfig(max_tokens=500, allow_skeletons=True))
    candidates = [
        (FileDoc(path="a.py", content="x = 1\n", token_count=100), 0.9, {}),
        (FileDoc(path="b.py", content="y = 2\n", token_count=200), 0.8, {}),
        (FileDoc(path="c.py", content="z = 3\n", token_count=400), 0.7, {}),
    ]
    packed = optimizer.pack_context(candidates, budget_tokens=350)
    total_toks = sum(f.token_count for f in packed)
    assert total_toks <= 350
    assert len(packed) >= 1


def test_skeleton_generation():
    optimizer = BudgetOptimizer()
    content = (
        "'''Module docstring.'''\n"
        "import os\n"
        "class BigModel:\n"
        "    '''Class docstring.'''\n"
        "    def method_one(self):\n"
        "        " + ("print('line')\n        " * 80) +
        "        return True\n"
        "    def method_two(self):\n"
        "        return False\n"
    )
    skeleton, tokens = optimizer.generate_skeleton(content, "big.py")
    assert "class BigModel" in skeleton
    assert "def method_one" in skeleton
    assert "def method_two" in skeleton
    assert tokens < len(content.splitlines()) * 10
