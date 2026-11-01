"""
Stage 3.9.4 Phase C: Comprehensive Real Repository Graph Coverage Profiler.
Profiles all 13 primary Python repositories in the ARB v2 benchmark:
  1. HypothesisWorks/hypothesis
  2. fastapi/fastapi
  3. huggingface/diffusers
  4. huggingface/transformers
  5. ipython/ipython
  6. numpy/numpy
  7. pallets/click
  8. pydantic/pydantic
  9. pypa/pip
  10. pytest-dev/pytest
  11. python/mypy
  12. scrapy/scrapy
  13. tox-dev/tox

Measures all 14 Phase C metrics and outputs:
  - research/stage3_9/PER_REPOSITORY_COVERAGE.csv
"""

import os
import sys
import json
import csv
import glob
from pathlib import Path
from collections import defaultdict, Counter

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_9"
sys.path.insert(0, str(STAGE_DIR / "prototypes"))
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ARB_DIR / "src"))

from python_lfcg import PythonLFCGEngine, TIER_E_UNRESOLVED
from agent_retrieval_bench.baseline import target_gold_files, read_jsonl

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

def load_queries_by_repo():
    subsets = ["v2_code2test", "v2_comment2context", "v2_trace2code", "v2_edit2ripple"]
    queries_by_repo = defaultdict(list)
    for sub in subsets:
        fpath = ARB_DIR / "data" / "benchmark" / sub / "samples.jsonl"
        if not fpath.exists():
            continue
        for line in open(fpath, encoding="utf-8"):
            if line.strip():
                rec = json.loads(line)
                queries_by_repo[rec["repo"]].append(rec)
    return queries_by_repo

def get_repo_chunks_files(repo_name: str) -> list[Path]:
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    matched_paths = []
    if manifest_path.exists():
        for line in open(manifest_path, encoding="utf-8"):
            if line.strip():
                row = json.loads(line)
                if row.get("repo") == repo_name:
                    p = ARB_DIR / row["chunks_path"]
                    if p.exists():
                        matched_paths.append(p)
    if not matched_paths:
        # Fallback search across corpus dirs
        repo_slug = repo_name.replace("/", "__")
        candidates = list(ARB_DIR.glob(f"data/corpus/*/{repo_slug}/*.chunks.jsonl"))
        matched_paths.extend(candidates)
    return matched_paths

