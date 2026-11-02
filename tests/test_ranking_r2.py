"""
Automated unit and integration tests for Phase R2 ranking behavior.
Tests SFS seed extraction & intent guard, TIP test-role detection & asymmetric boost,
and SMS stem & directory symmetry scoring.
"""
import os
import sys
import pytest

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "research", "v1_accuracy", "ranking_0_80", "r2", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from seed_suppression import (
    SeedExtractor,
    SeedSuppressor,
    normalize_path,
)
from test_intent import (
    TestIntentClassifier,
    TestIntentPrior,
    is_test_candidate,
)
from stem_symmetry import (
    StemDirectorySymmetry,
    StemSymmetryReranker,
    extract_stem,
)
from ranker_r2 import R2Ranker, TREATMENTS

def test_normalize_path():
    assert normalize_path("./src/foo/bar.py") == "src/foo/bar.py"
    assert normalize_path("src\\foo\\bar.py") == "src/foo/bar.py"
    assert normalize_path("/src/foo/bar.py") == "src/foo/bar.py"

def test_seed_extractor_json():
    query_json = '{"changed_file": "src/core/parser.rs", "pr_body": "fix parser", "pr_title": "Fix"}'
    seeds = SeedExtractor.extract_seeds(query_json)
    assert "src/core/parser.rs" in seeds
    assert SeedExtractor.determine_intent(query_json, seeds) == "relational"

def test_seed_extractor_diff():
    diff_text = '{"anchor_diff": "--- a/old.py\\n+++ b/pkg/new.py\\n@@ -1,3 +1,3 @@"}'
    seeds = SeedExtractor.extract_seeds(diff_text)
    assert "pkg/new.py" in seeds or "old.py" in seeds
    assert SeedExtractor.determine_intent(diff_text, seeds) == "relational"

def test_seed_suppressor_preserves_candidate_pool():
    suppressor = SeedSuppressor(demotion_factor=0.01)
    cands = [
        {"path": "src/seed.py", "m1_score": 10.0, "m1_rank": 1},
        {"path": "src/target.py", "m1_score": 8.0, "m1_rank": 2},
    ]
    query = '{"changed_file": "src/seed.py", "pr_body": "add test for target"}'
    reordered, telem = suppressor.suppress(cands, query)
    
    # Target should now be rank 1
    assert reordered[0]["path"] == "src/target.py"
    assert reordered[1]["path"] == "src/seed.py"
    # Seed is preserved in candidate pool (not deleted)
    assert len(reordered) == 2
    assert reordered[1]["sfs_demoted"] is True

def test_test_candidate_detection():
    assert is_test_candidate("tests/test_client.py") is True
    assert is_test_candidate("pkg/cache/demux_test.go") is True
    assert is_test_candidate("clap_complete/tests/testsuite/engine.rs") is True
    assert is_test_candidate("src/test/java/com/app/AppTest.java") is True
    assert is_test_candidate("src/core/parser.rs") is False
    assert is_test_candidate("pkg/cache/cache.go") is False

def test_test_intent_classifier():
    c2t_query = '{"changed_file": "src/foo.py", "pr_body": "Please find tests for this feature", "pr_title": "feat: foo"}'
    assert TestIntentClassifier.classify(c2t_query) is True
    
    t2c_query = '{"command": "python app.py", "failure_excerpt": "Traceback in src/main.py line 20", "source_type": "local_test_reproduction"}'
    assert TestIntentClassifier.classify(t2c_query) is False

def test_test_intent_prior_boosting():
    tip = TestIntentPrior(boost_weight=1.5, threshold=0.5)
    cands = [
        {"path": "src/foo.py", "m1_score": 10.0, "m1_rank": 1},
        {"path": "tests/test_foo.py", "m1_score": 7.0, "m1_rank": 2},
    ]
    query = '{"changed_file": "src/foo.py", "pr_body": "add tests for foo"}'
    reordered, telem = tip.apply(cands, query)
    
    # Test candidate should be boosted
    assert reordered[0]["path"] == "tests/test_foo.py"
    assert reordered[0]["tip_boosted"] is True

def test_stem_symmetry_scoring():
    sim = StemDirectorySymmetry.compute_stem_similarity("src/foo.py", "tests/test_foo.py")
    assert sim == 1.0  # Exact match after stripping test_ prefix
    
    sim_go = StemDirectorySymmetry.compute_stem_similarity("cache/demux.go", "cache/demux_test.go")
    assert sim_go == 1.0  # Exact match after stripping _test
    
    score = StemDirectorySymmetry.compute_symmetry_score("cache/demux.go", "cache/demux_test.go")
    assert score >= 2.0

def test_r2_ranker_end_to_end():
    ranker = R2Ranker()
    cands = [
        {"path": "src/engine/complete.rs", "m1_score": 12.0, "m1_rank": 1},
        {"path": "src/engine/builder.rs", "m1_score": 8.0, "m1_rank": 2},
        {"path": "tests/testsuite/complete.rs", "m1_score": 5.0, "m1_rank": 3},
    ]
    query = '{"changed_file": "src/engine/complete.rs", "pr_body": "fix complete engine and add unit test"}'
    
    # Baseline Treatment A: complete.rs is rank 1
    res_a, _ = ranker.rank(cands, query, treatment="A")
    assert res_a[0]["path"] == "src/engine/complete.rs"
    
    # Treatment E (SFS + TIP): tests/testsuite/complete.rs should be rank 1
    res_e, _ = ranker.rank(cands, query, treatment="E")
    assert res_e[0]["path"] == "tests/testsuite/complete.rs"
    # Pool size invariant
    assert len(res_e) == 3
