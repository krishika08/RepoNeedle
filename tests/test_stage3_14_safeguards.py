"""
Stage 3.14 Safeguard Tests: Evidence Integrity, Historical Errata, and Independent Validation Gate.
"""

import sys
import os
import csv
import json
import subprocess
from pathlib import Path
import pytest
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_14"


def test_frozen_tags_immutability():
    """Verify frozen tags remain completely untouched."""
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


def test_historical_errata_banners():
    """Verify that historical Stage 3.5 reports have prominent warning notices."""
    stage35_dir = ROOT_DIR / "research" / "stage3_5"
    reports_to_check = [
        stage35_dir / "STAGE3_5_DECISION_REPORT.md",
        stage35_dir / "BASELINE_REPRODUCTION.md",
        stage35_dir / "FAILURE_ANALYSIS.md",
        stage35_dir / "REPRODUCE.md",
    ]
    for path in reports_to_check:
        assert path.exists(), f"Missing historical report {path}"
        content = path.read_text(encoding="utf-8")
        assert "HISTORICAL AUDIT NOTICE" in content, f"Missing historical audit notice in {path}"
        assert "INVALIDATED" in content or "SUPERSEDED" in content, f"Missing invalidation notice in {path}"
        assert "CANONICAL_LINEAGE_AUDIT.md" in content, f"Missing link to canonical audit in {path}"


def test_errata_ledger_exists_and_covers_artifacts():
    """Verify HISTORICAL_ERRATA.md exists and catalogs all errata."""
    errata_md = STAGE_DIR / "HISTORICAL_ERRATA.md"
    assert errata_md.exists(), "Missing HISTORICAL_ERRATA.md"
    content = errata_md.read_text(encoding="utf-8")
    assert "ERR-305-01" in content
    assert "FORMALLY_INVALIDATED" in content
    assert "0.2152" in content
    assert "0.1334" in content
    assert "0.2293" in content


def test_runtime_memory_reconciliation_csv():
    """Verify RUNTIME_MEMORY_RECONCILIATION.csv documents file count and snapshot differences."""
    mem_csv = STAGE_DIR / "RUNTIME_MEMORY_RECONCILIATION.csv"
    assert mem_csv.exists(), "Missing RUNTIME_MEMORY_RECONCILIATION.csv"
    rows = list(csv.DictReader(open(mem_csv, encoding="utf-8")))
    assert len(rows) >= 5

    # Check Click and Caddy entries
    caddy_rows = [r for r in rows if "caddy" in r["repository"]]
    click_rows = [r for r in rows if "click" in r["repository"]]
    assert len(caddy_rows) >= 2
    assert len(click_rows) >= 2

    # Check Stage 3.5 vs canonical file counts
    s35_caddy = next(r for r in caddy_rows if r["stage"] == "Stage 3.5")
    s313_caddy = next(r for r in caddy_rows if r["stage"] == "Stage 3.13")
    assert int(s35_caddy["file_count_tested"]) == 250
    assert int(s313_caddy["file_count_tested"]) == 605
    assert s35_caddy["comparability_status"] == "NON_COMPARABLE_PARTIAL_SNAPSHOT"


def test_canonical_metrics_recomputation_exactness():
    """Verify that recomputed metrics match canonical figures within tight numerical tolerance."""
    recomp_csv = STAGE_DIR / "CANONICAL_REPRODUCTION_RESULTS.csv"
    assert recomp_csv.exists(), "Missing CANONICAL_REPRODUCTION_RESULTS.csv"
    rows = {r["system_id"]: r for r in csv.DictReader(open(recomp_csv, encoding="utf-8"))}

    # Verify CONFIG-09
    assert "CONFIG-09" in rows
    c09 = rows["CONFIG-09"]
    assert pytest.approx(float(c09["mrr"]), abs=1e-4) == 0.2061
    assert pytest.approx(float(c09["recall_at_20"]), abs=1e-4) == 0.5576
    assert pytest.approx(float(c09["token_bcy_at_8k"]), abs=1e-4) == 0.2729

    # Verify CONFIG-10
    assert "CONFIG-10" in rows
    c10 = rows["CONFIG-10"]
    assert pytest.approx(float(c10["mrr"]), abs=1e-4) == 0.2019
    assert pytest.approx(float(c10["recall_at_20"]), abs=1e-4) == 0.5494
    assert pytest.approx(float(c10["token_bcy_at_8k"]), abs=1e-4) == 0.2633

    # Verify BASE-REPOMAP
    assert "BASE-REPOMAP" in rows
    repomap = rows["BASE-REPOMAP"]
    assert pytest.approx(float(repomap["mrr"]), abs=1e-4) == 0.2293
    assert pytest.approx(float(repomap["recall_at_20"]), abs=1e-4) == 0.6599
    assert pytest.approx(float(repomap["token_bcy_at_8k"]), abs=1e-4) == 0.3177

    # Verify Candidate F collapse
    assert "CAND-F" in rows
    candf = rows["CAND-F"]
    assert float(candf["mrr"]) < 0.14  # 0.1334


def test_tost_equivalence_and_wilcoxon_safeguards():
    """Verify statistical rules: TOST bounds inside margin and Holm significance."""
    stat_audit = STAGE_DIR / "STATISTICAL_TEST_AUDIT.md"
    assert stat_audit.exists(), "Missing STATISTICAL_TEST_AUDIT.md"
    content = stat_audit.read_text(encoding="utf-8")
    assert "7.0440" in content
    assert "-12.5787" in content
    assert "5.12" in content or "5.1165" in content
    assert "proves statistical equivalence" in content.lower() or "proves equivalence" in content.lower()
    assert "1.58" in content or "1.5783" in content


def test_contextbench_fail_closed_validation(tmp_path):
    """Verify validate_contextbench.py fails closed on missing, wrong hash, or malformed schema."""
    script_path = STAGE_DIR / "validate_contextbench.py"
    assert script_path.exists(), "Missing validate_contextbench.py"

    # Test 1: Empty directory -> exit code 2 (BLOCKED)
    res_empty = subprocess.run(
        [sys.executable, str(script_path), "--data-dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert res_empty.returncode == 2, f"Expected 2 on empty dir, got {res_empty.returncode}"
    assert "BLOCKED BY EXTERNAL DATA ACCESS" in res_empty.stdout

    # Test 2: Malformed schema -> exit code 4 (INVALID SCHEMA)
    bad_file = tmp_path / "bad_contextbench.jsonl"
    bad_file.write_text('{"bad_key": 1}\n', encoding="utf-8")
    res_bad = subprocess.run(
        [sys.executable, str(script_path), "--data-dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert res_bad.returncode == 4, f"Expected 4 on bad schema, got {res_bad.returncode}"
    assert "Missing required field" in res_bad.stdout

    # Test 3: Checksum mismatch -> exit code 3 (INVALID HASH)
    valid_schema_file = tmp_path / "test.jsonl"
    valid_schema_file.write_text(
        json.dumps({
            "id": "cb-001",
            "repository": "test/repo",
            "base_commit": "abcdef",
            "query": "find bug",
            "gold_files": ["src/main.py"],
        }) + "\n",
        encoding="utf-8",
    )
    res_hash = subprocess.run(
        [sys.executable, str(script_path), "--data-dir", str(tmp_path), "--expected-sha256", "0000000000000000000000000000000000000000000000000000000000000000"],
        capture_output=True,
        text=True,
    )
    assert res_hash.returncode == 3, f"Expected 3 on hash mismatch, got {res_hash.returncode}"
    assert "Checksum mismatch" in res_hash.stdout
