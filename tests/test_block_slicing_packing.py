"""
CUD-Pack integration of AST block slicing (``BudgetConfig.focus_span_strategy``).

* The default ("legacy") strategy must reproduce the baseline packer exactly: focus spans, skeletons and packs are
  compared with tests/fixtures/block_slicing/legacy_golden.json, generated from the packer on main at 0c0effe.
* With "ast_blocks", the hard invariant ``sum(token_count) <= budget`` and exact prompt accounting hold at every
  budget and in both modes, and output is deterministic.

Runs without optional extras; Tree-sitter languages simply fall back to the legacy span when it is missing.
"""

import json

import pytest

from block_slicing_support import (BUDGETS, GOLDEN, LANGUAGE_FIXTURES, QUERIES, fixture_corpus, legacy_snapshot,
                                   read)
from reponeedle.core import block_slicing as bs
from reponeedle.core import packer
from reponeedle.core.packer import CodeSpanExtractor, CUDPackOptimizer
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import BudgetConfig, ContextTier, FileDoc

AST = BudgetConfig(focus_span_strategy="ast_blocks")


# --- the default path is unchanged ----------------------------------------------------------------

def test_default_strategy_is_legacy():
    assert BudgetConfig().focus_span_strategy == "legacy"
    with pytest.raises(Exception):
        BudgetConfig(focus_span_strategy="blocks")


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.parametrize("config", [None, BudgetConfig(focus_span_strategy="legacy")], ids=["default", "explicit"])
def test_legacy_outputs_match_the_baseline_golden(golden, config):
    current = legacy_snapshot(packer, config)
    for key in ("focus_spans", "skeletons", "packs"):
        assert current[key] == golden[key], f"{key} changed relative to the baseline packer"


def test_legacy_explanations_carry_no_block_note():
    content = read("python/packer_snapshot.py")
    sel = CUDPackOptimizer().pack_context([{"path": "p.py", "content": content, "rank": 1, "score": 1.0}], 1500,
                                          query_text="skeleton extract", mode="compact")
    assert sel and all("ast_blocks" not in s.explanation for s in sel)


# --- ast_blocks: budget invariants ----------------------------------------------------------------

def _candidates():
    return [{"path": p, "content": c, "rank": i, "score": 1.0 / i}
            for i, (p, c) in enumerate(fixture_corpus().items(), start=1)]


@pytest.mark.parametrize("mode", ["compact", "complete"])
@pytest.mark.parametrize("budget", BUDGETS + [40, 60, 3000])
def test_budget_is_never_exceeded_and_accounting_is_exact(mode, budget):
    for q in QUERIES:
        optimizer = CUDPackOptimizer(AST)
        selected = optimizer.pack_context(_candidates(), budget, query_text=" ".join(q), mode=mode)
        total = sum(s.token_count for s in selected)
        assert total <= budget
        prompt = optimizer.tokenizer.render_prompt(selected)
        assert optimizer.tokenizer.count_tokens(prompt) == total
        for s in selected:
            assert s.token_count == optimizer.tokenizer.package_file(s.path, s.rendered_content)[1]


def test_every_tier_is_still_produced():
    tiers = set()
    for mode in ("compact", "complete"):
        for budget in BUDGETS:
            for q in QUERIES[:3]:
                tiers.update(s.tier for s in CUDPackOptimizer(AST).pack_context(
                    _candidates(), budget, query_text=" ".join(q), mode=mode))
    assert {ContextTier.FULL, ContextTier.FOCUS_SPAN, ContextTier.SKELETON} <= tiers


def test_a_large_block_span_cannot_overflow_a_tight_budget():
    body = "".join(f"        value_{i} = target + {i}\n" for i in range(110))
    content = "import math\n\n\nclass Big:\n    def target_method(self):\n" + body + "        return 0\n" + \
              "".join(f"\nCONST_{i} = {i}" for i in range(20)) + "\n"
    ex = CodeSpanExtractor()
    span, _ = ex.extract_block_span(content, "big.py", {"target"})
    assert ex.slice_blocks(content, "big.py", {"target"}).selected[0][1] == "target_method"
    span_tokens = ex.tokenizer.package_file("big.py", span)[1]
    for budget in (span_tokens - 1, span_tokens, span_tokens + 1, 100, 400):
        for mode in ("compact", "complete"):
            sel = CUDPackOptimizer(AST).pack_context([{"path": "big.py", "content": content, "rank": 1, "score": 1}],
                                                     budget, query_text="target", mode=mode)
            assert sum(s.token_count for s in sel) <= budget
            for s in sel:
                if s.tier == ContextTier.FOCUS_SPAN:
                    assert s.rendered_content == span          # never a truncated block


