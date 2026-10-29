"""
Stage 3.10.2: Independent Clean-Room Reference Implementation of Evaluation Metrics.

Implements all metrics from first principles without calling evaluation harness code:
  - Reciprocal Rank (MRR component)
  - Fractional Multi-Target Recall@k (k=5, 10, 20)
  - Binary Hit@k (k=20)
  - Precision@k (k=5)
  - Character-based Greedy-Stop Coverage (ARB v2 baseline metric: char_cov@8k)
  - Token-based BCY at 4k, 8k, 16k with boundary truncation (BCY@4k, BCY@8k, BCY@16k)
  - Token-based Greedy-Skip Knapsack Packing
"""

import re
from typing import List, Set, Dict, Any, Tuple


# Pinned regex tokenizer (matches official ARB v2 regex tokenizer)
TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[^\s\w]", re.UNICODE)

def count_code_tokens(text: str) -> int:
    """Counts tokens using standard unicode identifier/punctuation splitting."""
    if not text:
        return 0
    return len(TOKEN_RE.findall(text))


def compute_reciprocal_rank(ranked_paths: List[str], gold_set: Set[str]) -> Tuple[float, int]:
    """
    Computes reciprocal rank (1/rank) of the first retrieved gold file.
    Returns (rr, first_rank). If no gold file is retrieved, returns (0.0, -1).
    """
    if not gold_set:
        return 0.0, -1
    for r_idx, path in enumerate(ranked_paths, 1):
        if path in gold_set:
            return 1.0 / float(r_idx), r_idx
    return 0.0, -1


def compute_fractional_recall(ranked_paths: List[str], gold_set: Set[str], k: int) -> float:
    """
    Computes fractional multi-target recall in top-k positions:
    Recall@k = |TopK ∩ Gold| / |Gold|
    Denominator is strictly the total number of gold files.
    """
    if not gold_set or k <= 0:
        return 0.0
    top_k_set = set(ranked_paths[:k])
    intersect = top_k_set.intersection(gold_set)
    return float(len(intersect)) / float(len(gold_set))


def compute_binary_hit(ranked_paths: List[str], gold_set: Set[str], k: int) -> float:
    """
    Computes binary hit indicator in top-k positions:
    Hit@k = 1.0 if |TopK ∩ Gold| > 0 else 0.0
    """
    if not gold_set or k <= 0:
        return 0.0
    top_k_set = set(ranked_paths[:k])
    return 1.0 if len(top_k_set.intersection(gold_set)) > 0 else 0.0


def compute_precision_at_k(ranked_paths: List[str], gold_set: Set[str], k: int) -> float:
    """
    Computes precision in top-k positions:
    P@k = |TopK ∩ Gold| / min(k, len(ranked_paths))
    """
    if not gold_set or not ranked_paths or k <= 0:
        return 0.0
    denom = min(k, len(ranked_paths))
    top_k_set = set(ranked_paths[:k])
    intersect = top_k_set.intersection(gold_set)
    return float(len(intersect)) / float(denom)


def compute_char_coverage_greedy_stop(
    ranked_chunks: List[Dict[str, Any]],
    gold_set: Set[str],
    budget_chars: int = 8000
) -> float:
    """
    Independent reference implementation of ARB v2 baseline gold_coverage_at_budget:
    Measures character length (len(text)) under strict greedy-stop.
    """
    if not gold_set:
        return 0.0
    used_chars = 0
    covered_files = set()
    for chunk in ranked_chunks:
        text = str(chunk.get("text", ""))
        chunk_len = len(text)
        # ARB v2 boundary check
        if used_chars + chunk_len > budget_chars and used_chars > 0:
            break
        used_chars += chunk_len
        path = str(chunk.get("path", ""))
        if path in gold_set:
            covered_files.add(path)
    return float(len(covered_files)) / float(len(gold_set))


def compute_token_bcy_truncation(
    ranked_paths: List[str],
    path_to_text: Dict[str, str],
    gold_set: Set[str],
    budget_tokens: int = 8000
) -> float:
    """
    Independent reference implementation of true token-budgeted BCY with truncation.
    Measures code tokens using regex tokenizer; packs files up to budget_tokens.
    """
    if not gold_set or budget_tokens <= 0:
        return 0.0
    used_tokens = 0
    covered_gold = set()
    for path in ranked_paths:
        text = path_to_text.get(path, "")
        t_count = count_code_tokens(text)
        remaining = budget_tokens - used_tokens
        if remaining <= 0:
            break
        if t_count <= remaining:
            used_tokens += t_count
            if path in gold_set:
                covered_gold.add(path)
        else:
            # Partial truncation at budget boundary: file is partially included
            used_tokens += remaining
            if path in gold_set:
                covered_gold.add(path)
            break
    return float(len(covered_gold)) / float(len(gold_set))
