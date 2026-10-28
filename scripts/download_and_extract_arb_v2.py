"""
Download and extract official Agent Retrieval Bench v2 release bundles.
Validates SHA256 checksums and unpacks into external/agent-retrieval-bench/data/.
"""

import os
import sys
import hashlib
import json
import time
from pathlib import Path
import zstandard
import tarfile
from huggingface_hub import hf_hub_download

REPO_ID = "eyuansu71/agent_retrieval_bench"
RELEASES = [
    ("v2_trace2code", "releases/v2_trace2code/agent_retrieval_bench_v2_trace2code.tar.zst", "releases/v2_trace2code/agent_retrieval_bench_v2_trace2code.tar.zst.sha256"),
    ("v2_edit2ripple", "releases/v2_edit2ripple/agent_retrieval_bench_v2_edit2ripple.tar.zst", "releases/v2_edit2ripple/agent_retrieval_bench_v2_edit2ripple.tar.zst.sha256"),
    ("v2_abstention", "releases/v2_abstention/agent_retrieval_bench_v2_abstention.tar.zst", "releases/v2_abstention/agent_retrieval_bench_v2_abstention.tar.zst.sha256"),
    ("v2_comment2context", "releases/v2_comment2context/agent_retrieval_bench_v2_comment2context.tar.zst", "releases/v2_comment2context/agent_retrieval_bench_v2_comment2context.tar.zst.sha256"),
    ("v2_code2test", "releases/v2_code2test/agent_retrieval_bench_v2_code2test.tar.zst", "releases/v2_code2test/agent_retrieval_bench_v2_code2test.tar.zst.sha256"),
    ("v2_selective_retrieval_balanced", "releases/v2_selective_retrieval_balanced/agent_retrieval_bench_v2_selective_retrieval_balanced.tar.zst", "releases/v2_selective_retrieval_balanced/agent_retrieval_bench_v2_selective_retrieval_balanced.tar.zst.sha256"),
    ("v2_selective_retrieval_natural", "releases/v2_selective_retrieval_natural/agent_retrieval_bench_v2_selective_retrieval_natural.tar.zst", "releases/v2_selective_retrieval_natural/agent_retrieval_bench_v2_selective_retrieval_natural.tar.zst.sha256"),
]


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def extract_tar_zst(archive_path: Path, target_dir: Path):
    dctx = zstandard.ZstdDecompressor()
    with open(archive_path, "rb") as f:
        with dctx.stream_reader(f) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tar:
                tar.extractall(path=target_dir)


def main():
    dest_dir = Path("external/agent-retrieval-bench/data")
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"Target destination: {dest_dir.resolve()}")
    results = {}

    for release_id, archive_subpath, checksum_subpath in RELEASES:
        print(f"\n[{release_id}] Starting download and verification...")
        t0 = time.time()

        # 1. Download checksum
        checksum_local = hf_hub_download(repo_id=REPO_ID, filename=checksum_subpath, repo_type="dataset")
        with open(checksum_local, "r", encoding="utf-8") as f:
            expected_sha = f.read().strip().split()[0].lower()

        # 2. Download archive
        archive_local = hf_hub_download(repo_id=REPO_ID, filename=archive_subpath, repo_type="dataset")
        archive_path = Path(archive_local)
        file_size_mb = archive_path.stat().st_size / (1024 * 1024)

        # 3. Verify Checksum
        actual_sha = sha256_file(archive_path).lower()
        if actual_sha != expected_sha:
            raise ValueError(f"Checksum mismatch for {release_id}!\nExpected: {expected_sha}\nActual:   {actual_sha}")
        print(f"  Checksum verified: {actual_sha[:16]}... ({file_size_mb:.2f} MB)")

        # 4. Extract
        print(f"  Extracting into {dest_dir}...")
        extract_tar_zst(archive_path, dest_dir)
        dur = time.time() - t0
        print(f"  Extracted {release_id} in {dur:.2f}s")

        results[release_id] = {
            "size_mb": file_size_mb,
            "sha256": actual_sha,
            "extract_time_s": dur,
        }

    print("\n" + "=" * 60)
    print("ALL RELEASES DOWNLOADED, VERIFIED, AND EXTRACTED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()

