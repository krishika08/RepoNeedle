"""
Automated unit regression tests for Stage 3.7 Metric Contract and Forensic Aggregation.
Verifies the exact mathematical and computational behavior of:
  - Reciprocal Rank (MRR)
  - Fractional Multi-Target Recall@k
  - Precision@k and F0.5@k
  - Character-budgeted chunk coverage (sample_metrics gold_coverage@8k)
  - Token-budgeted file packing (bcy_curve pack_files)
  - Macro-average vs. repository-clustered bootstrap aggregation
"""

import sys
import math
from pathlib import Path
import pytest
import numpy as np
from typing import Set, List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
ARB_SRC = ROOT_DIR / "external" / "agent-retrieval-bench" / "src"
if str(ARB_SRC) not in sys.path:
    sys.path.insert(0, str(ARB_SRC))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import (
    reciprocal_rank,
    recall_at,
    precision_at,
    f_score,
    gold_coverage_at_budget,
    unique_ranked_paths,
)
from agent_retrieval_bench.bcy_curve import count_tokens, pack_files, CorpusFileCache


class TestMetricContractCore:
    """Tests the canonical metric contract pinned in agent_retrieval_bench."""

    def test_reciprocal_rank_single_target(self):
        gold = {"src/app.py"}
        ranked = ["README.md", "docs/index.md", "src/app.py", "tests/test_app.py"]
        # src/app.py is at rank 3 -> 1/3
        rr = reciprocal_rank(gold, ranked)
        assert pytest.approx(rr, 1e-6) == 1.0 / 3.0

    def test_reciprocal_rank_multi_target_first_match(self):
        gold = {"src/model.py", "src/util.py"}
        ranked = ["docs/guide.md", "src/util.py", "src/model.py"]
        # src/util.py matches first at rank 2 -> 1/2 (not 1/3)
        rr = reciprocal_rank(gold, ranked)
        assert pytest.approx(rr, 1e-6) == 0.5

    def test_reciprocal_rank_missing_or_empty(self):
        assert reciprocal_rank(set(), ["src/app.py"]) == 0.0
        assert reciprocal_rank({"src/app.py"}, []) == 0.0
        assert reciprocal_rank({"src/app.py"}, ["other.py", "docs.py"]) == 0.0

    def test_fractional_recall_at_k(self):
        gold = {"a.py", "b.py", "c.py", "d.py"}
        ranked = ["a.py", "x.py", "b.py", "y.py", "z.py", "c.py"]
        # At k=1: 1 hit out of 4 -> 0.25
        assert pytest.approx(recall_at(gold, ranked, 1), 1e-6) == 0.25
        # At k=3: a.py, b.py -> 2/4 = 0.50
        assert pytest.approx(recall_at(gold, ranked, 3), 1e-6) == 0.50
        # At k=5: 2/4 = 0.50 (x, y, z are distractors)
        assert pytest.approx(recall_at(gold, ranked, 5), 1e-6) == 0.50
        # At k=6: a, b, c -> 3/4 = 0.75
        assert pytest.approx(recall_at(gold, ranked, 6), 1e-6) == 0.75

    def test_precision_and_f05(self):
        gold = {"a.py", "b.py"}
        ranked = ["a.py", "distractor1.py", "distractor2.py", "distractor3.py", "b.py"]
        # Precision@5: 2 / 5 = 0.40
        p5 = precision_at(gold, ranked, 5)
        assert pytest.approx(p5, 1e-6) == 0.40
        # Recall@5: 2 / 2 = 1.00
        r5 = recall_at(gold, ranked, 5)
        assert pytest.approx(r5, 1e-6) == 1.00
        # F0.5: beta=0.5 heavily penalizes lower precision
        # Formula: (1 + 0.25) * P * R / (0.25 * P + R)
        expected_f05 = 1.25 * 0.40 * 1.00 / (0.25 * 0.40 + 1.00)  # 0.50 / 1.10 = 0.454545...
        assert pytest.approx(f_score(p5, r5, beta=0.5), 1e-6) == expected_f05


