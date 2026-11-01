import math
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple


class QueryIntentDetector:
    """
    Infers intent from raw query text without oracle task labels (AUTO mode).
    Identifies:
    - traceback / error diagnosis
    - code2test / test discovery
    - edit2ripple / ripple dependency
    - comment2context / semantic concept lookup
    """

    TRACE_PATTERNS = [
        re.compile(r"Traceback\s+\(most\s+recent\s+call\s+last\)", re.IGNORECASE),
        re.compile(r"File\s+[\"'][^\"']+[\"'],\s+line\s+\d+", re.IGNORECASE),
        re.compile(r"\bpanic:\s+", re.IGNORECASE),
        re.compile(r"[\w\.\-/]+\.go:\d+\s+\+0x[0-9a-fA-F]+"),
        re.compile(r"at\s+[\w\.\-/]+\.rs:\d+(?::\d+)?"),
        re.compile(r"at\s+[\w\.\-/]+\.[jt]sx?:\d+:\d+"),
        re.compile(r"\b(?:NullPointerException|IndexOutOfBoundsException|KeyError|ValueError|TypeError|AttributeError|RuntimeError)\b"),
        re.compile(r"stack\s+trace", re.IGNORECASE),
    ]

    TEST_PATTERNS = [
        re.compile(r"\b(?:find|write|unit|integration|coverage)\s+tests?\b", re.IGNORECASE),
        re.compile(r"\btests?\s+(?:for|covering|validating|exercising)\b", re.IGNORECASE),
        re.compile(r"\b(?:test_cases?|test_suite|test_function)\b", re.IGNORECASE),
        re.compile(r"\btest_\w+\b"),
        re.compile(r"\b\w+_test\b"),
        re.compile(r"\bassert(?:s|ion|Equal|True|False|Raises)?\b"),
    ]

    RIPPLE_PATTERNS = [
        re.compile(r"\b(?:ripple|side[- ]effects?|impact|dependents?)\b", re.IGNORECASE),
        re.compile(r"\b(?:modify|modifying|refactor|refactoring|renamed?|changing)\b", re.IGNORECASE),
        re.compile(r"\b(?:called\s+by|callers?\s+of|importers?\s+of|downstream)\b", re.IGNORECASE),
        re.compile(r"\b(?:edit|edits|patch|patching)\b", re.IGNORECASE),
    ]

    @classmethod
    def detect_intent(cls, query_text: str) -> str:
        trace_matches = sum(1 for p in cls.TRACE_PATTERNS if p.search(query_text))
        if trace_matches >= 1:
            return "traceback"

        test_matches = sum(1 for p in cls.TEST_PATTERNS if p.search(query_text))
        ripple_matches = sum(1 for p in cls.RIPPLE_PATTERNS if p.search(query_text))

        if test_matches >= 1 and test_matches >= ripple_matches:
            return "code2test"

        if ripple_matches >= 1:
            return "edit2ripple"

        return "comment2context"


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


class TestLinkageAnalyzer:
    pass


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

        if has_unique_symbol_match:
            base_penalty = base_penalty + (1.0 - base_penalty) * 0.85

        return max(0.1, min(1.0, base_penalty))