def profile_repository(repo_name: str, queries: list) -> dict:
    print(f"\nProfiling {repo_name}...")
    chunk_files = get_repo_chunks_files(repo_name)
    if not chunk_files:
        print(f"  Warning: No chunks found for {repo_name}")
        return {}

    # Load clean Python files from first available corpus split
    target_chunk_file = chunk_files[0]
    print(f"  Using chunks file: {target_chunk_file.name}")
    
    # We collect files: first check kind == 'file', if absent, fall back to longest chunk
    files_by_path = {}
    with open(target_chunk_file, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            p = c.get("path", "")
            if not p.endswith(".py"):
                continue
            t = c.get("text", "")
            kind = c.get("kind", "")
            if kind == "file":
                files_by_path[p] = t
            elif p not in files_by_path or len(t) > len(files_by_path[p]):
                files_by_path[p] = t

    eligible_files = len(files_by_path)
    engine = PythonLFCGEngine(repo_name=repo_name)

    parsed_successfully = 0
    parse_failures = 0
    failure_reasons = []

    for path, code in files_by_path.items():
        try:
            engine.parse_source(path, code)
            meta = engine.file_metadata.get(engine.make_file_uri(path), {})
            if meta.get("syntax_error", False):
                parse_failures += 1
                failure_reasons.append(f"{path}: SyntaxError")
            else:
                parsed_successfully += 1
        except Exception as e:
            parse_failures += 1
            failure_reasons.append(f"{path}: {type(e).__name__}")

    # Files containing >= 1 function
    files_with_funcs = set()
    for fn in engine.function_nodes.values():
        files_with_funcs.add(fn.file_uri)
    files_containing_at_least_one_func = len(files_with_funcs)
    total_funcs = len(engine.function_nodes)

    # Pass 2: Call resolution
    engine.resolve_all_calls()
    total_extractions = len(engine.extractions)

    calls_edges = [e for e in engine.edges if e.edge_type == "CALLS"]
    local_resolved = 0
    cross_file_resolved = 0
    ambiguous_count = 0
    unresolved_count = 0

    in_degrees = Counter()
    out_degrees = Counter()
    unique_targets = set()

    # Track files with symbol evidence (has function nodes involved in calls or contains)
    files_with_symbol_evidence = set()
    for e in engine.edges:
        if e.edge_type == "CALLS":
            # Extract file from source_uri and target_uri
            src_file = e.source_uri.split("#")[0].replace("func://", "file://")
            tgt_file = e.target_uri.split("#")[0].replace("func://", "file://")
            files_with_symbol_evidence.add(src_file)
            files_with_symbol_evidence.add(tgt_file)
            unique_targets.add(e.target_uri)
            out_degrees[e.source_uri] += 1
            in_degrees[e.target_uri] += 1
            if src_file == tgt_file:
                local_resolved += 1
            else:
                cross_file_resolved += 1

    for r in engine.resolutions:
        if not r.is_resolved or r.provenance_tier == TIER_E_UNRESOLVED:
            unresolved_count += 1
        if r.candidate_count > 1:
            ambiguous_count += 1

    max_in = max(in_degrees.values()) if in_degrees else 0
    max_out = max(out_degrees.values()) if out_degrees else 0
    pct_files_with_evidence = (len(files_with_symbol_evidence) / eligible_files * 100.0) if eligible_files > 0 else 0.0

    # Query level evidence check: check if any gold file or query path has symbol evidence
    queries_total = len(queries)
    queries_with_evidence = 0
    for q in queries:
        gold_files = target_gold_files(q)
        has_ev = False
        for gf in gold_files:
            gf_uri = engine.make_file_uri(gf)
            if gf_uri in files_with_symbol_evidence or gf_uri in engine.file_nodes:
                funcs_in_gf = [fn.uri for fn in engine.functions_by_file.get(gf_uri, [])]
                if any(f in in_degrees or f in out_degrees for f in funcs_in_gf):
                    has_ev = True
                    break
        if has_ev:
            queries_with_evidence += 1

    pct_queries_with_evidence = (queries_with_evidence / queries_total * 100.0) if queries_total > 0 else 0.0

    print(f"  Files: {eligible_files} | Funcs: {total_funcs} | Extracted: {total_extractions} | CALLS: {len(calls_edges)}")
    print(f"  Local: {local_resolved} | Cross-File: {cross_file_resolved} | Unresolved: {unresolved_count}")
    print(f"  Queries: {queries_total} (with symbol evidence: {queries_with_evidence} = {pct_queries_with_evidence:.1f}%)")

    return {
        "repo": repo_name,
        "eligible_files": eligible_files,
        "parsed_successfully": parsed_successfully,
        "parse_failures": parse_failures,
        "failure_reasons": "; ".join(failure_reasons[:3]) if failure_reasons else "None",
        "files_with_functions": files_containing_at_least_one_func,
        "function_nodes": total_funcs,
        "call_sites_extracted": total_extractions,
        "local_calls_resolved": local_resolved,
        "cross_file_calls_resolved": cross_file_resolved,
        "ambiguous_candidates": ambiguous_count,
        "unresolved_calls": unresolved_count,
        "final_calls_edges": len(calls_edges),
        "unique_targets": len(unique_targets),
        "max_in_degree": max_in,
        "max_out_degree": max_out,
        "pct_files_with_symbol_evidence": round(pct_files_with_evidence, 2),
        "queries_total": queries_total,
        "queries_with_symbol_evidence": queries_with_evidence,
        "pct_queries_with_symbol_evidence": round(pct_queries_with_evidence, 2),
    }

def main():
    queries_by_repo = load_queries_by_repo()
    results = []
    for r in PYTHON_REPOS:
        q_list = queries_by_repo.get(r, [])
        res = profile_repository(r, q_list)
        if res:
            results.append(res)

    out_csv = STAGE_DIR / "PER_REPOSITORY_COVERAGE.csv"
    fieldnames = [
        "repo",
        "eligible_files",
        "parsed_successfully",
        "parse_failures",
        "failure_reasons",
        "files_with_functions",
        "function_nodes",
        "call_sites_extracted",
        "local_calls_resolved",
        "cross_file_calls_resolved",
        "ambiguous_candidates",
        "unresolved_calls",
        "final_calls_edges",
        "unique_targets",
        "max_in_degree",
        "max_out_degree",
        "pct_files_with_symbol_evidence",
        "queries_total",
        "queries_with_symbol_evidence",
        "pct_queries_with_symbol_evidence",
    ]

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    print(f"\nWrote repository coverage metrics to {out_csv}")

if __name__ == "__main__":
    main()
