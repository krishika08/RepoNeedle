"""
Strict Repository-Clustered Split for Mission 0.80+ Phase R2.
Ensures zero data leakage between Train, Validation, and Held-out sets.
"""
import gzip
import json
import os
from typing import Dict, List, Set, Tuple

TRAIN_REPOS: Set[str] = {
    "gin-gonic/gin",
    "etcd-io/etcd",
    "pallets/click",
    "caddyserver/caddy",
    "clap-rs/clap",
    "spring-projects/spring-boot",
    "vuejs/core",
    "pypa/pip",
    "fastapi/fastapi",
    "scrapy/scrapy",
    "ipython/ipython",
    "tox-dev/tox",
    "mockito/mockito",
    "HypothesisWorks/hypothesis",
    "numpy/numpy",
}

VAL_REPOS: Set[str] = {
    "tokio-rs/tokio",
    "huggingface/diffusers",
    "microsoft/playwright",
    "pydantic/pydantic",
    "eslint/eslint",
}

HELD_OUT_REPOS: Set[str] = {
    "huggingface/transformers",
    "vitejs/vite",
    "pytest-dev/pytest",
    "astral-sh/ruff",
    "python/mypy",
}

def verify_split_integrity():
    # Verify pairwise disjointness
    assert not (TRAIN_REPOS & VAL_REPOS), "Train and Validation overlap!"
    assert not (TRAIN_REPOS & HELD_OUT_REPOS), "Train and Held-out overlap!"
    assert not (VAL_REPOS & HELD_OUT_REPOS), "Validation and Held-out overlap!"
    assert len(TRAIN_REPOS) == 15, f"Expected 15 train repos, got {len(TRAIN_REPOS)}"
    assert len(VAL_REPOS) == 5, f"Expected 5 val repos, got {len(VAL_REPOS)}"
    assert len(HELD_OUT_REPOS) == 5, f"Expected 5 held-out repos, got {len(HELD_OUT_REPOS)}"

def load_data(
    baseline_path: str = "reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl",
    m1_path: str = "research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz"
) -> Tuple[List[dict], List[dict], List[dict]]:
    verify_split_integrity()
    
    # Load baseline records
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_records = {r["sample_id"]: r for r in (json.loads(l) for l in f if l.strip())}
        
    # Load M1 candidates
    m1_records = {}
    with gzip.open(m1_path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                m1_records[data["query_id"]] = data

    assert len(baseline_records) == 345, f"Expected 345 baseline records, got {len(baseline_records)}"
    assert len(m1_records) == 345, f"Expected 345 M1 records, got {len(m1_records)}"

    train_data = []
    val_data = []
    held_out_data = []

    for qid, base in baseline_records.items():
        m1 = m1_records[qid]
        repo = base["repo"]
        
        # Merge record for evaluation
        record = {
            "query_id": qid,
            "repo": repo,
            "base_commit": base["base_commit"],
            "task_type": base.get("task_type", "unknown"),
            "gold_files": base["gold_files"],
            "query_text": m1.get("query_text", ""),
            "candidates": m1["candidates"],
            "total_candidates": m1.get("total_candidates", len(m1["candidates"])),
            "v0_reponeedle": base["reponeedle"],
        }
        
        if repo in TRAIN_REPOS:
            train_data.append(record)
        elif repo in VAL_REPOS:
            val_data.append(record)
        elif repo in HELD_OUT_REPOS:
            held_out_data.append(record)
        else:
            raise ValueError(f"Unknown repo: {repo}")

    assert len(train_data) == 210, f"Expected 210 train records, got {len(train_data)}"
    assert len(val_data) == 60, f"Expected 60 val records, got {len(val_data)}"
    assert len(held_out_data) == 75, f"Expected 75 held-out records, got {len(held_out_data)}"

    return train_data, val_data, held_out_data

if __name__ == "__main__":
    t, v, h = load_data()
    print(f"Data Split Verified Successfully!")
    print(f"  Train:     {len(t)} queries ({len(TRAIN_REPOS)} repos)")
    print(f"  Val:       {len(v)} queries ({len(VAL_REPOS)} repos)")
    print(f"  Held-Out:  {len(h)} queries ({len(HELD_OUT_REPOS)} repos)")
    print(f"  Total:     {len(t) + len(v) + len(h)} queries (25 repos)")

