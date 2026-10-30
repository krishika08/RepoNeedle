"""
Deterministic Intake & Integrity Validator for Official ContextBench Datasets.

Validates official artifacts against strict benchmark contract:
- Full dataset (default configuration): exactly 1,136 rows, 66 repositories, 8 languages.
- Verified subset (contextbench_verified): exactly 500 rows.
- Required columns: instance_id, repo, base_commit, problem_statement, gold_context.
- Uniqueness of instance_id and non-empty gold context.
- SHA-256 calculation and file integrity.

Exit codes:
- 0: Validation SUCCESS
- 2: BLOCKED — Files missing
- 3: CHECKSUM MISMATCH
- 4: INVALID SCHEMA OR ROW COUNT
"""

import sys
import os
import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

try:
    import duckdb
except ImportError:
    duckdb = None

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DATA_DIR = Path(__file__).resolve().parent

REQUIRED_COLUMNS = [
    "instance_id",
    "repo",
    "base_commit",
    "problem_statement",
    "gold_context",
]

PINNED_REVISION = "c285579"
FULL_EXPECTED_ROWS = 1136
FULL_EXPECTED_REPOS = 66
FULL_EXPECTED_LANGUAGES = 8
FULL_EXPECTED_BYTES = 26102607
FULL_EXPECTED_SHA256 = "2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8"

VERIFIED_EXPECTED_ROWS = 500
VERIFIED_EXPECTED_BYTES = 9558250
VERIFIED_EXPECTED_SHA256 = "e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791"


def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_dataset_records(filepath: Path) -> List[Dict[str, Any]]:
    suffix = filepath.suffix.lower()
    if suffix == ".parquet":
        if not duckdb:
            raise RuntimeError("DuckDB required to inspect Parquet files in this environment.")
        con = duckdb.connect()
        # Query parquet into list of dicts
        escaped_path = str(filepath).replace("\\", "/")
        df = con.execute(f"SELECT * FROM '{escaped_path}'").fetchall()
        col_names = [desc[0] for desc in con.description]
        records = []
        for row in df:
            records.append(dict(zip(col_names, row)))
        return records

    elif suffix in (".jsonl", ".json"):
        records = []
        with open(filepath, "r", encoding="utf-8") as f:
            if suffix == ".jsonl":
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
            else:
                data = json.load(f)
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict) and "data" in data:
                    records = data["data"]
                else:
                    records = [data]
        return records
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def validate_contextbench_records(records: List[Dict[str, Any]], expected_config: Optional[str] = "full") -> Tuple[bool, str]:
    if not records:
        return False, "Dataset contains 0 rows (empty dataset)."

    row_count = len(records)
    if expected_config == "full" and row_count != FULL_EXPECTED_ROWS:
        return False, f"Full dataset row count mismatch: expected {FULL_EXPECTED_ROWS}, found {row_count}."
    elif expected_config == "verified" and row_count != VERIFIED_EXPECTED_ROWS:
        return False, f"Verified subset row count mismatch: expected {VERIFIED_EXPECTED_ROWS}, found {row_count}."

    seen_ids = set()
    repos = set()
    languages = set()

    for idx, row in enumerate(records):
        for col in REQUIRED_COLUMNS:
            if col not in row or row[col] is None:
                return False, f"Row {idx} missing required column '{col}'."

        iid = str(row["instance_id"]).strip()
        if not iid:
            return False, f"Row {idx} has empty instance_id."
        if iid in seen_ids:
            return False, f"Duplicate instance_id '{iid}' at row {idx}."
        seen_ids.add(iid)

        repo = str(row["repo"]).strip()
        if not repo:
            return False, f"Row {idx} has empty repo identifier."
        repos.add(repo)

        bcommit = str(row["base_commit"]).strip()
        if not bcommit:
            return False, f"Row {idx} has empty base_commit."

        prob = str(row["problem_statement"]).strip()
        if not prob:
            return False, f"Row {idx} has empty problem_statement query."

        # Check gold_context structure
        gold = row["gold_context"]
        if isinstance(gold, str):
            try:
                gold = json.loads(gold)
            except Exception:
                pass
        if not gold:
            return False, f"Row {idx} ('{iid}') has empty gold_context."

        # Language tracking
        lang = row.get("language")
        if lang:
            languages.add(str(lang).lower())

    if expected_config == "full":
        if len(repos) < FULL_EXPECTED_REPOS:
            return False, f"Repository coverage incomplete: expected {FULL_EXPECTED_REPOS}, found {len(repos)}."
        if languages and len(languages) < FULL_EXPECTED_LANGUAGES:
            return False, f"Language coverage incomplete: expected {FULL_EXPECTED_LANGUAGES}, found {len(languages)}."

    return True, f"Valid {expected_config} dataset ({row_count} tasks, {len(repos)} repos)."