class QueryConditionedRanker:
    def __init__(self, mode: str = "auto"):
        self.mode = mode.lower()

    def rank_candidates(
        self,
        query_snapshot: Dict[str, Any],
        config_name: str = "m2_full_auto",
    ) -> List[Dict[str, Any]]:
        query_text = query_snapshot["query_text"]
        track = query_snapshot["track"]
        candidates = query_snapshot["candidates"]

        if not candidates:
            return []

        if config_name == "m2_full_task_conditioned":
            intent = track
        elif config_name == "m1_baseline":
            intent = "none"
        else:
            intent = QueryIntentDetector.detect_intent(query_text)

        # 1. Precompute trace lookup dictionary ONCE
        trace_frames = TracebackParser.parse_frames(query_text) if intent in ("traceback", "v2_trace2code") else []
        trace_lookup = TracebackParser.build_trace_lookup(trace_frames)

        # 2. Precompute test linkage stem lookups ONCE (O(1) hash lookups)
        raw_tokens = re.findall(r"[A-Za-z0-9_\-\./]+", query_text[:3000])
        query_stems = set()
        test_stem_targets = set()
        for t in raw_tokens:
            t_low = t.lower()
            base = t_low.split("/")[-1]
            stem = base.rsplit(".", 1)[0]
            query_stems.add(stem)
            test_stem_targets.add(f"test_{stem}")
            test_stem_targets.add(f"{stem}_test")
            test_stem_targets.add(f"{stem}test")

        is_target_test = intent in ("code2test", "v2_code2test")

        ranked_items = []
        for c in candidates:
            path = c["path"]
            cand_norm = path.lower().replace("\\", "/")
            cand_base = cand_norm.split("/")[-1]
            cand_stem = cand_base.rsplit(".", 1)[0]

            m1_score = c.get("m1_score", 0.0)
            ch_scores = c.get("scores", {})
            sym_score = ch_scores.get("exact_symbol", 0.0)
            bm25_score = ch_scores.get("field_bm25", 0.0)
            struct_score = ch_scores.get("structural_expansion", 0.0)

            # O(1) test linkage evaluation
            test_score = 0.0
            if is_target_test:
                if "test" in cand_norm:
                    if cand_stem in test_stem_targets:
                        test_score = 0.85
                    elif cand_stem in query_stems:
                        test_score = 0.75
                    else:
                        test_score = 0.15
            else:
                if cand_stem in query_stems:
                    test_score = 0.50

            # O(1) trace score evaluation
            trace_score = trace_lookup.get(cand_norm, 0.0)
            if trace_score == 0.0:
                trace_score = trace_lookup.get(cand_base, 0.0)

            # Hub factor
            evidence = c.get("evidence") or []
            in_degree_est = len(evidence)
            has_unique_sym = (sym_score > 0.8)
            hub_factor = HubNormalizer.compute_hub_penalty(path, in_degree=in_degree_est, has_unique_symbol_match=has_unique_sym)

            if config_name == "m1_baseline":
                final_score = m1_score

            elif config_name == "m2a_test_linkage_only":
                final_score = 0.60 * m1_score + 0.40 * test_score

            elif config_name == "m2b_traceback_only":
                final_score = 0.50 * m1_score + 0.50 * trace_score

            elif config_name == "m2c_hub_norm_only":
                final_score = m1_score * hub_factor

            elif config_name == "m2d_combined_structural":
                final_score = (0.40 * m1_score + 0.25 * test_score + 0.25 * trace_score + 0.10 * struct_score) * (0.7 + 0.3 * hub_factor)

            elif config_name == "m2e_rrf":
                rrf_m1 = 1.0 / (60.0 + c.get("m1_rank", 100))
                rrf_struct = (test_score + trace_score + struct_score) / 60.0
                final_score = rrf_m1 + rrf_struct

            elif config_name in ("m2_full_auto", "m2_full_task_conditioned"):
                if intent in ("traceback", "v2_trace2code"):
                    base = 0.30 * m1_score + 0.50 * trace_score + 0.15 * sym_score + 0.05 * struct_score
                elif intent in ("code2test", "v2_code2test"):
                    base = 0.35 * m1_score + 0.45 * test_score + 0.10 * sym_score + 0.10 * struct_score
                elif intent in ("edit2ripple", "v2_edit2ripple"):
                    base = 0.40 * m1_score + 0.30 * struct_score + 0.15 * test_score + 0.15 * sym_score
                else:
                    base = 0.60 * m1_score + 0.20 * sym_score + 0.10 * struct_score + 0.10 * bm25_score

                final_score = base * (0.65 + 0.35 * hub_factor)

            else:
                raise ValueError(f"Unknown config: {config_name}")

            ranked_items.append({
                "path": path,
                "original_m1_rank": c.get("m1_rank", 0),
                "m1_score": m1_score,
                "final_score": round(float(final_score), 6),
                "test_score": round(float(test_score), 4),
                "trace_score": round(float(trace_score), 4),
                "hub_factor": round(float(hub_factor), 4),
            })

        ranked_items.sort(key=lambda x: (-x["final_score"], x["original_m1_rank"], x["path"]))
        for idx, item in enumerate(ranked_items, 1):
            item["m2_rank"] = idx

        return ranked_items