def test_ast_blocks_output_is_deterministic():
    runs = []
    for _ in range(3):
        sel = CUDPackOptimizer(AST).pack_context(_candidates(), 4096, query_text="restock threshold", mode="compact")
        runs.append([(s.path, s.tier, s.token_count, s.rendered_content) for s in sel])
    assert runs[0] == runs[1] == runs[2]


def test_focus_span_explanation_names_the_strategy():
    content = read(LANGUAGE_FIXTURES["python"])
    sel = CUDPackOptimizer(AST).pack_context([{"path": "inv.py", "content": content, "rank": 1, "score": 1.0}],
                                             600, query_text="ceil", mode="compact")
    assert sel[0].tier == ContextTier.FOCUS_SPAN
    assert "[ast_blocks: python, 1 block(s)]" in sel[0].explanation
    assert "def restock_quantity" in sel[0].rendered_content and "def reserve" not in sel[0].rendered_content


# --- caching ------------------------------------------------------------------------------------------

def test_cache_is_keyed_by_content_path_and_terms():
    content = read(LANGUAGE_FIXTURES["python"])
    ex = CodeSpanExtractor()
    first = ex.extract_block_span(content, "inv.py", {"ceil"})
    assert ex.extract_block_span(content, "inv.py", {"ceil"}) == first
    changed = content.replace("math.ceil", "math.floor")
    assert ex.extract_block_span(changed, "inv.py", {"ceil"}) != first          # content change: recomputed
    assert ex.extract_block_span(content, "inv.py", {"release"}) != first      # different terms
    assert ex.extract_block_span(content, "inv.txt", {"ceil"}) == ex.extract_focus_span(content, "inv.txt", {"ceil"})
    assert ex.extract_block_span(content, "inv.py", {"ceil"}) == first


def test_caches_are_bounded(monkeypatch):
    monkeypatch.setattr(CodeSpanExtractor, "BLOCK_STRUCTURE_CACHE_SIZE", 2)
    monkeypatch.setattr(CodeSpanExtractor, "BLOCK_SPAN_CACHE_SIZE", 3)
    ex = CodeSpanExtractor()
    content = read(LANGUAGE_FIXTURES["python"])
    for i in range(6):
        ex.extract_block_span(content + f"\nX{i} = {i}\n", f"m{i}.py", {"reserve", f"t{i}"})
    assert len(ex._structure_cache) == 2 and len(ex._block_cache) == 3


def test_structure_is_parsed_once_per_file(monkeypatch):
    calls = []
    real = bs.analyze_structure
    monkeypatch.setattr(bs, "analyze_structure", lambda c, p: calls.append(p) or real(c, p))
    ex = CodeSpanExtractor()
    content = read(LANGUAGE_FIXTURES["python"])
    for terms in ({"reserve"}, {"release"}, {"ceil"}):
        ex.extract_block_span(content, "inv.py", terms)
    assert calls == ["inv.py"]


# --- engine -------------------------------------------------------------------------------------------

def _docs():
    return [FileDoc(path=p, content=c) for p, c in fixture_corpus().items() if p.endswith(".py")]


def test_engine_accepts_the_opt_in_and_respects_the_budget():
    engine = RepoNeedleEngine.from_documents(_docs(), budget_config=AST)
    result = engine.retrieve("why does restock planning ignore the threshold", budget_tokens=1500)
    assert result.total_tokens <= 1500
    assert engine.budget_optimizer.config.focus_span_strategy == "ast_blocks"
    default = RepoNeedleEngine.from_documents(_docs()).retrieve("why does restock planning ignore the threshold",
                                                                 budget_tokens=1500)
    assert all("ast_blocks" not in s.explanation for s in default.selected_files)
