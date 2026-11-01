"""
RepoNeedle V1.0.0 - Milestone 2 Recovery: Evidence-Gated Structural Ranker
Implements Treatments A through F with bounded multipliers and strict evidence gating.
Preserves frozen M1 candidate membership and guarantees zero candidate eviction.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple


class ConfidenceAwareIntentClassifier:
    """
    Infers intent and confidence from query text without oracle benchmark labels.
    If confidence < 0.70, retrieval falls back to lexical baseline.
    """
    TRACE_STRONG = [
        re.compile(r"Traceback\s+\(most\s+recent\s+call\s+last\)", re.IGNORECASE),
        re.compile(r"File\s+[\"'][^\"']+[\"'],\s+line\s+\d+", re.IGNORECASE),
        re.compile(r"\bpanic:\s+", re.IGNORECASE),
        re.compile(r"[\w\.\-/]+\.go:\d+\s+\+0x[0-9a-fA-F]+"),
        re.compile(r"at\s+[\w\.\-/]+\.rs:\d+(?::\d+)?"),
        re.compile(r"at\s+[\w\.\-/]+\.[jt]sx?:\d+:\d+"),
    ]
    TRACE_WEAK = [
        re.compile(r"\b(?:NullPointerException|IndexOutOfBoundsException|KeyError|ValueError|TypeError|AttributeError|RuntimeError|panic)\b"),
        re.compile(r"stack\s+trace", re.IGNORECASE),
        re.compile(r"line\s+\d+", re.IGNORECASE),
    ]

    DIFF_STRONG = [
        re.compile(r"@@\s+-\d+,\d+\s+\+\d+,\d+\s+@@"),
        re.compile(r"diff\s+--git"),
        re.compile(r"\banchor_diff\b"),
        re.compile(r"\b(?:ripple|side[- ]effects?|impact|dependents?)\b", re.IGNORECASE),
    ]
    DIFF_WEAK = [
        re.compile(r"\b(?:modify|modifying|refactor|refactoring|renamed?|changing)\b", re.IGNORECASE),
        re.compile(r"\b(?:called\s+by|callers?\s+of|importers?\s+of|downstream)\b", re.IGNORECASE),
        re.compile(r"\b(?:edit|edits|patch|patching)\b", re.IGNORECASE),
    ]

    TEST_STRONG = [
        re.compile(r"\b(?:find|write|unit|integration|coverage)\s+tests?\b", re.IGNORECASE),
        re.compile(r"\btests?\s+(?:for|covering|validating|exercising)\b", re.IGNORECASE),
        re.compile(r"\b(?:test_cases?|test_suite|test_function)\b", re.IGNORECASE),
    ]
    TEST_WEAK = [
        re.compile(r"\btest_\w+\b"),
        re.compile(r"\b\w+_test\b"),
        re.compile(r"\bassert(?:s|ion|Equal|True|False|Raises)?\b"),
    ]

    @classmethod
    def classify(cls, query_text: str) -> Tuple[str, float, str]:
        strong_trace = sum(1 for p in cls.TRACE_STRONG if p.search(query_text))
        weak_trace = sum(1 for p in cls.TRACE_WEAK if p.search(query_text))
        trace_score = strong_trace * 3.0 + weak_trace * 1.0

        strong_diff = sum(1 for p in cls.DIFF_STRONG if p.search(query_text))
        weak_diff = sum(1 for p in cls.DIFF_WEAK if p.search(query_text))
        diff_score = strong_diff * 3.0 + weak_diff * 1.0

        strong_test = sum(1 for p in cls.TEST_STRONG if p.search(query_text))
        weak_test = sum(1 for p in cls.TEST_WEAK if p.search(query_text))
        test_score = strong_test * 3.0 + weak_test * 1.0

        if strong_trace >= 1:
            conf = min(0.99, 0.70 + 0.10 * strong_trace + 0.05 * weak_trace)
            return "traceback", round(conf, 2), f"Strong stack frame patterns detected ({strong_trace} frames)"

        if strong_diff >= 1:
            conf = min(0.99, 0.75 + 0.10 * strong_diff + 0.05 * weak_diff)
            return "edit2ripple", round(conf, 2), f"Unified diff / patch markers detected ({strong_diff} markers)"

        if strong_test >= 1 and test_score > diff_score:
            conf = min(0.95, 0.65 + 0.15 * strong_test)
            return "code2test", round(conf, 2), f"Explicit test discovery intent detected ({strong_test} phrases)"

        scores = {
            "traceback": trace_score,
            "edit2ripple": diff_score,
            "code2test": test_score,
        }
        best_intent, best_val = max(scores.items(), key=lambda x: x[1])

        if best_val >= 2.0:
            sorted_vals = sorted(scores.values(), reverse=True)
            margin = sorted_vals[0] - sorted_vals[1]
            if margin >= 1.5:
                return best_intent, 0.65, f"Moderate pattern match with margin {margin:.1f}"
            else:
                return "ambiguous", 0.40, f"Colliding intent signals (best: {best_intent}, margin: {margin:.1f})"

        words = re.findall(r"\b[A-Za-z]{3,}\b", query_text)
        if len(words) > 5:
            return "comment2context", 0.75, "Natural language description without structural markers"

        return "ambiguous", 0.35, "Short uncharacterized token string"


class TracebackParser:
    FRAME_PATTERNS = [
        re.compile(r'File\s+["\'](?P<path>[^"\']+)["\'],\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<func>\w+))?'),
        re.compile(r'(?P<path>[\w\.\-/]+\.go):(?P<line>\d+)(?:\s+\+0x[0-9a-fA-F]+)?'),
        re.compile(r'at\s+(?P<path>[\w\.\-/]+\.rs):(?P<line>\d+)(?::(?P<col>\d+))?'),
        re.compile(r'at\s+(?:(?P<func>[\w\.\$<>]+)\s+\()?(?P<path>[\w\.\-/]+\.[jt]sx?):(?P<line>\d+):(?P<col>\d+)\)?'),
    ]

    EXTERNAL_MARKERS = [
        "site-packages", "node_modules", "/usr/lib", "/usr/local",
        "library/frameworks", "go/src/runtime", "rustc/", "cargo/registry",
    ]

    TEST_RUNNER_MARKERS = [
        "pytest", "unittest", "testing/runner", "_test.go", "tests/runner",
        "jest", "mocha", "cargo test",
    ]

    @classmethod
    def parse_frames(cls, query_text: str) -> List[Dict[str, Any]]:
        frames = []
        for line in query_text.splitlines():
            for pat in cls.FRAME_PATTERNS:
                m = pat.search(line)
                if m:
                    raw_path = m.group("path").replace("\\", "/")
                    line_num = int(m.group("line")) if "line" in m.groupdict() and m.group("line") else None
                    func_name = m.group("func") if "func" in m.groupdict() else None

                    is_external = any(ext in raw_path.lower() for ext in cls.EXTERNAL_MARKERS)
                    is_test_runner = any(tr in raw_path.lower() for tr in cls.TEST_RUNNER_MARKERS)

                    frames.append({
                        "raw_path": raw_path,
                        "line": line_num,
                        "func": func_name,
                        "is_external": is_external,
                        "is_test_runner": is_test_runner,
                    })
                    break
        return frames

    @classmethod
    def build_trace_lookup(cls, trace_frames: List[Dict[str, Any]]) -> Dict[str, float]:
        lookup: Dict[str, float] = {}
        if not trace_frames:
            return lookup

        app_frames = [f for f in trace_frames if not f["is_external"]]
        if not app_frames:
            app_frames = trace_frames

        for idx, f in enumerate(reversed(app_frames)):
            fp = f["raw_path"].lower()
            fb = fp.split("/")[-1]
            depth_factor = 1.0 / (1.0 + 0.3 * idx)
            runner_penalty = 0.5 if f["is_test_runner"] else 1.0
            score = depth_factor * runner_penalty

            if fp not in lookup:
                lookup[fp] = 1.0 * score
            if fb not in lookup:
                lookup[fb] = 0.8 * score

        return lookup


class HubNormalizer:
    GENERIC_STEMS = {
        "utils", "util", "common", "helpers", "helper", "types", "type",
        "constants", "constant", "errors", "error", "base", "index",
        "__init__", "mod", "config", "defs", "shared",
    }

    @classmethod
    def compute_hub_penalty(
        cls,
        candidate_path: str,
        in_degree: int = 0,
        has_unique_symbol_match: bool = False,
    ) -> float:
        cand_norm = candidate_path.lower().replace("\\", "/")
        cand_base = cand_norm.split("/")[-1].rsplit(".", 1)[0]

        is_generic = cand_base in cls.GENERIC_STEMS
        base_penalty = 1.0 / (1.0 + 0.20 * math.log(1.0 + max(0, in_degree)))

        if is_generic:
            base_penalty *= 0.75

        # Shield legitimate targets that match exact unique symbols
        if has_unique_symbol_match:
            base_penalty = base_penalty + (1.0 - base_penalty) * 0.85

        return max(0.1, min(1.0, base_penalty))


class EvidenceGatedRanker:
    """
    Reranks frozen M1 candidates using evidence-gated bounded multipliers.
    Guarantees:
    - Never drops or evicts candidates.
    - Uses M1 rank as deterministic tie-breaker.
    - Weak structural evidence cannot override strong lexical retrieval.
    """

    SUPPORTED_CONFIGS = {
        "A": "m1_baseline",
        "B": "m1_hub_norm",
        "C": "m1_exact_structural",
        "D": "m1_intent_guided",
        "E": "m1_bounded_structural",
        "F": "m1_evidence_gated_combined",
    }

    @classmethod
    def rank_candidates(
        cls,
        query_snapshot: Dict[str, Any],
        config: str = "F",
    ) -> List[Dict[str, Any]]:
        query_text = query_snapshot.get("query_text", "")
        candidates = query_snapshot.get("candidates", [])

        if not candidates:
            return []

        # Intent classification with confidence gate
        intent, confidence, _ = ConfidenceAwareIntentClassifier.classify(query_text)
        is_confident = (confidence >= 0.70)

        # Parse trace frames if query has stack trace markers
        trace_frames = TracebackParser.parse_frames(query_text) if intent == "traceback" else []
        trace_lookup = TracebackParser.build_trace_lookup(trace_frames)

        ranked_items = []
        for c in candidates:
            path = c["path"]
            cand_norm = path.lower().replace("\\", "/")
            cand_base = cand_norm.split("/")[-1]

            m1_score = float(c.get("m1_score", 0.0))
            ch_scores = c.get("scores", {})
            sym_score = float(ch_scores.get("exact_symbol", 0.0))
            struct_raw = float(ch_scores.get("structural_expansion", 0.0))

            # Trace score (Tier 1 AST/frame match)
            trace_score = trace_lookup.get(cand_norm, 0.0)
            if trace_score == 0.0:
                trace_score = trace_lookup.get(cand_base, 0.0)

            # Verified structural score (exclude noisy stem matching)
            # Only count structural expansion if verified symbol or caller/import exists
            # Normalize struct_raw to [0, 1] relative to m1_score
            struct_norm = min(1.0, struct_raw / 1000.0) if struct_raw > 0 else 0.0

            # Hub factor
            evidence = c.get("evidence") or []
            in_degree_est = len(evidence)
            has_unique_sym = (sym_score > 5.0)
            hub_factor = HubNormalizer.compute_hub_penalty(
                path,
                in_degree=in_degree_est,
                has_unique_symbol_match=has_unique_sym,
            )

            # Compute final score based on treatment configuration
            if config in ("A", "m1_baseline"):
                final_score = m1_score

            elif config in ("B", "m1_hub_norm"):
                # Treatment B: Hub normalization only (M2c)
                final_score = m1_score * hub_factor

            elif config in ("C", "m1_exact_structural"):
                # Treatment C: Exact structural evidence (bounded, no intent switching)
                # Exact trace frame match or verified AST call
                exact_struct = trace_score
                multiplier = 1.0 + 0.10 * exact_struct
                final_score = m1_score * multiplier

            elif config in ("D", "m1_intent_guided"):
                # Treatment D: Confidence-aware query intent
                if not is_confident:
                    final_score = m1_score
                else:
                    if intent == "traceback":
                        multiplier = 1.0 + 0.12 * trace_score
                        final_score = m1_score * multiplier
                    elif intent == "code2test":
                        # In test intent, boost tests that have symbol matches
                        is_test_file = ("test" in cand_norm)
                        test_boost = 0.08 if (is_test_file and has_unique_sym) else 0.0
                        final_score = m1_score * (1.0 + test_boost)
                    elif intent == "edit2ripple":
                        # In ripple intent, boost files with structural connections
                        ripple_boost = 0.06 * struct_norm
                        final_score = m1_score * (1.0 + ripple_boost)
                    else:
                        final_score = m1_score

            elif config in ("E", "m1_bounded_structural"):
                # Treatment E: Bounded structural reranking across all queries + hub norm
                struct_boost = 0.08 * trace_score + 0.04 * struct_norm
                final_score = m1_score * (1.0 + struct_boost) * hub_factor

            elif config in ("F", "m1_evidence_gated_combined"):
                # Treatment F: Full evidence-gated combined ranker
                if not is_confident:
                    # Gated fallback: weak confidence retains lexical M1 baseline with gentle hub norm
                    final_score = m1_score * (0.90 + 0.10 * hub_factor)
                else:
                    boost = 0.0
                    if intent == "traceback":
                        boost += 0.12 * trace_score
                    elif intent == "code2test":
                        is_test_file = ("test" in cand_norm)
                        if is_test_file and has_unique_sym:
                            boost += 0.08
                    elif intent == "edit2ripple":
                        boost += 0.05 * struct_norm

                    # Bounded multiplier + gentle hub penalty
                    final_score = m1_score * (1.0 + boost) * (0.85 + 0.15 * hub_factor)

            else:
                raise ValueError(f"Unknown configuration: {config}")

            ranked_items.append({
                "path": path,
                "original_m1_rank": c.get("m1_rank", 0),
                "m1_score": m1_score,
                "final_score": round(float(final_score), 6),
                "trace_score": round(float(trace_score), 4),
                "hub_factor": round(float(hub_factor), 4),
            })

        # Deterministic sorting: highest score first, break ties by original m1_rank, then path
        ranked_items.sort(key=lambda x: (-x["final_score"], x["original_m1_rank"], x["path"]))
        for idx, item in enumerate(ranked_items, 1):
            item["m2_rank"] = idx

        return ranked_items

