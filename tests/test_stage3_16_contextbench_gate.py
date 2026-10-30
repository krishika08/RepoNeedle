"""
Automated Safeguard and Intake Integrity Tests for RepoNeedle Stage 3.16:
Official ContextBench Acquisition and Independent Validation Gate.
"""

import sys
import os
import json
import subprocess
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from research.contextbench_evaluation.leakage_guard import (
    LeakageGuard,
    DataLeakageSecurityException,
    FORBIDDEN_EVALUATION_FIELDS,
)
from research.contextbench_evaluation.adapter import (
    ContextBenchAdapter,
    FrozenConfigurationRegistry,
)
from research.contextbench_evaluation.evaluator import (
    evaluate_task_prediction,
    extract_gold_files,
)
from research.external_data.contextbench.validate_contextbench import (
    validate_contextbench_records,
    FULL_EXPECTED_ROWS,
    VERIFIED_EXPECTED_ROWS,
)


def test_frozen_baseline_tags_unmodified():
    """Verify immutable baseline tags point to their exact recorded commit SHAs."""
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


def test_stage3_16_deliverables_exist():
    """Verify all required deliverables exist and are non-empty."""
    s16_dir = ROOT_DIR / "research" / "stage3_16"
    ext_dir = ROOT_DIR / "research" / "external_data" / "contextbench"
    eval_dir = ROOT_DIR / "research" / "contextbench_evaluation"

    required_s16 = [
        "STAGE3_16_REPORT.md",
        "ACQUISITION_REPORT.md",
        "DATASET_INTEGRITY_REPORT.md",
        "EVALUATION_PROTOCOL.md",
        "METRIC_CONTRACT.md",
        "EXPERIMENT_REGISTRY.jsonl",
        "REPRODUCE.md",
        "DECISION_REPORT.md",
        "dataset_manifest.json",
        "evaluation_manifest.json",
    ]
    for filename in required_s16:
        filepath = s16_dir / filename
        assert filepath.exists(), f"Missing required file in stage3_16: {filename}"
        assert filepath.stat().st_size > 50, f"File unexpectedly small: {filename}"

    required_ext = [
        "README.md",
        "validate_contextbench.py",
        "dataset_manifest.json",
        "ACQUISITION_BLOCKER.md",
        ".gitignore",
    ]
    for filename in required_ext:
        filepath = ext_dir / filename
        assert filepath.exists(), f"Missing required file in external_data/contextbench: {filename}"

    required_eval = [
        "__init__.py",
        "leakage_guard.py",
        "adapter.py",
        "evaluator.py",
    ]
    for filename in required_eval:
        filepath = eval_dir / filename
        assert filepath.exists(), f"Missing required file in contextbench_evaluation: {filename}"


def test_leakage_guard_strictly_blocks_forbidden_fields():
    """Verify LeakageGuard raises DataLeakageSecurityException if any forbidden field is passed."""
    # Test 1: Query packet with gold_context
    packet_with_gold = {
        "instance_id": "test-task-1",
        "repo": "pallets/click",
        "base_commit": "abcdef",
        "problem_statement": "Fix Click param parser",
        "gold_context": ["src/click/core.py"],
    }
    # Sanitizer strips gold_context
    sanitized = LeakageGuard.inspect_and_sanitize(packet_with_gold)
    assert "gold_context" not in sanitized
    assert "problem_statement" in sanitized

    # Direct assertion failure on engine call
    with pytest.raises(DataLeakageSecurityException):
        LeakageGuard.assert_no_leakage_in_engine_call(packet_with_gold)

    # Test all forbidden fields
    for field in FORBIDDEN_EVALUATION_FIELDS:
        bad_meta = {"instance_id": "bad-task", field: "forbidden_payload"}
        with pytest.raises(DataLeakageSecurityException):
            LeakageGuard.assert_no_leakage_in_engine_call(bad_meta)


