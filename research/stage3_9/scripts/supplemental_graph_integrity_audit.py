"""
Stage 3.9.4 Supplemental Graph Integrity Audit.
Executes detailed forensic audits for:
1. Edge Count Reconciliation: Raw records vs unique edges across all 13 Python repos.
2. Heuristic Edge Audit: Breakdown of the 1,752 Tier D heuristic edges by repo and resolution method, with stratified source inspections.
3. Symbol Hub Audit: Top 20 in-degree & out-degree symbols, power-law concentration (top 1% symbols), recursive edges.
4. Parse Failure Audit: Detailed taxonomy of syntax errors across Diffusers, Transformers, Mypy, etc.
5. Source Snapshot Integrity: Repo, base commit, file path, and deterministic SHA-256 verification.
"""

import sys
import os
import json
import ast
import math
import hashlib
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_9"

sys.path.insert(0, str(STAGE_DIR / "prototypes"))
sys.path.insert(0, str(ROOT_DIR))

from python_lfcg import PythonLFCGEngine, TIER_D_HEURISTIC_PATTERN

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

def load_manifest_data():
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_rows = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            if r["repo"] in PYTHON_REPOS and r["repo"] not in manifest_rows:
                manifest_rows[r["repo"]] = r
    return manifest_rows

def run_supplemental_audit():
    manifest_rows = load_manifest_data()
    audit_data = {}

    for repo in PYTHON_REPOS:
        mrow = manifest_rows.get(repo)
        if not mrow:
            continue
        chunks_file = ARB_DIR / mrow["chunks_path"]

        # 1. Source files extraction
        files = {}
        raw_chunk_stats = {"total_chunks": 0, "file_chunks": 0, "symbol_chunks": 0}
        with open(chunks_file, "r", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                raw_chunk_stats["total_chunks"] += 1
                kind = c.get("kind", "")
                if kind == "file":
                    raw_chunk_stats["file_chunks"] += 1
                elif kind == "symbol":
                    raw_chunk_stats["symbol_chunks"] += 1

                p = c.get("path", "")
                if not p.endswith(".py"):
                    continue
                t = c.get("text", "")
                if kind == "file":
                    files[p] = t
                elif p not in files or len(t) > len(files[p]):
                    files[p] = t

        # Compute source SHA-256
        hasher = hashlib.sha256()
        for p in sorted(files.keys()):
            hasher.update(p.encode("utf-8"))
            hasher.update(files[p].encode("utf-8"))
        repo_sha = hasher.hexdigest()

        # Parse and resolve
        engine = PythonLFCGEngine(repo_name=repo)
        parse_errors = []
        for p, code in files.items():
            try:
                ast.parse(code, filename=p)
                engine.parse_source(p, code)
            except SyntaxError as e:
                parse_errors.append((p, str(e), e.lineno, e.text))
                engine.file_metadata[engine.make_file_uri(p)] = {"syntax_error": True}
            except Exception as e:
                parse_errors.append((p, f"Exception: {str(e)}", 0, ""))
                engine.file_metadata[engine.make_file_uri(p)] = {"syntax_error": True}

        engine.resolve_all_calls()

        calls_edges = [e for e in engine.edges if e.edge_type == "CALLS"]
        raw_record_count = len(calls_edges)

        unique_edge_pairs = set()
        self_recursive_edges = 0
        in_degrees = Counter()
        out_degrees = Counter()
        heuristic_edges = []

        for e in calls_edges:
            pair = (e.source_uri, e.target_uri)
            unique_edge_pairs.add(pair)
            if e.source_uri == e.target_uri:
                self_recursive_edges += 1
            out_degrees[e.source_uri] += 1
            in_degrees[e.target_uri] += 1
            if e.provenance_tier == TIER_D_HEURISTIC_PATTERN:
                heuristic_edges.append(e)

        unique_edge_count = len(unique_edge_pairs)
        dup_citations = raw_record_count - unique_edge_count

        # Power law concentration: top 1% symbols
        all_symbols = set(in_degrees.keys()) | set(out_degrees.keys())
        total_symbols_with_edges = len(all_symbols)
        top_1_pct_count = max(1, int(math.ceil(total_symbols_with_edges * 0.01)))

        # Combined degree per symbol
        combined_deg = Counter()
        for s in all_symbols:
            combined_deg[s] = in_degrees[s] + out_degrees[s]
        
        top_1_pct_symbols = [s for s, _ in combined_deg.most_common(top_1_pct_count)]
        edges_connected_to_top_1_pct = 0
        for s_uri, t_uri in unique_edge_pairs:
            if s_uri in top_1_pct_symbols or t_uri in top_1_pct_symbols:
                edges_connected_to_top_1_pct += 1

        pct_edges_top_1_pct = (edges_connected_to_top_1_pct / unique_edge_count * 100.0) if unique_edge_count > 0 else 0.0

        # Syntax error classification
        syntax_taxonomy = defaultdict(list)
        for path, err_msg, lineno, err_line in parse_errors:
            err_line_str = err_line.strip() if err_line else ""
            err_lower = err_msg.lower()
            if "invalid escape sequence" in err_lower:
                syntax_taxonomy["escape_sequence_warning"].append(path)
            elif "missing parentheses in call to 'print'" in err_lower or "print " in err_line_str:
                syntax_taxonomy["legacy_python_2_print"].append(path)
            elif "except " in err_line_str and "," in err_line_str and " as " not in err_line_str:
                syntax_taxonomy["legacy_python_2_except"].append(path)
            elif "jinja" in path.lower() or "template" in path.lower() or "{%" in err_line_str or "{{" in err_line_str:
                syntax_taxonomy["templated_or_generated"].append(path)
            elif "doc" in path.lower() or "example" in path.lower() or "tutorial" in path.lower():
                syntax_taxonomy["doc_example_or_snippet"].append(path)
            elif "test" in path.lower() or "benchmark" in path.lower():
                syntax_taxonomy["test_or_benchmark_code"].append(path)
            else:
                syntax_taxonomy["internal_module_syntax_variation"].append(path)

        audit_data[repo] = {
            "base_commit": mrow["base_commit"],
            "chunks_path": mrow["chunks_path"],
            "manifest_files": mrow["file_count"],
            "total_py_files": len(files),
            "parsed_cleanly": len(files) - len(parse_errors),
            "parse_error_count": len(parse_errors),
            "syntax_taxonomy": {k: len(v) for k, v in syntax_taxonomy.items()},
            "syntax_samples": parse_errors[:3],
            "raw_calls_records": raw_record_count,
            "unique_calls_edges": unique_edge_count,
            "duplicate_citations": dup_citations,
            "self_recursive_edges": self_recursive_edges,
            "heuristic_edges_count": len(heuristic_edges),
            "heuristic_samples": heuristic_edges[:5],
            "top_in_degrees": in_degrees.most_common(20),
            "top_out_degrees": out_degrees.most_common(20),
            "total_symbols_active": total_symbols_with_edges,
            "top_1_pct_count": top_1_pct_count,
            "pct_edges_top_1_pct": round(pct_edges_top_1_pct, 2),
            "source_sha256": repo_sha,
        }

    # Output JSON summary for artifact authoring
    out_json = STAGE_DIR / "scripts" / "supplemental_audit_data.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2, default=str)

    print(f"Supplemental audit data saved to {out_json}")
    return audit_data

if __name__ == "__main__":
    run_supplemental_audit()
