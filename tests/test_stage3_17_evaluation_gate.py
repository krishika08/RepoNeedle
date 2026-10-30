"""
Test Suite for RepoNeedle Stage 3.17 — Frozen Official ContextBench Evaluation Gate.

Verifies:
1. Baseline git tags remain immutable.
2. Production code under reponeedle/ remains completely untouched.
3. Stage 3.17 research artifacts exist and satisfy schema contracts.
4. Official intake validator fails closed with exit code 2 when datasets are missing.
5. Validator helper routines (subset integrity, checksums, size checks) are correct.
6. Formal governance decision is recorded as BLOCKED — DATA ACQUISITION OR VALIDATION FAILED.
7. Candidate F invalidation and ARM-101 champion status are consistently recorded.
"""

import sys
import subprocess
import json
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

STAGE3_17_DIR = ROOT_DIR / "research" / "stage3_17"
CONTEXTBENCH_DATA_DIR = ROOT_DIR / "research" / "external_data" / "contextbench"


def test_baseline_tags_immutable():
    """Verify frozen baseline git tags point to immutable commits."""
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


def test_production_code_untouched():
    """Verify zero modifications to production code under reponeedle/."""
    r = subprocess.run(
        ["git", "diff", "--name-only", "548dab5eea6c71c3e9982676289098d9e0dca5f0", "--", "reponeedle/"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True
    )
    assert r.stdout.strip() == "", f"Production code modified: {r.stdout.strip()}"


def test_stage3_17_deliverables_exist():
    """Verify all Stage 3.17 research artifacts exist and are non-empty."""
    required_files = [
        "STAGE3_17_REPORT.md",
        "DATASET_VALIDATION_REPORT.md",
        "EVALUATION_CONFIGURATIONS.md",
        "EXPERIMENT_REGISTRY.jsonl",
        "REPRODUCE.md",
        "DECISION_REPORT.md",
        "dataset_manifest.json",
        "evaluation_manifest.json",
    ]
    for fname in required_files:
        fpath = STAGE3_17_DIR / fname
        assert fpath.exists(), f"Missing required file: {fname}"
        assert fpath.stat().st_size > 0, f"File is empty: {fname}"


def test_stage3_17_manifest_schemas():
    """Verify dataset and evaluation manifests load with valid JSON and required keys."""
    # Dataset manifest
    ds_path = STAGE3_17_DIR / "dataset_manifest.json"
    with open(ds_path, "r", encoding="utf-8") as f:
        ds_manifest = json.load(f)

    assert ds_manifest["pinned_upstream_revision"] == "c285579"
    assert ds_manifest["configurations"]["default"]["expected_rows"] == 1136
    assert ds_manifest["configurations"]["default"]["expected_sha256"] == "2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8"
    assert ds_manifest["configurations"]["default"]["expected_bytes"] == 26102607
    assert ds_manifest["configurations"]["contextbench_verified"]["expected_rows"] == 500
    assert ds_manifest["configurations"]["contextbench_verified"]["expected_sha256"] == "e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791"
    assert ds_manifest["configurations"]["contextbench_verified"]["expected_bytes"] == 9558250
    assert ds_manifest["acquisition_status"] == "BLOCKED — DATA ACQUISITION OR VALIDATION FAILED"

    # Evaluation manifest
    eval_path = STAGE3_17_DIR / "evaluation_manifest.json"
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_manifest = json.load(f)

    assert eval_manifest["evaluation_gate_verdict"] == "BLOCKED — DATA ACQUISITION OR VALIDATION FAILED"
    configs = {c["system_id"]: c for c in eval_manifest["preregistered_configurations"]}
    assert "ARM-101-BASE" in configs
    assert "BASE-BM25" in configs
    assert "BASE-REPOMAP" in configs
    assert configs["ARM-101-BASE"]["status"] == "PREREGISTERED_CANDIDATE_CHAMPION"
    assert eval_manifest["candidate_naming_reconciliation"]["candidate_f_status"] == "FORMALLY_INVALIDATED"


def test_validator_fails_closed_on_missing_files():
    """Verify that validate_contextbench.py exits with code 2 when files are missing."""
    validator_script = CONTEXTBENCH_DATA_DIR / "validate_contextbench.py"
    r = subprocess.run(
        [sys.executable, str(validator_script)],
        capture_output=True,
        text=True
    )
    assert r.returncode == 2, f"Expected exit code 2, got {r.returncode}"
    assert "[STATUS: BLOCKED - DATA ACCESS]" in r.stdout
    assert "c285579" in r.stdout


def test_validator_subset_integrity_logic():
    """Verify that subset integrity validation correctly catches discrepancies."""
    from research.external_data.contextbench.validate_contextbench import verify_subset_integrity

    full_records = [{"instance_id": f"task_{i}"} for i in range(10)]
    verified_records = [{"instance_id": f"task_{i}"} for i in range(5)]
    ok, msg = verify_subset_integrity(full_records, verified_records)
    assert ok is True
    assert "strict subset" in msg

    # Invalid subset: extra task not in full
    invalid_verified = [{"instance_id": f"task_{i}"} for i in range(5)] + [{"instance_id": "alien_task"}]
    ok, msg = verify_subset_integrity(full_records, invalid_verified)
    assert ok is False
    assert "alien_task" in msg


def test_validator_checksum_and_size_logic(tmp_path):
    """Verify validate_file checks file existence, byte size, and SHA256 checksum."""
    from research.external_data.contextbench.validate_contextbench import validate_file

    non_existent = tmp_path / "missing.parquet"
    code, _ = validate_file(non_existent, expected_config="full")
    assert code == 2

    # Create dummy file with mismatch size
    dummy_file = tmp_path / "dummy.parquet"
    dummy_file.write_bytes(b"hello world")
    code, msg = validate_file(dummy_file, expected_config="full", expected_bytes=100)
    assert code == 3
    assert "Byte size mismatch" in msg

    # Checksum mismatch
    code, msg = validate_file(dummy_file, expected_config="full", expected_sha="deadbeef")
    assert code == 3
    assert "Checksum mismatch" in msg


def test_governance_verdict_blocked():
    """Verify governance decision across reports matches the required string."""
    decision_text = (STAGE3_17_DIR / "DECISION_REPORT.md").read_text(encoding="utf-8")
    assert "FINAL VERDICT: BLOCKED — DATA ACQUISITION OR VALIDATION FAILED" in decision_text

    stage_report_text = (STAGE3_17_DIR / "STAGE3_17_REPORT.md").read_text(encoding="utf-8")
    assert "GOVERNANCE VERDICT: BLOCKED — DATA ACQUISITION OR VALIDATION FAILED" in stage_report_text


def test_candidate_f_invalidation_recorded():
    """Verify Candidate F is recorded as invalidated and not used as champion."""
    config_text = (STAGE3_17_DIR / "EVALUATION_CONFIGURATIONS.md").read_text(encoding="utf-8")
    assert "Candidate F is Formally Invalidated" in config_text
    assert "0.1351" in config_text
    assert "ARM-101-BASE" in config_text
