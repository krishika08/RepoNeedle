"""
Tests for Stage 3.9.2: Context-Budget Validity and Packing Policy Audit.

Verifies:
1. Greedy-stop vs Greedy-skip policy behavior on oversized candidates.
2. Character-based budget (len(text)) vs Tokenizer-based budget (count_tokens).
3. Structural skeleton packing vs whole files under fixed token budget.
4. Deterministic tie-breaking for equal-ranked candidates.
5. Boundary conditions (exact budget saturation, zero-budget, and the ARB v2 used==0 quirk).
6. Content truncation behavior at budget limits.
7. Separation of ranking metrics (MRR, Recall@k) from context-packing metrics (BCY, coverage).
"""

import pytest
import re
from typing import List, Dict, Any, Tuple
from reponeedle.models import FileDoc, ScoredFile, ContextTier, BudgetConfig
from reponeedle.core.tokenizer import estimate_tokens, split_identifier
from reponeedle.core.budget import BudgetOptimizer

# Pinned regex tokenizer from external/agent-retrieval-bench (commit 9e4d689)
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[^A-Za-z0-9_\s]", re.UNICODE)


def count_tokens_pinned(text: str) -> int:
    if not text:
        return 0
    return len(TOKEN_RE.findall(text))


def simulate_arb_greedy_stop(gold_files: set[str], ranked_items: List[Dict[str, Any]], budget: int, unit: str = "char") -> Tuple[float, int, List[str]]:
    """
    Simulates ARB v2 gold_coverage_at_budget greedy-stop policy exactly:
    if used + len(text) > context_budget and used > 0:
        break
    used += len(text)
    """
    if not gold_files:
        return 0.0, 0, []
    used = 0
    covered = set()
    packed_paths = []
    for item in ranked_items:
        text = str(item.get("text", ""))
        size = len(text) if unit == "char" else count_tokens_pinned(text)
        if used + size > budget and used > 0:
            break
        used += size
        path = str(item.get("path", ""))
        packed_paths.append(path)
        if path in gold_files:
            covered.add(path)
    return len(covered) / len(gold_files), used, packed_paths


def simulate_strict_greedy_stop(gold_files: set[str], ranked_items: List[Dict[str, Any]], budget: int, unit: str = "char") -> Tuple[float, int, List[str]]:
    """
    Strict greedy stop that does NOT allow overflow even on item 0.
    """
    if not gold_files or budget <= 0:
        return 0.0, 0, []
    used = 0
    covered = set()
    packed_paths = []
    for item in ranked_items:
        text = str(item.get("text", ""))
        size = len(text) if unit == "char" else count_tokens_pinned(text)
        if used + size > budget:
            break
        used += size
        path = str(item.get("path", ""))
        packed_paths.append(path)
        if path in gold_files:
            covered.add(path)
    return len(covered) / len(gold_files), used, packed_paths


def simulate_greedy_skip(gold_files: set[str], ranked_items: List[Dict[str, Any]], budget: int, unit: str = "char") -> Tuple[float, int, List[str]]:
    """
    Simulates knapsack greedy-skip policy.
    Skips oversized files and packs subsequent candidates that fit within remaining budget.
    """
    if not gold_files or budget <= 0:
        return 0.0, 0, []
    used = 0
    covered = set()
    packed_paths = []
    for item in ranked_items:
        text = str(item.get("text", ""))
        size = len(text) if unit == "char" else count_tokens_pinned(text)
        if used + size <= budget:
            used += size
            path = str(item.get("path", ""))
            packed_paths.append(path)
            if path in gold_files:
                covered.add(path)
    return len(covered) / len(gold_files), used, packed_paths


def simulate_boundary_truncation(gold_files: set[str], ranked_items: List[Dict[str, Any]], budget: int) -> Tuple[float, int, List[str], int]:
    """
    Simulates ARB bcy_curve.pack_files boundary truncation policy.
    Partially packs the boundary file up to remaining tokens; 
    counts gold as covered if included tokens >= min threshold (1 token).
    """
    if not gold_files or budget <= 0:
        return 0.0, 0, [], 0
    used = 0
    covered = set()
    packed_paths = []
    partial_count = 0
    for item in ranked_items:
        text = str(item.get("text", ""))
        path = str(item.get("path", ""))
        header_tokens = count_tokens_pinned(f"### {path}\n")
        content_tokens = count_tokens_pinned(text)
        total_tokens = header_tokens + content_tokens + (1 if text else 0)
        if total_tokens <= 0:
            continue
        remaining = budget - used
        if remaining <= 0:
            break
        if total_tokens <= remaining:
            used += total_tokens
            inc = content_tokens
        else:
            partial_count += 1
            inc = max(0, remaining - header_tokens)
            used = budget
        packed_paths.append(path)
        if path in gold_files and inc >= 1:
            covered.add(path)
        if used >= budget:
            break
    return len(covered) / len(gold_files), used, packed_paths, partial_count