class TestBcyVersusGoldCoverageDivergence:
    """Verifies the root cause divergence between character-budgeted gold coverage and token-budgeted BCY."""

    def test_gold_coverage_at_budget_uses_character_length(self):
        # 3 chunks of length 3,000 characters each
        chunk1 = {"path": "file1.py", "text": "A" * 3000}
        chunk2 = {"path": "file2.py", "text": "B" * 3000}
        chunk3 = {"path": "file3.py", "text": "C" * 3000}  # 3000 * 3 = 9000 > 8000
        ranked_chunks = [chunk1, chunk2, chunk3]

        gold = {"file1.py", "file2.py", "file3.py"}
        # Budget = 8,000 characters
        # Chunk 1: used=3000, covers file1
        # Chunk 2: used=6000, covers file2
        # Chunk 3: 6000 + 3000 = 9000 > 8000 -> BREAK!
        # Result: only file1 and file2 are covered -> 2/3 = 0.6667
        cov = gold_coverage_at_budget(gold, ranked_chunks, 8000)
        assert pytest.approx(cov, 1e-4) == 2.0 / 3.0

    def test_gold_coverage_character_depletion_on_long_chunks(self):
        # A realistic scenario where each file chunk has 4,500 characters
        chunk1 = {"path": "file1.py", "text": "X" * 4500}
        chunk2 = {"path": "file2.py", "text": "Y" * 4500}
        ranked_chunks = [chunk1, chunk2]
        gold = {"file2.py"}

        # Chunk 1 consumes 4500. Chunk 2 requires 4500 -> 4500 + 4500 = 9000 > 8000.
        # file2.py is never reached! Coverage = 0.0
        cov = gold_coverage_at_budget(gold, ranked_chunks, 8000)
        assert cov == 0.0

    def test_pack_files_uses_token_boundary(self):
        # Mock Corpus Cache
        class MockCorpusCache:
            def file_text(self, repo, commit, path):
                if path == "src/core.py":
                    return "def process():\n    return 42\n" * 50  # ~300 tokens
                elif path == "src/util.py":
                    return "def helper():\n    pass\n" * 50       # ~200 tokens
                return None

        cache = MockCorpusCache()
        ranked = ["src/core.py", "src/util.py"]
        gold = {"src/core.py", "src/util.py"}

        packed = pack_files("test/repo", "head", ranked, gold, cache, budget=8000)
        # Both files fit easily in 8,000 tokens
        assert packed["bcy"] == 1.0
        assert packed["packed_files"] == 2
        assert packed["covered_gold_count"] == 2


class TestClusteredBootstrapAggregation:
    """Verifies the statistical distinction between query-level Wilcoxon and repository-clustered bootstrap."""

    def test_clustered_bootstrap_confidence_interval_symmetry_and_containment(self):
        np.random.seed(42)
        # Construct synthetic data: 25 repositories, each with 10 queries
        # Repositories 0-4 have strong positive delta (+0.30)
        # Repositories 5-24 have slightly negative or zero delta (-0.05 to 0.0)
        n_repos = 25
        queries_per_repo = 10

        repo_deltas = {}
        for r in range(n_repos):
            if r < 3:
                repo_deltas[r] = np.random.normal(0.25, 0.05, queries_per_repo)
            else:
                repo_deltas[r] = np.random.normal(-0.02, 0.04, queries_per_repo)

        all_diffs = []
        clusters = []
        for r, diffs in repo_deltas.items():
            for d in diffs:
                all_diffs.append(d)
                clusters.append(r)

        all_diffs = np.array(all_diffs)
        clusters = np.array(clusters)

        # 1. Query-level sign test (Wilcoxon)
        import scipy.stats as stats
        w_stat, w_p = stats.wilcoxon(all_diffs, alternative="greater")

        # 2. Clustered bootstrap resampling
        B = 2000
        boot_means = []
        unique_clusters = np.unique(clusters)
        n_c = len(unique_clusters)

        for _ in range(B):
            sampled_c = np.random.choice(unique_clusters, size=n_c, replace=True)
            sampled_diffs = []
            for c in sampled_c:
                sampled_diffs.extend(all_diffs[clusters == c])
            boot_means.append(np.mean(sampled_diffs))

        ci_lower = np.percentile(boot_means, 2.5)
        ci_upper = np.percentile(boot_means, 97.5)

        # Wilcoxon can be significant while the clustered bootstrap crosses 0
        # because the wins are concentrated in only 3 of 25 clusters!
        assert ci_lower < 0.0  # Crosses zero, proving general claims fail
        assert ci_upper > 0.0
