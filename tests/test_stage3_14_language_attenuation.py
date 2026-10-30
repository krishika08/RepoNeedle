"""
Unit and safeguard tests for RepoNeedle Stage 3.14:
Language-Aware Hub Attenuation and Generalization-Safe Validation.
"""

import csv
import json
import subprocess
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_14"


def test_frozen_baseline_tags_unmodified():
    """Verify that immutable tags point to their exact documented commit SHAs."""
    res_b = subprocess.run(
        ["git", "rev-parse", "v0.1.0-baseline^{commit}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert res_b.stdout.strip() == "8e0042553a14b6e3c6cf5b35823c4da84181a8e9"

    res_c = subprocess.run(
        ["git", "rev-parse", "stage3-candidate-freeze^{commit}"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert res_c.stdout.strip() == "cd7f3b01e28695f9a9357e0815069e0eae85baca"


def test_stage3_14_deliverables_exist():
    """Verify all 11 required Stage 3.14 deliverables exist and are non-empty."""
    required_files = [
        "STAGE3_14_REPORT.md",
        "HYPOTHESES.md",
        "EXPERIMENT_REGISTRY.jsonl",
        "PER_QUERY_RESULTS.csv",
        "PER_REPOSITORY_RESULTS.csv",
        "PER_LANGUAGE_RESULTS.csv",
        "STATISTICAL_ANALYSIS.json",
        "RUNTIME_AND_MEMORY.csv",
        "FAILURE_ANALYSIS.md",
        "DECISION_REPORT.md",
        "REPRODUCE.md",
    ]
    for filename in required_files:
        filepath = STAGE_DIR / filename
        assert filepath.exists(), f"Missing required deliverable: {filename}"
        assert filepath.stat().st_size > 100, f"Deliverable is suspiciously small: {filename}"


def test_per_query_results_schema_and_counts():
    """Verify PER_QUERY_RESULTS.csv contains exactly 345 queries with all 9 evaluated systems."""
    csv_path = STAGE_DIR / "PER_QUERY_RESULTS.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) == 345, f"Expected 345 queries, got {len(reader)}"

    expected_systems = [
        "BASE-BM25",
        "CONTROL-CASCADE",
        "ARM-101-BASE",
        "ARM-111-UNIFORM",
        "LANG-CALIBRATED",
        "STRUCTURAL-ROLE",
        "COMBINED-LANG-ROLE",
        "DEGREE-THRESHOLD-15",
        "BASE-REPOMAP",
    ]
    for row in reader:
        assert "query_id" in row
        assert "repository" in row
        assert "language" in row
        for sys_id in expected_systems:
            assert f"{sys_id}_mrr" in row
            rr = float(row[f"{sys_id}_mrr"])
            assert 0.0 <= rr <= 1.0


def test_statistical_analysis_results():
    """Verify the statistical analysis confirms absence of improvement over ARM-101-BASE."""
    json_path = STAGE_DIR / "STATISTICAL_ANALYSIS.json"
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    comps = data["comparisons_vs_arm101_base"]

    # Verify ARM-111 degradation
    assert comps["ARM-111-UNIFORM"]["significant_at_05"] is True
    assert comps["ARM-111-UNIFORM"]["mean_delta_mrr"] < 0
    assert comps["ARM-111-UNIFORM"]["holm_adjusted_p_value"] < 0.05

    # Verify no attenuation variant improves upon ARM-101-BASE
    for sys_id in ["LANG-CALIBRATED", "STRUCTURAL-ROLE", "COMBINED-LANG-ROLE", "DEGREE-THRESHOLD-15"]:
        assert comps[sys_id]["mean_delta_mrr"] <= 0.0001
        assert comps[sys_id]["holm_adjusted_p_value"] > 0.05


def test_decision_report_verdict():
    """Verify DECISION_REPORT.md records the formal verdict NO ROBUST IMPROVEMENT."""
    report_path = STAGE_DIR / "DECISION_REPORT.md"
    content = report_path.read_text(encoding="utf-8")
    assert "[NO ROBUST IMPROVEMENT]" in content
    assert "ARM-101" in content
    assert "reponeedle/" in content


def test_production_code_untouched():
    """Ensure no production code in reponeedle/ has been modified."""
    res = subprocess.run(
        ["git", "diff", "--name-only", "8218812..12142e8", "--", "reponeedle/"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert res.stdout.strip() == "", f"Production files were modified: {res.stdout}"