def verify_subset_integrity(full_records: List[Dict[str, Any]], verified_records: List[Dict[str, Any]]) -> Tuple[bool, str]:
    full_ids = {str(r["instance_id"]).strip() for r in full_records}
    verified_ids = {str(r["instance_id"]).strip() for r in verified_records}
    if not verified_ids.issubset(full_ids):
        diff = verified_ids - full_ids
        return False, f"Verified dataset contains {len(diff)} tasks not present in full dataset: {list(diff)[:5]}"
    return True, f"Verified dataset (500 tasks) is a strict subset of full dataset ({len(full_ids)} tasks)."


def validate_file(filepath: Path, expected_config: str, expected_sha: Optional[str] = None, expected_bytes: Optional[int] = None) -> Tuple[int, str]:
    if not filepath.exists():
        return 2, f"Target file does not exist: {filepath}"

    file_size = filepath.stat().st_size
    if file_size == 0:
        return 4, f"Target file is 0 bytes: {filepath}"

    if expected_bytes is not None and file_size != expected_bytes:
        return 3, f"Byte size mismatch for {filepath.name}: expected {expected_bytes} bytes, got {file_size} bytes."

    actual_sha = compute_sha256(filepath)
    if expected_sha and actual_sha.lower() != expected_sha.lower():
        return 3, f"Checksum mismatch for {filepath.name}: expected {expected_sha}, got {actual_sha}."

    try:
        records = load_dataset_records(filepath)
    except Exception as e:
        return 4, f"Failed to parse dataset file {filepath.name}: {e}"

    is_valid, msg = validate_contextbench_records(records, expected_config=expected_config)
    if not is_valid:
        return 4, f"Validation failure in {filepath.name}: {msg}"

    return 0, f"SUCCESS: {filepath.name} valid {expected_config} dataset ({len(records)} rows, {file_size} bytes, SHA-256: {actual_sha[:16]}...)"


def main():
    parser = argparse.ArgumentParser(description="Official ContextBench Intake & Integrity Validator")
    parser.add_argument("--data-dir", type=str, default=str(DEFAULT_DATA_DIR), help="Directory holding ContextBench artifacts")
    parser.add_argument("--expected-config", type=str, choices=["full", "verified", "auto"], default="auto")
    parser.add_argument("--expected-sha256", type=str, default=None)
    parser.add_argument("--expected-bytes", type=int, default=None)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print("=" * 80)
    print("REPONEEDLE: OFFICIAL CONTEXTBENCH VALIDATION GATE (STAGE 3.17)")
    print(f"Data Directory: {data_dir}")
    print(f"Pinned Upstream Revision: {PINNED_REVISION}")
    print("=" * 80)

    if not data_dir.exists():
        print(f"\n[STATUS: BLOCKED - DATA ACCESS]")
        print(f"Target data directory does not exist: {data_dir}")
        sys.exit(2)

    # Check for candidate files
    candidates = list(data_dir.glob("*.parquet")) + list(data_dir.glob("*.jsonl"))
    candidates = [c for c in candidates if not c.name.startswith("bad_") and not c.name.startswith("empty_") and not c.name.startswith("test_")]

    if not candidates:
        print("\n[STATUS: BLOCKED - DATA ACCESS]")
        print(f"No ContextBench artifacts found in {data_dir}.")
        print("Required artifacts:")
        print(f"  - full.parquet (expected SHA: {FULL_EXPECTED_SHA256}, {FULL_EXPECTED_BYTES} bytes)")
        print(f"  - contextbench_verified.parquet (expected SHA: {VERIFIED_EXPECTED_SHA256}, {VERIFIED_EXPECTED_BYTES} bytes)")
        print("Network boundary prevents automated acquisition from Hugging Face.")
        print("See research/external_data/contextbench/ACQUISITION_BLOCKER.md for handoff instructions.")
        sys.exit(2)

    exit_code = 0
    loaded_records = {}
    for cand in candidates:
        fname = cand.name.lower()
        cfg = args.expected_config
        expected_sha = args.expected_sha256
        expected_bytes = args.expected_bytes

        if cfg == "auto":
            if "verified" in fname:
                cfg = "verified"
                if not expected_sha:
                    expected_sha = VERIFIED_EXPECTED_SHA256
                if not expected_bytes:
                    expected_bytes = VERIFIED_EXPECTED_BYTES
            else:
                cfg = "full"
                if not expected_sha:
                    expected_sha = FULL_EXPECTED_SHA256
                if not expected_bytes:
                    expected_bytes = FULL_EXPECTED_BYTES

        code, msg = validate_file(cand, expected_config=cfg, expected_sha=expected_sha, expected_bytes=expected_bytes)
        print(f"[{'PASS' if code == 0 else 'FAIL'}] {cand.name}: {msg}")
        if code != 0:
            exit_code = code
        else:
            try:
                loaded_records[cfg] = load_dataset_records(cand)
            except Exception:
                pass

    if "full" in loaded_records and "verified" in loaded_records:
        sub_ok, sub_msg = verify_subset_integrity(loaded_records["full"], loaded_records["verified"])
        print(f"[{'PASS' if sub_ok else 'FAIL'}] Subset Integrity: {sub_msg}")
        if not sub_ok:
            exit_code = 4

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
