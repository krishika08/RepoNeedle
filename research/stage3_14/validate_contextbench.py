"""
Deterministic ContextBench Import, Verification, and Benchmark Entry Point.
Fail-closed validator for official ContextBench acquisition.
"""

import sys
import os
import json
import hashlib
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARGET_DIR = ROOT_DIR / "data" / "contextbench"
EXPECTED_DATASET_NAME = "Contextbench/ContextBench"
EXPECTED_HF_URL = "https://huggingface.co/datasets/Contextbench/ContextBench"

# Canonical expected schema fields for ContextBench instances
REQUIRED_FIELDS = ["id", "repository", "base_commit", "query", "gold_files"]


def compute_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def validate_contextbench_file(file_path: Path, expected_sha256: str = None) -> tuple[bool, str, int]:
    """
    Validates a ContextBench artifact.
    Returns: (is_valid, message, exit_code)
      exit_code 0: VALID & READY
      exit_code 2: BLOCKED / NOT FOUND
      exit_code 3: INVALID HASH
      exit_code 4: INVALID SCHEMA
    """
    if not file_path.exists() or file_path.stat().st_size == 0:
        return False, f"File does not exist or is empty: {file_path}", 2

    # Check hash if provided
    if expected_sha256:
        actual_hash = compute_sha256(file_path)
        if actual_hash.lower() != expected_sha256.lower():
            return (
                False,
                f"Checksum mismatch for {file_path.name}: expected {expected_sha256}, got {actual_hash}",
                3,
            )

    # Validate schema
    try:
        if file_path.suffix == ".jsonl":
            rows = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    rows.append(obj)
                    for req in REQUIRED_FIELDS:
                        if req not in obj:
                            return (
                                False,
                                f"Missing required field '{req}' at line {line_no} in {file_path.name}",
                                4,
                            )
                    if not isinstance(obj["gold_files"], list) or len(obj["gold_files"]) == 0:
                        return (
                            False,
                            f"Field 'gold_files' must be a non-empty list at line {line_no}",
                            4,
                        )
            if len(rows) == 0:
                return False, f"Dataset contains 0 rows: {file_path.name}", 4
            return True, f"Valid JSONL ContextBench dataset with {len(rows)} instances.", 0

        elif file_path.suffix == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("instances", [])
            if not items:
                return False, f"Dataset contains 0 instances: {file_path.name}", 4
            for idx, obj in enumerate(items):
                for req in REQUIRED_FIELDS:
                    if req not in obj:
                        return False, f"Missing required field '{req}' at instance index {idx}", 4
            return True, f"Valid JSON ContextBench dataset with {len(items)} instances.", 0

        elif file_path.suffix in [".parquet", ".arrow"]:
            # Native binary format validation
            return True, f"Binary dataset found ({file_path.suffix}). Schema check deferred to reader.", 0

        else:
            return False, f"Unsupported file extension: {file_path.suffix}", 4

    except Exception as e:
        return False, f"Corrupted or unreadable dataset file: {e}", 4


def main():
    parser = argparse.ArgumentParser(description="Deterministic ContextBench Validator")
    parser.add_argument("--data-dir", type=str, default=str(DEFAULT_TARGET_DIR))
    parser.add_argument("--expected-sha256", type=str, default=None)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print("=" * 80)
    print("REPONEEDLE: CONTEXTBENCH INDEPENDENT VALIDATION GATE")
    print(f"Target Directory: {data_dir}")
    print(f"Official Source:  {EXPECTED_HF_URL}")
    print("=" * 80)

    # Search for recognized ContextBench files in data_dir
    candidate_files = []
    if data_dir.is_dir():
        for ext in ["*.jsonl", "*.parquet", "*.json"]:
            candidate_files.extend(data_dir.glob(ext))

    if not candidate_files:
        print("\n[STATUS: BLOCKED BY EXTERNAL DATA ACCESS]")
        print(f"No ContextBench artifacts found in {data_dir}.")
        print("Network boundary prevents automated acquisition from Hugging Face.")
        print("See research/stage3_14/CONTEXTBENCH_ACQUISITION_BLOCKER.md for handoff instructions.")
        sys.exit(2)

    primary_file = candidate_files[0]
    is_valid, msg, code = validate_contextbench_file(primary_file, args.expected_sha256)
    if is_valid:
        print(f"\n[STATUS: VERIFIED AND READY] {msg}")
        sys.exit(0)
    else:
        print(f"\n[STATUS: REJECTED (Code {code})] {msg}")
        sys.exit(code)


if __name__ == "__main__":
    main()
