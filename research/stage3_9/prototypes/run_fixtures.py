"""
Runner script for isolated synthetic parser fixtures.
Runs Python, Go, Rust, TypeScript, JavaScript, and Java fixtures.
Validates extraction vs resolution separation and fail-closed resolution.
Generates research/stage3_9/prototypes/fixture_results.json.
"""

import os
import json
from lfcg_core import (
    LFCGExtractor,
    TIER_A_EXACT_AST,
    TIER_B_SCOPED_IMPORT,
    TIER_C_RECEIVER_BOUND,
    TIER_D_HEURISTIC_PATTERN,
    TIER_E_UNRESOLVED,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def run_all_fixtures():
    extractor = LFCGExtractor(repo_name="fixture_suite")
    results = {
        "languages": {},
        "summary": {
            "total_files": 0,
            "total_function_nodes": 0,
            "total_call_sites_extracted": 0,
            "total_resolutions_attempted": 0,
            "total_resolved": 0,
            "total_unresolved": 0,
            "total_calls_edges_emitted": 0,
            "total_contains_edges_emitted": 0,
        }
    }

    # 1. Python Fixture
    py_path = os.path.join(FIXTURES_DIR, "python_cases.py")
    with open(py_path, "r", encoding="utf-8") as f:
        py_code = f.read()
    extractor.parse_and_resolve_python("src/python_cases.py", py_code)

    # 2. Go Fixture
    go_path = os.path.join(FIXTURES_DIR, "go_cases.go")
    with open(go_path, "r", encoding="utf-8") as f:
        go_code = f.read()
    extractor.parse_and_resolve_go("src/go_cases.go", go_code)

    # 3. Rust Fixture
    rs_path = os.path.join(FIXTURES_DIR, "rust_cases.rs")
    with open(rs_path, "r", encoding="utf-8") as f:
        rs_code = f.read()
    extractor.parse_and_resolve_rust("src/rust_cases.rs", rs_code)

    # 4. TypeScript Fixture
    ts_path = os.path.join(FIXTURES_DIR, "ts_cases.ts")
    with open(ts_path, "r", encoding="utf-8") as f:
        ts_code = f.read()
    extractor.parse_and_resolve_ts_js("src/ts_cases.ts", ts_code, is_ts=True)

    # 5. JavaScript Fixture
    js_path = os.path.join(FIXTURES_DIR, "js_cases.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js_code = f.read()
    extractor.parse_and_resolve_ts_js("src/js_cases.js", js_code, is_ts=False)

    # 6. Java Fixture
    java_path = os.path.join(FIXTURES_DIR, "java_cases.java")
    with open(java_path, "r", encoding="utf-8") as f:
        java_code = f.read()
    extractor.parse_and_resolve_java("src/java_cases.java", java_code)

    # Compile Results by Language
    for file_uri, fnode in extractor.file_nodes.items():
        lang = fnode.language
        lang_funcs = [fn for fn in extractor.function_nodes.values() if fn.file_uri == file_uri]
        lang_extractions = [ex for ex in extractor.extractions if ex.caller_file_uri == file_uri]
        lang_resolutions = [r for r in extractor.resolutions if r.extraction.caller_file_uri == file_uri]
        lang_resolved = [r for r in lang_resolutions if r.is_resolved]
        lang_unresolved = [r for r in lang_resolutions if not r.is_resolved]

        # Breakdown by construct category
        by_category = {}
        for r in lang_resolutions:
            cat = r.extraction.construct_category
            if cat not in by_category:
                by_category[cat] = {
                    "extracted_count": 0,
                    "resolved_count": 0,
                    "unresolved_count": 0,
                    "methods_used": set(),
                    "statuses": set(),
                    "tiers": set(),
                }
            by_category[cat]["extracted_count"] += 1
            if r.is_resolved:
                by_category[cat]["resolved_count"] += 1
            else:
                by_category[cat]["unresolved_count"] += 1
            by_category[cat]["methods_used"].add(r.resolution_method)
            by_category[cat]["statuses"].add(r.resolution_status)
            by_category[cat]["tiers"].add(r.provenance_tier)

        for cat in by_category:
            by_category[cat]["methods_used"] = sorted(list(by_category[cat]["methods_used"]))
            by_category[cat]["statuses"] = sorted(list(by_category[cat]["statuses"]))
            by_category[cat]["tiers"] = sorted(list(by_category[cat]["tiers"]))

        results["languages"][lang] = {
            "filepath": fnode.filepath,
            "function_count": len(lang_funcs),
            "call_sites_extracted": len(lang_extractions),
            "resolutions_attempted": len(lang_resolutions),
            "resolved_count": len(lang_resolved),
            "unresolved_count": len(lang_unresolved),
            "construct_categories": by_category,
        }

    results["summary"]["total_files"] = len(extractor.file_nodes)
    results["summary"]["total_function_nodes"] = len(extractor.function_nodes)
    results["summary"]["total_call_sites_extracted"] = len(extractor.extractions)
    results["summary"]["total_resolutions_attempted"] = len(extractor.resolutions)
    results["summary"]["total_resolved"] = sum(1 for r in extractor.resolutions if r.is_resolved)
    results["summary"]["total_unresolved"] = sum(1 for r in extractor.resolutions if not r.is_resolved)
    results["summary"]["total_contains_edges_emitted"] = sum(1 for e in extractor.edges if e.edge_type == "CONTAINS")
    results["summary"]["total_calls_edges_emitted"] = sum(1 for e in extractor.edges if e.edge_type == "CALLS")

    # Serialize
    out_path = os.path.join(os.path.dirname(__file__), "fixture_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("=== LFCG Synthetic Fixture Validation Summary ===")
    print(f"Total Files Analyzed: {results['summary']['total_files']}")
    print(f"Total Function Nodes Registered: {results['summary']['total_function_nodes']}")
    print(f"Total Call Sites Extracted: {results['summary']['total_call_sites_extracted']}")
    print(f"Total Call Target Resolutions: {results['summary']['total_resolutions_attempted']}")
    print(f"  - Resolved Calls: {results['summary']['total_resolved']}")
    print(f"  - Unresolved Calls (Fail-Closed / Filtered): {results['summary']['total_unresolved']}")
    print(f"Edges Emitted:")
    print(f"  - CONTAINS: {results['summary']['total_contains_edges_emitted']}")
    print(f"  - CALLS: {results['summary']['total_calls_edges_emitted']}")
    print(f"\nLanguage Details:")
    for lang, details in results["languages"].items():
        print(f"  [{lang}]: {details['function_count']} funcs, {details['call_sites_extracted']} calls extracted, {details['resolved_count']} resolved, {details['unresolved_count']} safe unresolved")
        for cat, cinfo in details["construct_categories"].items():
            print(f"    - {cat}: {cinfo['extracted_count']} calls -> {cinfo['resolved_count']} resolved, {cinfo['unresolved_count']} unresolved ({cinfo['methods_used']})")

    sha = extractor.get_serialized_sha256()
    print(f"\nDeterministic Serialization SHA-256 Digest:\n  {sha}")
    return results

if __name__ == "__main__":
    run_all_fixtures()

