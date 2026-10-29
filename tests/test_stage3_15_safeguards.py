"""
Stage 3.15 Safeguard Tests: ContextBench Acquisition, Ingestion Integrity, and Adapter Immobility.
"""

import sys
import os
import json
import subprocess
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_15"
sys.path.insert(0, str(ROOT_DIR))

from research.stage3_15.contextbench_adapter import (
    FrozenConfigurationRegistry,
    compute_instance_metrics,
    run_evaluation_adapter,
)
from research.stage3_15.validate_contextbench import (
    validate_contextbench_file,
    RECORDED_FULL_SHA256,
)


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


def test_missing_dataset_fails_closed(tmp_path):
    """Verify validate_contextbench.py exits with code 2 on empty or missing directory."""
    script_path = STAGE_DIR / "validate_contextbench.py"
    assert script_path.exists(), "Missing validate_contextbench.py"

    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    res = subprocess.run(
        [sys.executable, str(script_path), "--data-dir", str(empty_dir)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 2, f"Expected returncode 2, got {res.returncode}"
    assert "BLOCKED — DATA ACCESS" in res.stdout


def test_checksum_mismatch_fails_closed(tmp_path):
    """Verify validate_contextbench.py exits with code 3 on hash mismatch."""
    script_path = STAGE_DIR / "validate_contextbench.py"
    fake_file = tmp_path / "contextbench_fake.jsonl"
    fake_file.write_text(
        json.dumps({
            "id": "cb-test-1",
            "repository": "test/repo",
            "base_commit": "12345678",
            "query": "Fix memory leak in buffer pool",
            "gold_files": ["buffer/pool.go"],
        }) + "\n",
        encoding="utf-8",
    )

    res = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--data-dir",
            str(tmp_path),
            "--expected-sha256",
            "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 3, f"Expected returncode 3, got {res.returncode}"
    assert "Checksum mismatch" in res.stdout


def test_incorrect_schema_fails_closed(tmp_path):
    """Verify validate_contextbench_file returns exit code 4 on missing fields or empty gold files."""
    # Subtest A: Missing query field
    bad_schema = tmp_path / "bad_schema.jsonl"
    bad_schema.write_text(
        json.dumps({
            "id": "cb-test-2",
            "repository": "test/repo",
            "base_commit": "12345678",
            "gold_files": ["main.py"],
        }) + "\n",
        encoding="utf-8",
    )
    is_valid, msg, code = validate_contextbench_file(bad_schema)
    assert not is_valid
    assert code == 4
    assert "Missing required field 'query'" in msg

    # Subtest B: Empty gold_files list
    empty_gold = tmp_path / "empty_gold.jsonl"
    empty_gold.write_text(
        json.dumps({
            "id": "cb-test-3",
            "repository": "test/repo",
            "base_commit": "12345678",
            "query": "Find bug",
            "gold_files": [],
        }) + "\n",
        encoding="utf-8",
    )
    is_valid, msg, code = validate_contextbench_file(empty_gold)
    assert not is_valid
    assert code == 4
    assert "must be a non-empty list" in msg


def test_missing_task_predictions_surfaced():
    """Verify that empty or missing predictions are surfaced explicitly as failures (0.0)."""
    metrics = compute_instance_metrics(
        gold_files=["src/core.py"],
        ranked_paths=[],
    )
    assert metrics["status"] == "FAILED_EMPTY_PREDICTIONS"
    assert metrics["mrr"] == 0.0
    assert metrics["recall_at_20"] == 0.0
    assert metrics["precision_at_5"] == 0.0


def test_evaluator_adapter_freezes_configurations():
    """Verify that configuration factory enforces immutable, frozen parameters."""
    cfg01 = FrozenConfigurationRegistry.get_config_01()
    assert cfg01.enable_lexical is True
    assert cfg01.enable_semantic is False
    assert cfg01.enable_graph is False
    assert cfg01.enable_doc_filter is False

    cfg09 = FrozenConfigurationRegistry.get_config_09()
    assert cfg09.enable_lexical is True
    assert cfg09.enable_semantic is True
    assert cfg09.enable_doc_filter is True
    assert cfg09.doc_filter_penalty == 0.5
    assert cfg09.decouple_bm25_symbols is True
    assert cfg09.enable_graph_diffusion is False
    assert cfg09.enable_pagerank_fusion is False

    cfg10 = FrozenConfigurationRegistry.get_config_10()
    assert cfg10.candidate_pool_size == 50
    assert cfg10.doc_filter_penalty == 0.5
    assert cfg10.decouple_bm25_symbols is True


def test_acquisition_attempts_provenance_record():
    """Verify machine-readable ACQUISITION_ATTEMPTS.json exists and records HTTP 403."""
    json_path = STAGE_DIR / "ACQUISITION_ATTEMPTS.json"
    assert json_path.exists(), "Missing ACQUISITION_ATTEMPTS.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["stage"] == "3.15"
    assert len(data["attempted_routes"]) >= 4
    assert all(r["http_status"] == 403 for r in data["attempted_routes"])
    assert data["policy_compliance"]["verdict"] == "BLOCKED — DATA ACCESS"
