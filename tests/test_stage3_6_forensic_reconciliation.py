"""
Stage 3.6 Forensic Reconciliation and Candidate F Validation Tests.
Asserts commit ancestry, tag immutability, metric discrepancy reconciliation, and Stage 3.15 safeguard preservation.
"""

import sys
import os
import csv
import json
import subprocess
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_6"
sys.path.insert(0, str(ROOT_DIR))

from reponeedle.models import AblationConfig
from research.stage3_15.contextbench_adapter import FrozenConfigurationRegistry


def test_commit_ancestry_4f78cc3_to_29bb3b9():
    """Verify that Stage 3.5 commit 4f78cc3 is a direct ancestor of Stage 3.15 commit 29bb3b9."""
    res = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "4f78cc3", "29bb3b9"],
        capture_output=True,
        text=True,
        cwd=ROOT_DIR,
    )
    assert res.returncode == 0, "Stage 3.5 commit 4f78cc3 is not an ancestor of Stage 3.15 commit 29bb3b9"


def test_frozen_tags_immutability():
    """Verify baseline and candidate freeze tags are intact and unchanged."""
    res_b = subprocess.run(
        ["git", "cat-file", "-p", "v0.1.0-baseline"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert "8e00425" in res_b.stdout, f"v0.1.0-baseline moved: {res_b.stdout}"

    res_c = subprocess.run(
        ["git", "cat-file", "-p", "stage3-candidate-freeze"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert "cd7f3b0" in res_c.stdout, f"stage3-candidate-freeze moved: {res_c.stdout}"


def test_metric_discrepancy_reconciliation():
    """Verify that METRIC_DISCREPANCY_TABLE.csv exists and accounts for BM25 and RepoMap discrepancies."""
    disc_csv = STAGE_DIR / "METRIC_DISCREPANCY_TABLE.csv"
    assert disc_csv.exists(), "Missing METRIC_DISCREPANCY_TABLE.csv"
    rows = {r["metric"]: r for r in csv.DictReader(open(disc_csv, encoding="utf-8"))}

    # BM25 Recall@20: 0.4467 (chunk) vs 0.4928 (binary hit) vs 0.4549 (canonical)
    assert "BASE-BM25 Recall@20" in rows
    bm25 = rows["BASE-BM25 Recall@20"]
    assert bm25["stage_3_4_value"] == "0.4467"
    assert bm25["stage_3_5_value"] == "0.4928"
    assert bm25["stage_3_6_canonical"] == "0.4549"

    # RepoMap Recall@20: 0.6306 vs 0.5681 vs 0.6599
    assert "BASE-REPOMAP Recall@20" in rows
    rm = rows["BASE-REPOMAP Recall@20"]
    assert rm["stage_3_4_value"] == "0.6306"
    assert rm["stage_3_5_value"] == "0.5681"
    assert rm["stage_3_6_canonical"] == "0.6599"

    # Candidate C Recall@20: 0.5516 vs 0.5105
    assert "CAND-C Recall@20" in rows
    candc = rows["CAND-C Recall@20"]
    assert candc["stage_3_5_value"] == "0.5516"
    assert candc["stage_3_6_canonical"] == "0.5105"


def test_candidate_f_retraction_and_statistical_loss():
    """Verify paired statistics confirm Candidate F is not superior to Candidate C or RepoMap."""
    stat_csv = STAGE_DIR / "PAIRED_STATISTICAL_TESTS.csv"
    assert stat_csv.exists(), "Missing PAIRED_STATISTICAL_TESTS.csv"
    rows = list(csv.DictReader(open(stat_csv, encoding="utf-8")))

    # Candidate F vs Candidate C MRR must have non-significant p-value (p >= 0.05)
    f_vs_c_mrr = next(r for r in rows if r["comparison"] == "Candidate F vs. Candidate C" and r["metric"] == "MRR")
    assert float(f_vs_c_mrr["wilcoxon_p_value"]) >= 0.05
    assert float(f_vs_c_mrr["mean_difference"]) < 0.0  # -0.0048

    # Candidate F vs RepoMap MRR must be decisively negative and significant
    f_vs_rm_mrr = next(r for r in rows if r["comparison"] == "Candidate F vs. RepoMap" and r["metric"] == "MRR")
    assert float(f_vs_rm_mrr["wilcoxon_p_value"]) < 0.001
    assert float(f_vs_rm_mrr["mean_difference"]) <= -0.09


def test_stage3_15_safeguards_preserved():
    """Verify that Stage 3.15 independent validation adapter and fail-closed gates remain untouched."""
    s15_val = ROOT_DIR / "research" / "stage3_15" / "validate_contextbench.py"
    s15_adapt = ROOT_DIR / "research" / "stage3_15" / "contextbench_adapter.py"
    assert s15_val.exists(), "Stage 3.15 validate_contextbench.py was deleted or moved"
    assert s15_adapt.exists(), "Stage 3.15 contextbench_adapter.py was deleted or moved"

    # Configurations remain frozen
    cfg01 = FrozenConfigurationRegistry.get_config_01()
    cfg09 = FrozenConfigurationRegistry.get_config_09()
    cfg10 = FrozenConfigurationRegistry.get_config_10()
    assert cfg01.enable_lexical is True and cfg01.enable_semantic is False
    assert cfg09.doc_filter_penalty == 0.5 and cfg09.decouple_bm25_symbols is True
    assert cfg10.candidate_pool_size == 50


def test_candidate_f_separate_versioned_isolation():
    """Verify Candidate F is isolated in AblationConfig and Candidate C remains frozen."""
    cfg_f = AblationConfig.candidate_f()
    cfg_c = AblationConfig.candidate_c()
    assert cfg_f.enable_graph_diffusion is True
    assert cfg_f.enable_polyglot_symbols is True
    assert cfg_c.enable_graph_diffusion is False
