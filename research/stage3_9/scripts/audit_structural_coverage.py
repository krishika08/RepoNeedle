"""
Stage 3.9.4: Structural Coverage & Gold-Target Structural Validation.
Computes:
1. Call-Site Multiplicity: raw records vs unique directed edges vs duplicate citations by repo.
2. Provenance Separation: retrieval-relevant edge counts (Exact local, Scoped import, Receiver-bound, Heuristic).
3. AST Parse Coverage: files registered, parsed successfully, failed, structural graph eligibility, lexical fallback.
   Separation of segmented source truncation vs genuine Python syntax incompatibility.
4. Gold-Target Structural Coverage:
   - Queries with >= 1 gold file parsed successfully.
   - Queries with ALL gold files parsed successfully.
   - Queries with NO gold file available for symbol-level indexing.
   - Fraction of gold files containing >= 1 FunctionNode.
   - Breakdown by repository and task type.
5. Hub Analysis: Degree distribution and top 1% edge concentration.
Outputs:
  - research/stage3_9/scripts/structural_coverage_data.json
"""

import sys
import os
import json
import ast
import math
from pathlib import Path
from collections import defaultdict, Counter

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_9"

sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(STAGE_DIR / "prototypes"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl, target_gold_files
from python_lfcg import (
    PythonLFCGEngine,
    TIER_A_EXACT_AST,
    TIER_B_SCOPED_IMPORT,
    TIER_C_RECEIVER_BOUND,
    TIER_D_HEURISTIC_PATTERN,
)

PYTHON_REPOS = [
    "HypothesisWorks/hypothesis",
    "fastapi/fastapi",
    "huggingface/diffusers",
    "huggingface/transformers",
    "ipython/ipython",
    "numpy/numpy",
    "pallets/click",
    "pydantic/pydantic",
    "pypa/pip",
    "pytest-dev/pytest",
    "python/mypy",
    "scrapy/scrapy",
    "tox-dev/tox",
]

def run_structural_coverage_audit():
    # 1. Load manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_rows = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if r["repo"] in PYTHON_REPOS and r["repo"] not in manifest_rows:
                manifest_rows[r["repo"]] = r

    # 2. Load benchmark queries
    subsets_def = [
        ("code2test", ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl"),
        ("comment2context", ARB_DIR / "data" / "benchmark" / "v2_comment2context" / "samples.jsonl"),
        ("trace2code", ARB_DIR / "data" / "benchmark" / "v2_trace2code" / "samples.jsonl"),
        ("edit2ripple", ARB_DIR / "data" / "benchmark" / "v2_edit2ripple" / "samples.jsonl"),
    ]

    all_queries = []
    for sname, spath in subsets_def:
        for r in read_jsonl(spath):
            r["_subset_name"] = sname
            all_queries.append(r)

    py_queries = [q for q in all_queries if q["repo"] in PYTHON_REPOS]

    repo_gold_stats = defaultdict(lambda: {
        "queries_total": 0,
        "queries_at_least_one_parsed": 0,
        "queries_all_parsed": 0,
        "queries_none_parsed": 0,
        "gold_files_total": 0,
        "gold_files_parsed": 0,
        "gold_files_with_funcs": 0,
        "gold_files_with_edges": 0,
    })

    task_gold_stats = defaultdict(lambda: {
        "queries_total": 0,
        "queries_at_least_one_parsed": 0,
        "queries_all_parsed": 0,
        "queries_none_parsed": 0,
        "gold_files_total": 0,
        "gold_files_parsed": 0,
        "gold_files_with_funcs": 0,
        "gold_files_with_edges": 0,
    })

    repo_edge_multiplicity = {}
    repo_provenance_separation = {}
    repo_ast_coverage = {}
    repo_hub_stats = {}

    for repo in PYTHON_REPOS:
        mrow = manifest_rows.get(repo)
        if not mrow:
            continue
        chunks_file = ARB_DIR / mrow["chunks_path"]

        # Load clean files
        files = {}
        with open(chunks_file, "r", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                p = c.get("path", "")
                if not p.endswith(".py"):
                    continue
                if c.get("kind") == "file":
                    files[p] = c.get("text", "")
                elif p not in files or len(c.get("text", "")) > len(files[p]):
                    files[p] = c.get("text", "")

        engine = PythonLFCGEngine(repo_name=repo)
        parsed_files = set()
        failed_files = {}

        for p, code in files.items():
            try:
                ast.parse(code, filename=p)
                engine.parse_source(p, code)
                parsed_files.add(p)
            except SyntaxError as e:
                failed_files[p] = f"SyntaxError: {str(e)}"
                engine.file_metadata[engine.make_file_uri(p)] = {"syntax_error": True}
            except Exception as e:
                failed_files[p] = f"{type(e).__name__}: {str(e)}"
                engine.file_metadata[engine.make_file_uri(p)] = {"syntax_error": True}

        engine.resolve_all_calls()

        # Call-Site Multiplicity
        calls_edges = [e for e in engine.edges if e.edge_type == "CALLS"]
        raw_count = len(calls_edges)

        unique_pairs = Counter()
        for e in calls_edges:
            unique_pairs[(e.source_uri, e.target_uri)] += 1

        unique_count = len(unique_pairs)
        dup_citations = raw_count - unique_count
        max_multiplicity = max(unique_pairs.values()) if unique_pairs else 0

        repo_edge_multiplicity[repo] = {
            "raw_records": raw_count,
            "unique_edges": unique_count,
            "duplicate_citations": dup_citations,
            "max_multiplicity": max_multiplicity,
        }

        # Provenance separation
        prov_counts = Counter(e.provenance_tier for e in calls_edges)
        repo_provenance_separation[repo] = {
            "exact_ast": prov_counts[TIER_A_EXACT_AST],
            "scoped_import": prov_counts[TIER_B_SCOPED_IMPORT],
            "receiver_bound": prov_counts[TIER_C_RECEIVER_BOUND],
            "heuristic": prov_counts[TIER_D_HEURISTIC_PATTERN],
            "total_calls": raw_count,
        }

        # AST Parse Coverage & Truncation Classification
        truncation_errors = 0
        genuine_incompatibility = 0
        for p, err in failed_files.items():
            err_lower = err.lower()
            if "was never closed" in err_lower or "unterminated" in err_lower or "unexpected eof" in err_lower:
                truncation_errors += 1
            else:
                genuine_incompatibility += 1

        repo_ast_coverage[repo] = {
            "files_registered": len(files),
            "files_parsed_cleanly": len(parsed_files),
            "files_failed_parsing": len(failed_files),
            "segmented_truncation": truncation_errors,
            "genuine_incompatibility": genuine_incompatibility,
            "structural_graph_eligibility_pct": round(len(parsed_files) / len(files) * 100.0, 2) if files else 0.0,
            "lexical_fallback_coverage_pct": 100.0,
        }

        # Symbol Hubs
        in_deg = Counter()
        out_deg = Counter()
        for e in calls_edges:
            out_deg[e.source_uri] += 1
            in_deg[e.target_uri] += 1

        all_syms = set(in_deg.keys()) | set(out_deg.keys())
        top_1_pct_count = max(1, int(math.ceil(len(all_syms) * 0.01))) if all_syms else 0
        comb_deg = Counter({s: in_deg[s] + out_deg[s] for s in all_syms})
        top_1_pct_syms = set([s for s, _ in comb_deg.most_common(top_1_pct_count)])

        edges_in_top_1_pct = 0
        for s_uri, t_uri in unique_pairs.keys():
            if s_uri in top_1_pct_syms or t_uri in top_1_pct_syms:
                edges_in_top_1_pct += 1

        pct_edges_top_1 = (edges_in_top_1_pct / unique_count * 100.0) if unique_count else 0.0

        repo_hub_stats[repo] = {
            "active_symbols": len(all_syms),
            "top_1_pct_count": top_1_pct_count,
            "pct_edges_top_1_pct": round(pct_edges_top_1, 2),
            "max_in_deg": max(in_deg.values()) if in_deg else 0,
            "max_out_deg": max(out_deg.values()) if out_deg else 0,
        }

        # Query Gold Target Analysis
        repo_queries = [q for q in py_queries if q["repo"] == repo]
        for q in repo_queries:
            t_type = q["_subset_name"]
            g_files = target_gold_files(q)

            repo_gold_stats[repo]["queries_total"] += 1
            task_gold_stats[t_type]["queries_total"] += 1

            parsed_g_count = 0
            has_func_count = 0
            has_edge_count = 0

            for gf in g_files:
                repo_gold_stats[repo]["gold_files_total"] += 1
                task_gold_stats[t_type]["gold_files_total"] += 1

                if gf in parsed_files:
                    parsed_g_count += 1
                    repo_gold_stats[repo]["gold_files_parsed"] += 1
                    task_gold_stats[t_type]["gold_files_parsed"] += 1

                    gf_uri = engine.make_file_uri(gf)
                    funcs_in_gf = engine.functions_by_file.get(gf_uri, [])
                    if funcs_in_gf:
                        has_func_count += 1
                        repo_gold_stats[repo]["gold_files_with_funcs"] += 1
                        task_gold_stats[t_type]["gold_files_with_funcs"] += 1

                        if any(fn.uri in in_deg or fn.uri in out_deg for fn in funcs_in_gf):
                            has_edge_count += 1
                            repo_gold_stats[repo]["gold_files_with_edges"] += 1
                            task_gold_stats[t_type]["gold_files_with_edges"] += 1

            if parsed_g_count > 0:
                repo_gold_stats[repo]["queries_at_least_one_parsed"] += 1
                task_gold_stats[t_type]["queries_at_least_one_parsed"] += 1

            if parsed_g_count == len(g_files):
                repo_gold_stats[repo]["queries_all_parsed"] += 1
                task_gold_stats[t_type]["queries_all_parsed"] += 1

            if parsed_g_count == 0:
                repo_gold_stats[repo]["queries_none_parsed"] += 1
                task_gold_stats[t_type]["queries_none_parsed"] += 1

    summary = {
        "edge_multiplicity": repo_edge_multiplicity,
        "provenance_separation": repo_provenance_separation,
        "ast_coverage": repo_ast_coverage,
        "hub_stats": repo_hub_stats,
        "repo_gold_stats": dict(repo_gold_stats),
        "task_gold_stats": dict(task_gold_stats),
    }

    out_file = STAGE_DIR / "scripts" / "structural_coverage_data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Structural coverage data saved to {out_file}")
    return summary

if __name__ == "__main__":
    run_structural_coverage_audit()

