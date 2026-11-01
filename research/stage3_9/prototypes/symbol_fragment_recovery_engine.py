"""
RepoNeedle Stage 3.9.4.1: Symbol Fragment Recovery & Safe Parsing Prototype.
Analyzes and extracts function-level representation from original kind=='symbol' chunks.

Categorization:
  - Complete function definitions (ast.FunctionDef)
  - Complete async functions (ast.AsyncFunctionDef)
  - Methods with missing class context
  - Class declarations (ast.ClassDef)
  - Partial code fragments (control blocks, expressions)
  - Truncated functions (unclosed blocks / syntax errors)
  - Duplicate symbols

Preserves:
  - repo, base_commit, path, symbol, start_line, end_line, fragment_sha256
Resolution Policy:
  - Fragment-local exact calls (local helpers / recursion)
  - Calls requiring unavailable module imports (marked UNRESOLVED)
  - Calls requiring unavailable class scope (marked UNRESOLVED)
  - Calls requiring runtime/type info (marked UNRESOLVED)

Evaluates coverage impact across:
  - All 13 Python repositories
  - All 104 Python queries (code2test, comment2context, edit2ripple, trace2code)
Outputs:
  - research/stage3_9/scripts/symbol_fragment_recovery_results.json
"""

import sys
import os
import json
import ast
import textwrap
import hashlib
from pathlib import Path
from collections import defaultdict, Counter

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
STAGE_DIR = ROOT_DIR / "research" / "stage3_9"

sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(STAGE_DIR / "prototypes"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl, target_gold_files

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

def load_py_queries():
    subsets_def = [
        ("code2test", ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl"),
        ("comment2context", ARB_DIR / "data" / "benchmark" / "v2_comment2context" / "samples.jsonl"),
        ("trace2code", ARB_DIR / "data" / "benchmark" / "v2_trace2code" / "samples.jsonl"),
        ("edit2ripple", ARB_DIR / "data" / "benchmark" / "v2_edit2ripple" / "samples.jsonl"),
    ]
    all_q = []
    for sname, spath in subsets_def:
        for r in read_jsonl(spath):
            if r["repo"] in PYTHON_REPOS:
                r["_subset_name"] = sname
                all_q.append(r)
    return all_q

def analyze_symbol_fragments():
    manifest_rows = load_manifest_data()
    py_queries = load_py_queries()

    repo_fragment_analysis = {}
    repo_recovered_funcs = defaultdict(lambda: defaultdict(list)) # repo -> path -> list of recovered funcs
    repo_fragment_calls = defaultdict(list)

    total_chunks_inspected = 0
    total_categories = Counter()

    for repo in PYTHON_REPOS:
        mrow = manifest_rows.get(repo)
        if not mrow:
            continue
        base_commit = mrow["base_commit"]
        chunks_file = ARB_DIR / mrow["chunks_path"]

        repo_cat = Counter()
        seen_symbols = set()
        duplicate_symbols = 0

        with open(chunks_file, "r", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                if c.get("kind") != "symbol":
                    continue
                p = c.get("path", "")
                if not p.endswith(".py"):
                    continue

                total_chunks_inspected += 1
                sym_id = f"{p}#{c.get('symbol', '')}"
                if sym_id in seen_symbols:
                    duplicate_symbols += 1
                seen_symbols.add(sym_id)

                raw_text = c.get("text", "")
                dedented = textwrap.dedent(raw_text).strip()
                s_line = c.get("start_line", 0)
                e_line = c.get("end_line", 0)

                # Try parsing
                parsed = False
                try:
                    tree = ast.parse(dedented)
                    if len(tree.body) > 0:
                        first = tree.body[0]
                        if isinstance(first, ast.FunctionDef):
                            # Check if method with self/cls as first arg
                            is_method = False
                            if first.args.args and first.args.args[0].arg in ("self", "cls"):
                                is_method = True
                                repo_cat["methods_missing_class_context"] += 1
                            else:
                                repo_cat["complete_function_def"] += 1

                            func_rec = {
                                "repo": repo,
                                "base_commit": base_commit,
                                "path": p,
                                "name": first.name,
                                "symbol": c.get("symbol", first.name),
                                "is_async": False,
                                "is_method": is_method,
                                "start_line": s_line,
                                "end_line": e_line,
                                "fragment_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16],
                                "tree": first,
                            }
                            repo_recovered_funcs[repo][p].append(func_rec)
                            parsed = True
                        elif isinstance(first, ast.AsyncFunctionDef):
                            repo_cat["complete_async_function_def"] += 1
                            func_rec = {
                                "repo": repo,
                                "base_commit": base_commit,
                                "path": p,
                                "name": first.name,
                                "symbol": c.get("symbol", first.name),
                                "is_async": True,
                                "is_method": False,
                                "start_line": s_line,
                                "end_line": e_line,
                                "fragment_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16],
                                "tree": first,
                            }
                            repo_recovered_funcs[repo][p].append(func_rec)
                            parsed = True
                        elif isinstance(first, ast.ClassDef):
                            repo_cat["class_declarations"] += 1
                            # Check if functions inside class declaration can be recovered
                            for sub in first.body:
                                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    func_rec = {
                                        "repo": repo,
                                        "base_commit": base_commit,
                                        "path": p,
                                        "name": sub.name,
                                        "symbol": f"{first.name}.{sub.name}",
                                        "parent_class": first.name,
                                        "is_async": isinstance(sub, ast.AsyncFunctionDef),
                                        "is_method": True,
                                        "start_line": s_line + getattr(sub, "lineno", 1) - 1,
                                        "end_line": s_line + getattr(sub, "end_lineno", getattr(sub, "lineno", 1)) - 1,
                                        "fragment_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16],
                                        "tree": sub,
                                    }
                                    repo_recovered_funcs[repo][p].append(func_rec)
                        else:
                            repo_cat["partial_code_fragments"] += 1
                    else:
                        repo_cat["partial_code_fragments"] += 1
                except (SyntaxError, IndentationError):
                    repo_cat["truncated_functions_or_syntax_error"] += 1

        repo_cat["duplicate_symbols"] = duplicate_symbols
        for k, v in repo_cat.items():
            total_categories[k] += v

        repo_fragment_analysis[repo] = dict(repo_cat)

    # Resolution Policy & Call Extraction
    resolution_counts = Counter()
    for repo, files_dict in repo_recovered_funcs.items():
        for path, funcs in files_dict.items():
            for fn in funcs:
                tree_node = fn["tree"]
                caller_uri = f"func://{repo}/{path}#{fn['symbol']}"

                # Local functions inside the fragment
                local_inner_funcs = set()
                for sub in ast.walk(tree_node):
                    if sub != tree_node and isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        local_inner_funcs.add(sub.name)

                # Extract calls inside the fragment
                for node in ast.walk(tree_node):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            callee_name = node.func.id
                            # 1. Fragment-local exact calls (calls inner function or self recursion)
                            if callee_name == fn["name"]:
                                resolution_counts["fragment_local_recursive_call"] += 1
                                repo_fragment_calls[repo].append((caller_uri, caller_uri, "TIER_A_EXACT_AST"))
                            elif callee_name in local_inner_funcs:
                                resolution_counts["fragment_local_nested_call"] += 1
                                target_uri = f"func://{repo}/{path}#{fn['symbol']}.{callee_name}"
                                repo_fragment_calls[repo].append((caller_uri, target_uri, "TIER_A_EXACT_AST"))
                            else:
                                # Without module import table, cannot verify if name is imported
                                resolution_counts["unresolved_unavailable_module_imports"] += 1
                        elif isinstance(node.func, ast.Attribute):
                            # Method call: without class hierarchy or type annotations
                            if node.func.attr == "self":
                                resolution_counts["unresolved_unavailable_class_scope"] += 1
                            else:
                                resolution_counts["unresolved_runtime_or_type_info"] += 1
                        else:
                            resolution_counts["unresolved_dynamic_dispatch"] += 1

    # Gold Target Coverage Recalculation (Before vs After)
    # Load previously audited baseline gold coverage
    base_audit = json.load(open(STAGE_DIR / "scripts" / "structural_coverage_data.json"))
    base_repo_gold = base_audit["repo_gold_stats"]
    base_task_gold = base_audit["task_gold_stats"]

    # Calculate recovered gold coverage
    recovered_repo_gold = defaultdict(lambda: {
        "queries_total": 0,
        "before_parsed_queries": 0,
        "after_parsed_queries": 0,
        "gold_files_total": 0,
        "before_parsed_gold_files": 0,
        "after_parsed_gold_files": 0,
        "recovered_gold_files_with_funcs": 0,
    })

    recovered_task_gold = defaultdict(lambda: {
        "queries_total": 0,
        "before_parsed_queries": 0,
        "after_parsed_queries": 0,
        "gold_files_total": 0,
        "before_parsed_gold_files": 0,
        "after_parsed_gold_files": 0,
        "recovered_gold_files_with_funcs": 0,
    })

    for q in py_queries:
        r = q["repo"]
        t = q["_subset_name"]
        g_files = target_gold_files(q)

        recovered_repo_gold[r]["queries_total"] += 1
        recovered_task_gold[t]["queries_total"] += 1

        before_has_parsed = False
        after_has_parsed = False

        for gf in g_files:
            recovered_repo_gold[r]["gold_files_total"] += 1
            recovered_task_gold[t]["gold_files_total"] += 1

            # Check before
            gf_had_before = False
            # Check if gf was parsed before in base_audit
            # We check if gf has recovered functions from symbol chunks
            has_recovered_funcs = len(repo_recovered_funcs[r].get(gf, [])) > 0
            if has_recovered_funcs:
                recovered_repo_gold[r]["recovered_gold_files_with_funcs"] += 1
                recovered_task_gold[t]["recovered_gold_files_with_funcs"] += 1
                after_has_parsed = True

        # Check before parsed from base_audit
        if base_repo_gold.get(r, {}).get("queries_at_least_one_parsed", 0) > 0:
            before_has_parsed = True

        if before_has_parsed:
            recovered_repo_gold[r]["before_parsed_queries"] += 1
            recovered_task_gold[t]["before_parsed_queries"] += 1
        if before_has_parsed or after_has_parsed:
            recovered_repo_gold[r]["after_parsed_queries"] += 1
            recovered_task_gold[t]["after_parsed_queries"] += 1

    summary = {
        "total_chunks_inspected": total_chunks_inspected,
        "total_categories": dict(total_categories),
        "repo_fragment_analysis": repo_fragment_analysis,
        "resolution_policy_breakdown": dict(resolution_counts),
        "total_recovered_functions": sum(len(fn_list) for r_dict in repo_recovered_funcs.values() for fn_list in r_dict.values()),
        "total_recovered_fragment_calls": sum(len(c_list) for c_list in repo_fragment_calls.values()),
        "recovered_repo_gold": dict(recovered_repo_gold),
        "recovered_task_gold": dict(recovered_task_gold),
        "base_task_gold": base_task_gold,
    }

    out_file = STAGE_DIR / "scripts" / "symbol_fragment_recovery_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Symbol fragment recovery results saved to {out_file}")
    return summary

if __name__ == "__main__":
    analyze_symbol_fragments()

