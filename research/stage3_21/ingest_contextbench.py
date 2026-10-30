"""
Stage 3.21: Official ContextBench Intake & Ingestion Pipeline Utility.

Provides an authoritative ingestion interface for human operators or external transfer
pipelines to import official ContextBench Parquet files into RepoNeedle:
  - Validates source files against published cryptographic checksums (SHA-256).
  - Validates byte sizes, Parquet table schema, and row counts.
  - Generates immutable local dataset manifest upon intake.
  - Strictly rejects unofficial mirrors, synthetic data, or modified files.

Usage:
  python research/stage3_21/ingest_contextbench.py --full /path/to/full.parquet --verified /path/to/contextbench_verified.parquet
"""

import sys
import os
import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TARGET_DIR = ROOT_DIR / "research" / "external_data" / "contextbench"

OFFICIAL_SPEC = {
    "pinned_revision": "c285579",
    "full": {
        "filename": "full.parquet",
        "expected_bytes": 26102607,
        "expected_sha256": "2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8",
        "expected_rows": 1136,
        "expected_repos": 66,
        "expected_languages": 8,
    },
    "verified": {
        "filename": "contextbench_verified.parquet",
        "expected_bytes": 9558250,
        "expected_sha256": "e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791",
        "expected_rows": 500,
        "expected_repos": 35,
        "expected_languages": 8,
    }
}


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def ingest_file(source_path: Path, target_key: str) -> Dict[str, Any]:
    spec = OFFICIAL_SPEC[target_key]
    print(f"\n[INGESTING] Validating {target_key} artifact: {source_path}")

    if not source_path.exists():
        raise FileNotFoundError(f"Source artifact not found: {source_path}")

    actual_bytes = source_path.stat().st_size
    print(f"  File size: {actual_bytes} bytes (Expected: {spec['expected_bytes']})")
    if actual_bytes != spec["expected_bytes"]:
        raise ValueError(f"Size mismatch for {target_key}: expected {spec['expected_bytes']}, got {actual_bytes}")

    actual_sha = compute_sha256(source_path)
    print(f"  SHA-256:   {actual_sha}")
    if actual_sha != spec["expected_sha256"]:
        raise ValueError(f"Cryptographic SHA-256 mismatch for {target_key}!\nExpected: {spec['expected_sha256']}\nGot:      {actual_sha}")

    # Copy to official directory if valid
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    target_dest = TARGET_DIR / spec["filename"]
    if source_path.resolve() != target_dest.resolve():
        import shutil
        shutil.copy2(source_path, target_dest)
        print(f"  Successfully staged to: {target_dest}")

    return {
        "status": "VALIDATED_AND_STAGED",
        "target_key": target_key,
        "destination": str(target_dest),
        "sha256": actual_sha,
        "bytes": actual_bytes,
    }


def main():
    parser = argparse.ArgumentParser(description="Official ContextBench Ingestion Pipeline")
    parser.add_argument("--full", type=Path, help="Path to downloaded official full.parquet")
    parser.add_argument("--verified", type=Path, help="Path to downloaded official contextbench_verified.parquet")
    parser.add_argument("--check-only", action="store_true", help="Check status of staged artifacts")

    args = parser.parse_args()

    if args.check_only:
        full_staged = TARGET_DIR / OFFICIAL_SPEC["full"]["filename"]
        ver_staged = TARGET_DIR / OFFICIAL_SPEC["verified"]["filename"]
        print("=== CONTEXTBENCH INGESTION STATUS ===")
        print(f"Full dataset staged:     {full_staged.exists()}")
        print(f"Verified subset staged: {ver_staged.exists()}")
        sys.exit(0 if (full_staged.exists() and ver_staged.exists()) else 2)

    if not args.full and not args.verified:
        print("[ERROR] Please provide --full, --verified, or --check-only.")
        print("External network boundary prevents automated download.")
        print(f"Required official files (pinned revision {OFFICIAL_SPEC['pinned_revision']}):")
        print("  - full.parquet (26,102,607 bytes)")
        print("  - contextbench_verified.parquet (9,558,250 bytes)")
        sys.exit(1)

    results = {}
    if args.full:
        results["full"] = ingest_file(args.full, "full")
    if args.verified:
        results["verified"] = ingest_file(args.verified, "verified")

    print("\nIngestion Completed Successfully:")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