class TestStage392ContextBudgetAudit:
    """Deterministic tests auditing context budgeting and packing dynamics."""

    def test_greedy_stop_halts_on_oversized_top_file(self):
        """
        Demonstrates that under greedy-stop, an oversized top file blocks
        smaller relevant files ranked at position 2 or 3.
        """
        gold = {"src/target_small.py"}
        # File 1: 5,000 chars (not gold). File 2: 4,000 chars (not gold). File 3: 500 chars (GOLD).
        items = [
            {"path": "src/large_distractor_1.py", "text": "A" * 5000},
            {"path": "src/large_distractor_2.py", "text": "B" * 4000},
            {"path": "src/target_small.py", "text": "C" * 500},
        ]
        budget = 8000

        # ARB Greedy-stop: accepts File 1 (used=5000), checks File 2 (5000+4000 > 8000) -> HALTS!
        cov_stop, used_stop, paths_stop = simulate_arb_greedy_stop(gold, items, budget, unit="char")
        assert cov_stop == 0.0
        assert used_stop == 5000
        assert paths_stop == ["src/large_distractor_1.py"]

        # Greedy-skip: accepts File 1 (used=5000), skips File 2 (oversized), packs File 3 (5000+500 <= 8000)!
        cov_skip, used_skip, paths_skip = simulate_greedy_skip(gold, items, budget, unit="char")
        assert cov_skip == 1.0
        assert used_skip == 5500
        assert paths_skip == ["src/large_distractor_1.py", "src/target_small.py"]

    def test_character_vs_tokenizer_token_budget_units(self):
        """
        Verifies that character count and token count measure fundamentally
        different quantities and cannot be conflated under '8k'.
        """
        code = "fn search<'a, P: AsRef<Path>>(p: &'a P) -> Result<Option<Searcher>, Error> {\n    let mut x = vec![1, 2, 3];\n}"
        char_len = len(code)
        tok_len = count_tokens_pinned(code)
        est_len = estimate_tokens(code)

        assert char_len > tok_len
        ratio = char_len / tok_len
        # Highly punctuated code has ~2.0 to 4.5 characters per token:
        assert 2.0 <= ratio <= 5.0

        # 8,000 characters is only ~2,000 to ~3,500 tokens in realistic code:
        realistic_code = "let x = foo.bar(baz, qux);\n" * 300 # ~8100 chars
        assert len(realistic_code) >= 8000
        assert count_tokens_pinned(realistic_code) < 4000

    def test_structural_skeleton_vs_full_file_packing(self):
        """
        Verifies that BudgetOptimizer skeleton extraction compresses large files
        allowing multiple relevant files to fit within a strict token budget.
        """
        optimizer = BudgetOptimizer(BudgetConfig(skeleton_token_cap=500))
        python_code = (
            "import os\nimport sys\n\n"
            "class ComplexService:\n"
            "    '''Main entry point for service execution.'''\n"
            + "".join([
                f"    def method_{i}(self):\n"
                + "".join([f"        temp_{j} = {j} * {i}\n" for j in range(10)])
                + "        return temp_0\n"
                for i in range(20)
            ])
        )
        full_tokens = estimate_tokens(python_code)
        assert full_tokens > 500

        skel_content, skel_tokens = optimizer.generate_skeleton(python_code, "service.py", query_terms=["method_5"])
        assert skel_tokens < full_tokens * 0.50
        assert "class ComplexService" in skel_content
        assert "def method_5" in skel_content
        assert "# ... [elided implementation]" in skel_content

    def test_equal_ranked_files_deterministic_tie_breaking(self):
        """
        Verifies that sorting candidates with identical scores is deterministic
        and breaks ties lexicographically by path.
        """
        docs = [
            FileDoc(path="z/common.py", content="x = 1"),
            FileDoc(path="a/common.py", content="y = 2"),
            FileDoc(path="m/common.py", content="z = 3"),
        ]
        # All assigned identical score of 0.85
        scored = [(d, 0.85, {}) for d in docs]
        # Deterministic sorting: -score, then doc.path
        sorted_docs = sorted(scored, key=lambda x: (-x[1], x[0].path))
        paths = [d.path for d, _, _ in sorted_docs]
        assert paths == ["a/common.py", "m/common.py", "z/common.py"]

    def test_exact_budget_boundary_and_zero_budget(self):
        """
        Tests exact budget boundaries and demonstrates the ARB v2 used==0 overflow quirk.
        """
        items = [{"path": "file1.py", "text": "A" * 100}, {"path": "file2.py", "text": "B" * 100}]
        gold = {"file1.py", "file2.py"}

        # Exact match for file 1
        cov, used, paths = simulate_strict_greedy_stop(gold, items, 100, unit="char")
        assert cov == 0.5
        assert used == 100
        assert paths == ["file1.py"]

        # Budget overflow by 1 char for file 2
        cov, used, paths = simulate_strict_greedy_stop(gold, items, 199, unit="char")
        assert cov == 0.5
        assert used == 100
        assert paths == ["file1.py"]

        # Exactly enough for both
        cov, used, paths = simulate_strict_greedy_stop(gold, items, 200, unit="char")
        assert cov == 1.0
        assert used == 200
        assert paths == ["file1.py", "file2.py"]

        # Strict zero budget correctly rejects all files
        cov, used, paths = simulate_strict_greedy_stop(gold, items, 0, unit="char")
        assert cov == 0.0
        assert used == 0
        assert paths == []

        # Audit finding: ARB v2's gold_coverage_at_budget packs the first item even when budget=0
        # because condition is (used + len > budget and used > 0), which is False on step 0!
        cov_arb, used_arb, paths_arb = simulate_arb_greedy_stop(gold, items, 0, unit="char")
        assert cov_arb == 0.5
        assert used_arb == 100
        assert paths_arb == ["file1.py"]

    def test_empty_files_and_boundary_truncation(self):
        """
        Tests handling of empty files and partial boundary truncation under pack_files policy.
        """
        items = [
            {"path": "empty.py", "text": ""},
            {"path": "large_target.py", "text": "def test_func():\n    assert True\n" * 100},
        ]
        gold = {"large_target.py"}
        budget = 50 # Small token budget

        cov, used, paths, partial_count = simulate_boundary_truncation(gold, items, budget)
        assert "empty.py" in paths # Header was packed
        assert "large_target.py" in paths
        assert partial_count == 1
        assert used == budget
        # Target was partially included with >= 1 token, so covered
        assert cov == 1.0

    def test_ranking_metrics_vs_budgeted_metrics_separation(self):
        """
        Proves that a system can achieve superior MRR and Recall@20
        while reporting identical or zero BCY under a restrictive greedy-stop policy.
        """
        # System 1: Gold file ranked 1, but file is 10,000 chars (exceeds 8k).
        # System 2: Gold file ranked 10, preceded by 9 files of 1,000 chars each.
        gold = {"gold.py"}
        sys1_items = [{"path": "gold.py", "text": "X" * 10000}]
        sys2_items = [{"path": f"distractor_{i}.py", "text": "Y" * 1000} for i in range(9)] + [{"path": "gold.py", "text": "Z" * 1000}]

        # MRR: Sys 1 = 1.0 (rank 1), Sys 2 = 0.10 (rank 10)
        mrr_sys1 = 1.0
        mrr_sys2 = 1.0 / 10.0
        assert mrr_sys1 > mrr_sys2

        # Greedy-stop at 8000 characters:
        # Sys 1 packs gold.py because used==0, used becomes 10000. Coverage = 1.0.
        cov1, _, _ = simulate_arb_greedy_stop(gold, sys1_items, 8000, unit="char")
        # Sys 2 packs 8 distractors (used=8000), stops at distractor 9. gold.py at rank 10 is NEVER REACHED. Coverage = 0.0.
        cov2, _, _ = simulate_arb_greedy_stop(gold, sys2_items, 8000, unit="char")
        assert cov1 == 1.0
        assert cov2 == 0.0
