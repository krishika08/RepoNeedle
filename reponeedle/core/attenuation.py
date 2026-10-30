"""
Language detection and hub attenuation policies for RepoNeedle.
"""

from __future__ import annotations

import math


def detect_file_language(path: str) -> str:
    """Detects the programming language of a file from its path extension."""
    p = path.lower().replace("\\", "/")
    if p.endswith((".go",)):
        return "go"
    if p.endswith((".py", ".pyi")):
        return "python"
    if p.endswith((".rs",)):
        return "rust"
    if p.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")):
        return "typescript"
    if p.endswith((".java",)):
        return "java"
    return "unknown"


def compute_hub_attenuation(
    path: str,
    in_deg: int,
    out_deg: int,
    policy: str = "unattenuated",
) -> float:
    """
    Computes degree-based hub attenuation multiplier for graph propagation.
    
    Policies:
      - 'unattenuated': Canonical ARM-101 (multiplier = 1.0).
      - 'uniform_log2': Uniform logarithmic degree discount (1 / log2(2 + in_deg)).
      - 'lang_calibrated': Language-calibrated hub attenuation.
      - 'structural_role': Sink-ratio based attenuation.
      - 'degree_threshold_15': Hard step discount for high-degree nodes (in_deg >= 15 -> 0.5).
    """
    if policy == "unattenuated":
        return 1.0

    if policy == "uniform_log2":
        return 1.0 / math.log2(2.0 + max(0, in_deg))

    lang = detect_file_language(path)
    p_lower = path.lower().replace("\\", "/")
    is_util_name = any(u in p_lower for u in ["util", "helper", "compat", "common", "format", "log"])

    if policy == "lang_calibrated":
        if lang == "python":
            return 1.0 / math.log2(2.0 + max(0, in_deg))
        elif lang == "go":
            return 1.0
        elif lang in ("rust", "typescript", "java"):
            return 1.0 / math.log2(2.0 + 0.5 * max(0, in_deg))
        else:
            return 1.0

    if policy == "structural_role":
        if is_util_name:
            return 1.0 / math.log2(2.0 + max(0, in_deg))
        if in_deg >= 3 and out_deg <= 1:
            return 1.0 / math.log2(2.0 + max(0, in_deg))
        return 1.0

    if policy == "degree_threshold_15":
        if in_deg >= 15:
            return 0.5
        return 1.0

    return 1.0
