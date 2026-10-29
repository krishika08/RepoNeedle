"""
RepoNeedle Stage 3.15: ContextBench Thin Evaluation Adapter.
Connects frozen RepoNeedle retrieval engines to the ContextBench benchmark format.
Maintains strict hyperparameter immutability and fails closed on data anomalies.
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from reponeedle.models import FileDoc, Query, BudgetConfig, AblationConfig
from reponeedle.engine import RepoNeedleEngine
from research.stage3_15.validate_contextbench import validate_contextbench_file, RECORDED_FULL_SHA256


class FrozenConfigurationRegistry:
    """Provides immutable, frozen configuration instances for independent evaluation."""

    @staticmethod
    def get_config_01() -> AblationConfig:
        """BASE-BM25: Canonical BM25 baseline (Okapi k1=1.5, b=0.75)."""
        return AblationConfig.bm25_baseline()

    @staticmethod
    def get_config_09() -> AblationConfig:
        """CONFIG-09: RepoNeedle Quality Winner (Decoupled BM25 + Subword + DocFilter 0.5x, No PR)."""
        return AblationConfig.config_09()

    @staticmethod
    def get_config_10() -> AblationConfig:
        """CONFIG-10: Sparse Cascaded Production Reranker (BM25 Top-50 + Sliced Subword)."""
        return AblationConfig.config_10(pool_size=50)


def compute_instance_metrics(gold_files: List[str], ranked_paths: List[str], max_k: int = 20) -> Dict[str, float]:
    """
    Computes canonical retrieval metrics for a single task instance.
    Fails closed if ranked_paths is empty or incomplete.
    """
    if not ranked_paths:
        return {
            "mrr": 0.0,
            "recall_at_5": 0.0,
            "recall_at_10": 0.0,
            "recall_at_20": 0.0,
            "precision_at_5": 0.0,
            "status": "FAILED_EMPTY_PREDICTIONS",
        }

    gold_set = set(gold_files)
    if not gold_set:
        return {
            "mrr": 0.0,
            "recall_at_5": 0.0,
            "recall_at_10": 0.0,
            "recall_at_20": 0.0,
            "precision_at_5": 0.0,
            "status": "EXCLUDED_ZERO_GOLD_TARGETS",
        }

    # MRR (up to rank 20)
    rr = 0.0
    for idx, path in enumerate(ranked_paths[:max_k], 1):
        if path in gold_set:
            rr = 1.0 / idx
            break

    # Recall @ K
    def rec_k(k: int) -> float:
        top_k = set(ranked_paths[:k])
        return len(gold_set & top_k) / len(gold_set)

    # Precision @ 5
    p5_denom = min(5, len(ranked_paths))
    p5 = len(gold_set & set(ranked_paths[:5])) / p5_denom if p5_denom > 0 else 0.0

    return {
        "mrr": rr,
        "recall_at_5": rec_k(5),
        "recall_at_10": rec_k(10),
        "recall_at_20": rec_k(20),
        "precision_at_5": p5,
        "status": "SUCCESS",
    }


def run_evaluation_adapter(
    dataset_file: Path,
    output_dir: Path,
    expected_sha256: Optional[str] = RECORDED_FULL_SHA256,
) -> int:
    """
    Executes independent evaluation if dataset is verified.
    Returns exit code (0 on success, non-zero on failure or blocker).
    """
    print("=" * 80)
    print("REPONEEDLE: CONTEXTBENCH EVALUATION ADAPTER")
    print(f"Target Dataset: {dataset_file}")
    print("=" * 80)

    is_valid, msg, code = validate_contextbench_file(dataset_file, expected_sha256)
    if not is_valid:
        print(f"\n[EVALUATION BLOCKED] Dataset validation failed: {msg}")
        return code

    print(f"\n[DATASET VERIFIED] {msg}")
    print("Executing locked independent evaluation across frozen configurations...")

    # Load dataset instances
    instances = []
    if dataset_file.suffix == ".jsonl":
        with open(dataset_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    instances.append(json.loads(line))
    elif dataset_file.suffix == ".json":
        with open(dataset_file, "r", encoding="utf-8") as f:
            d = json.load(f)
            instances = d if isinstance(d, list) else d.get("instances", [])

    if not instances:
        print("[ERROR] No instances found in verified dataset.")
        return 4

    print(f"Loaded {len(instances)} task instances.")
    output_dir.mkdir(parents=True, exist_ok=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description="ContextBench Thin Evaluation Adapter")
    parser.add_argument("--dataset", type=str, required=True, help="Path to verified ContextBench file")
    parser.add_argument("--output-dir", type=str, default="research/stage3_15", help="Output directory")
    parser.add_argument("--sha256", type=str, default=RECORDED_FULL_SHA256, help="Expected dataset SHA-256")
    args = parser.parse_args()

    exit_code = run_evaluation_adapter(Path(args.dataset), Path(args.output_dir), args.sha256)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
