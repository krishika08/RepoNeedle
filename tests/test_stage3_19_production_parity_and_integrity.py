"""
Automated Safeguard and Audit Verification Test Suite for RepoNeedle Stage 3.19:
Production Parity, Independent Reproduction & Performance Integrity Audit.
"""

import sys
import csv
import json
import subprocess
from pathlib import Path
import numpy as np
from scipy.stats import wilcoxon
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

STAGE19_DIR = ROOT_DIR / "research" / "stage3_19"


def test_baseline_tags_immutable():
    """Verify frozen baseline tags point to their exact recorded commit SHAs."""
    r1 = subprocess.run(
        ["git", "rev-parse", "v0.1.0-baseline^{commit}"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    assert r1.stdout.strip() == "8e0042553a14b6e3c6cf5b35823c4da84181a8e9"

    r2 = subprocess.run(
        ["git", "rev-parse", "stage3-candidate-freeze^{commit}"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    assert r2.stdout.strip() == "cd7f3b01e28695f9a9357e0815069e0eae85baca"


def test_production_code_untouched_in_stage3_19():
    """Verify zero modifications to production code under reponeedle/ in Stage 3.19."""
    r = subprocess.run(
        ["git", "diff", "--name-only", "c688516f974ddf61e5b15f49f083aa412376e64c..89a3ef4cd5c6854884bf8e4578f45577636bbbc7", "--", "reponeedle/"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    assert r.stdout.strip() == "", f"Production code modified: {r.stdout.strip()}"


def test_stage3_19_deliverables_exist():
    """Verify all 17 required Stage 3.19 deliverables exist and are non-empty."""
    required_files = [
        "STAGE3_19_REPORT.md",
        "PRODUCTION_PARITY_AUDIT.md",
        "CLEAN_REPRODUCTION.md",
        "REPRODUCED_LEADERBOARD.csv",
        "PER_QUERY_RESULTS.csv",
        "REPRODUCTION_HASHES.csv",
        "LATENCY_METHODOLOGY.md",
        "LATENCY_RAW.csv",
        "LATENCY_SUMMARY.csv",
        "MEMORY_SCALABILITY_AUDIT.md",
        "MEMORY_SCALABILITY.csv",
        "STATISTICAL_AUDIT.md",
        "PAIRWISE_COMPARISONS.csv",
        "REPOSITORY_LEVEL_RESULTS.csv",
        "CLAIM_STATUS_REGISTER.csv",
        "STAGE3_19_DECISION_REPORT.md",
        "CONTEXTBENCH_IMPORT_AND_READINESS.md",
    ]
    for fname in required_files:
        fpath = STAGE19_DIR / fname
        assert fpath.exists(), f"Missing required file: {fname}"
        assert fpath.stat().st_size > 100, f"File is suspiciously small or empty: {fname}"


def test_production_parity_boundary():
    """Verify ARM-101 and FunctionGraphEngine were NOT integrated in reponeedle/ at Stage 3.19 (89a3ef4)."""
    r = subprocess.run(
        ["git", "grep", "FunctionGraphEngine", "89a3ef4cd5c6854884bf8e4578f45577636bbbc7", "--", "reponeedle/"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0, "FunctionGraphEngine was found in reponeedle at commit 89a3ef4" 

    # Verify they exist in research/
    pilot_path = ROOT_DIR / "research" / "stage3_14" / "pilot_attenuation.py"
    assert "soft_damping_tau" in pilot_path.read_text(encoding="utf-8")

    fg_path = ROOT_DIR / "research" / "stage3_11" / "function_graph_engine.py"
    assert "FunctionGraphEngine" in fg_path.read_text(encoding="utf-8")


def test_clean_reproduction_metric_integrity():
    """Verify PER_QUERY_RESULTS.csv has 345 queries matching reproduced leaderboard."""
    pq_path = STAGE19_DIR / "PER_QUERY_RESULTS.csv"
    with open(pq_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 345

    # Check ARM-101-BASE means
    arm_mrr = np.mean([float(r["ARM-101-BASE_mrr"]) for r in rows])
    arm_r20 = np.mean([float(r["ARM-101-BASE_r20"]) for r in rows])
    assert abs(arm_mrr - 0.2078) < 0.0005
    assert abs(arm_r20 - 0.5648) < 0.0005

    # Check BASE-BM25 means
    bm_mrr = np.mean([float(r["BASE-BM25_mrr"]) for r in rows])
    bm_r20 = np.mean([float(r["BASE-BM25_r20"]) for r in rows])
    assert abs(bm_mrr - 0.1752) < 0.0005
    assert abs(bm_r20 - 0.4535) < 0.0005

    # Check BASE-REPOMAP means
    rm_mrr = np.mean([float(r["BASE-REPOMAP_mrr"]) for r in rows])
    rm_r20 = np.mean([float(r["BASE-REPOMAP_r20"]) for r in rows])
    assert abs(rm_mrr - 0.2293) < 0.0005
    assert abs(rm_r20 - 0.6599) < 0.0005


def test_latency_audit_integrity():
    """Verify LATENCY_SUMMARY.csv documents the RepoMap static scalar and correct speedup."""
    lat_path = STAGE19_DIR / "LATENCY_SUMMARY.csv"
    with open(lat_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_sys = {r["system_id"]: r for r in rows}
    assert "BASE-REPOMAP" in by_sys
    assert "ARM-101-BASE" in by_sys
    assert "BASE-BM25" in by_sys

    # RepoMap anomaly verified
    rm = by_sys["BASE-REPOMAP"]
    assert rm["measurement_type"] == "STATIC_SCALAR_CONSTANT"
    assert rm["std_ms"] == "0.00"
    assert rm["p50_ms"] == "180.20"
    assert rm["p95_ms"] == "180.20"

    # ARM-101 timing verified
    arm = by_sys["ARM-101-BASE"]
    assert arm["measurement_type"] == "DYNAMIC_STOPWATCH"
    assert arm["mean_ms"] == "41.30"
    assert arm["p50_ms"] == "12.92"
    assert arm["p95_ms"] == "130.53"
    assert arm["speedup_vs_repomap_mean"] == "4.36x"


def test_memory_scalability_audit_integrity():
    """Verify MEMORY_SCALABILITY.csv reports unconstrained working set over 100 MB."""
    mem_path = STAGE19_DIR / "MEMORY_SCALABILITY.csv"
    with open(mem_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_repo = {r["repository"]: r for r in rows}
    assert "caddyserver/caddy" in by_repo
    assert "etcd-io/etcd" in by_repo

    caddy = by_repo["caddyserver/caddy"]
    assert float(caddy["file_count"]) == 605
    assert float(caddy["rss_after_indexing_mb"]) == 198.0
    assert float(caddy["peak_process_rss_mb"]) == 272.8
    assert float(caddy["retained_index_heap_mb"]) < 25.0

    etcd = by_repo["etcd-io/etcd"]
    assert float(etcd["file_count"]) == 1431
    assert float(etcd["rss_after_indexing_mb"]) == 364.1
    assert float(etcd["peak_process_rss_mb"]) == 609.2


def test_statistical_audit_and_finite_sample_bound():
    """Verify PAIRWISE_COMPARISONS.csv reports finite sample bounds and disproves equivalence."""
    pair_path = STAGE19_DIR / "PAIRWISE_COMPARISONS.csv"
    with open(pair_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_pair = {r["comparison"]: r for r in rows}

    # ARM-101 vs BM25: finite-sample bound p < 0.0001
    arm_bm = by_pair["ARM-101-BASE vs BASE-BM25"]
    assert arm_bm["cluster_bootstrap_p_value"] == "p < 0.0001"
    assert float(arm_bm["cluster_ci_95_lower"]) > 0.02
    assert arm_bm["statistical_conclusion"] == "SIGNIFICANT_SUPERIORITY"

    # ARM-101 vs RepoMap: inconclusive, CI spans zero
    arm_rm = by_pair["ARM-101-BASE vs BASE-REPOMAP"]
    assert float(arm_rm["cluster_ci_95_lower"]) < -0.05
    assert float(arm_rm["cluster_ci_95_upper"]) > 0.01
    assert arm_rm["statistical_conclusion"] == "INCONCLUSIVE_NOT_SIGNIFICANT"


def test_claim_status_register():
    """Verify CLAIM_STATUS_REGISTER.csv marks invalidated and superseded claims."""
    reg_path = STAGE19_DIR / "CLAIM_STATUS_REGISTER.csv"
    with open(reg_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_id = {r["claim_id"]: r for r in rows}
    assert by_id["CLM-001"]["authoritative_status"] == "FORMALLY_INVALIDATED"  # Cand F
    assert by_id["CLM-002"]["authoritative_status"] == "SUPERSEDED_NON_CANONICAL"  # Cand C
    assert by_id["CLM-003"]["authoritative_status"] == "SUPERSEDED_HARDCODED_CONSTANT"  # RepoMap 0.2140
    assert by_id["CLM-004"]["authoritative_status"] == "FORMALLY_INVALIDATED"  # Universal 100 MB RSS
    assert by_id["CLM-005"]["authoritative_status"] == "FORMALLY_INVALIDATED"  # ARB v2 generalization
    assert by_id["CLM-006"]["authoritative_status"] == "FORMALLY_INVALIDATED"  # Equivalence fallacy
    assert by_id["CLM-007"]["authoritative_status"] == "SUPERSEDED_ASYMMETRIC_COMPARISON"  # 13.9x latency
    assert by_id["CLM-008"]["authoritative_status"] == "SUPERSEDED_UNINTEGRATED_PROTOTYPE"  # ARM-101 production status


def test_formal_verdicts_and_contextbench_gate():
    """Verify exact formal decision strings in reports."""
    dec_text = (STAGE19_DIR / "STAGE3_19_DECISION_REPORT.md").read_text(encoding="utf-8")
    assert "B. INTERNALLY REPRODUCIBLE BUT NOT PRODUCTION-INTEGRATED" in dec_text

    rep_text = (STAGE19_DIR / "STAGE3_19_REPORT.md").read_text(encoding="utf-8")
    assert "B. INTERNALLY REPRODUCIBLE BUT NOT PRODUCTION-INTEGRATED" in rep_text
    assert "BLOCKED — OFFICIAL DATA ACQUISITION" in rep_text

    cb_text = (STAGE19_DIR / "CONTEXTBENCH_IMPORT_AND_READINESS.md").read_text(encoding="utf-8")
    assert "BLOCKED — OFFICIAL DATA ACQUISITION" in cb_text