def test_validator_fails_closed_on_missing_dir(tmp_path):
    """Verify validator returns exit code 2 when data directory is missing or empty."""
    validator_path = ROOT_DIR / "research" / "external_data" / "contextbench" / "validate_contextbench.py"
    empty_dir = tmp_path / "nonexistent"

    res = subprocess.run(
        [sys.executable, str(validator_path), "--data-dir", str(empty_dir)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 2
    assert "BLOCKED - DATA ACCESS" in res.stdout


def test_validator_fails_closed_on_invalid_schema_and_counts():
    """Verify validation logic detects row count mismatch and schema issues."""
    # Subtest A: Empty records
    valid, msg = validate_contextbench_records([])
    assert not valid
    assert "0 rows" in msg

    # Subtest B: Row count mismatch on full configuration
    fake_records = [
        {
            "instance_id": f"task-{i}",
            "repo": "test/repo",
            "base_commit": "123456",
            "problem_statement": "Fix issue",
            "gold_context": ["main.py"],
        }
        for i in range(10)
    ]
    valid, msg = validate_contextbench_records(fake_records, expected_config="full")
    assert not valid
    assert "Full dataset row count mismatch" in msg

    # Subtest C: Missing required column
    bad_col_record = [
        {
            "instance_id": "task-1",
            "repo": "test/repo",
            "base_commit": "123456",
            # missing problem_statement
            "gold_context": ["main.py"],
        }
    ]
    valid, msg = validate_contextbench_records(bad_col_record, expected_config=None)
    assert not valid
    assert "missing required column 'problem_statement'" in msg

    # Subtest D: Empty gold context
    empty_gold_record = [
        {
            "instance_id": "task-1",
            "repo": "test/repo",
            "base_commit": "123456",
            "problem_statement": "Fix issue",
            "gold_context": [],
        }
    ]
    valid, msg = validate_contextbench_records(empty_gold_record, expected_config=None)
    assert not valid
    assert "empty gold_context" in msg


def test_adapter_denominator_preservation_on_checkout_failure():
    """Verify adapter records checkout failures as ERROR_CHECKOUT_FAILED with empty predictions."""
    adapter = ContextBenchAdapter(config_name="ARM-101-BASE")
    instance = {
        "instance_id": "cb-checkout-fail-001",
        "repo": "nonexistent/repo",
        "base_commit": "00000000",
        "problem_statement": "Fix race condition in threadpool",
    }
    # Pass None for file_docs to simulate missing repository clone/checkout
    result = adapter.run_task(instance, file_docs=None)
    assert result["status"] == "ERROR_CHECKOUT_FAILED"
    assert result["ranked_files"] == []
    assert result["instance_id"] == "cb-checkout-fail-001"

    # Evaluator handles failed prediction gracefully (yielding 0.0 scores without dropping from denominator)
    metrics = evaluate_task_prediction(
        gold_files=["src/threadpool.py"],
        ranked_files=result["ranked_files"],
    )
    assert metrics["mrr"] == 0.0
    assert metrics["recall_at_20"] == 0.0
    assert metrics["hit_at_20"] == 0.0


def test_decision_report_verdict():
    """Verify DECISION_REPORT.md records BLOCKED - EXTERNAL DATA ACQUISITION REQUIRED."""
    report_path = ROOT_DIR / "research" / "stage3_16" / "DECISION_REPORT.md"
    content = report_path.read_text(encoding="utf-8")
    assert "BLOCKED — EXTERNAL DATA ACQUISITION REQUIRED" in content or "BLOCKED - EXTERNAL DATA ACQUISITION REQUIRED" in content
    assert "ARM-101-BASE" in content
    assert "0.2078" in content


def test_production_code_untouched():
    """Verify production code under reponeedle/ has not been modified."""
    res = subprocess.run(
        ["git", "status", "--porcelain", "reponeedle/"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert res.stdout.strip() == "", f"Production code in reponeedle/ was modified: {res.stdout}"
