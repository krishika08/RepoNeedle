import json
import re
import ast
from pathlib import Path
from collections import defaultdict
import numpy as np

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[^A-Za-z0-9_\s]", re.UNICODE)
def count_exact_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))

def package_file(path: str, content: str) -> tuple[str, int]:
    ext = path.split(".")[-1] if "." in path else "text"
    wrapped = f"# File: {path}\n```{ext}\n{content}\n```\n\n"
    return wrapped, count_exact_tokens(wrapped)

def extract_focus_span(content: str, path: str, q_terms: set[str]) -> tuple[str, int]:
    lines = content.splitlines()
    if len(lines) <= 50:
        return content, count_exact_tokens(content)

    # For Python files: AST extraction
    if path.endswith(".py"):
        try:
            tree = ast.parse(content)
            selected_lines = set()
            # Always include imports (first ~25 lines of imports)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    selected_lines.add(node.lineno)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = node.name.lower()
                    if any(t in name for t in q_terms if len(t) > 2):
                        end_l = getattr(node, "end_lineno", node.lineno + 30)
                        for l in range(max(1, node.lineno - 1), min(len(lines) + 1, end_l + 2)):
                            selected_lines.add(l)

            if selected_lines:
                res_lines = []
                last_l = 0
                for l_idx in sorted(selected_lines):
                    if last_l > 0 and l_idx > last_l + 1:
                        res_lines.append("    # ... [elided surrounding lines] ...")
                    res_lines.append(lines[l_idx - 1])
                    last_l = l_idx
                rendered = "\n".join(res_lines)
                return rendered, count_exact_tokens(rendered)
        except Exception:
            pass

    # Regex / line-based polyglot focus span extraction
    matched_lines = set()
    for idx, l in enumerate(lines, 1):
        stripped = l.strip().lower()
        if any(t in stripped for t in q_terms if len(t) > 2):
            # Take line and 5 lines surrounding
            for k in range(max(1, idx - 3), min(len(lines) + 1, idx + 4)):
                matched_lines.add(k)

    if not matched_lines:
        # Fallback to outline
        outline = [l for l in lines if l.strip().startswith(("class ", "def ", "func ", "pub fn", "fn ", "import ", "package ", "type ", "export "))]
        rendered = "\n".join(outline[:60])
        return rendered, count_exact_tokens(rendered)

    res_lines = []
    last_l = 0
    for l_idx in sorted(matched_lines):
        if last_l > 0 and l_idx > last_l + 1:
            res_lines.append("    // ... [elided surrounding lines] ...")
        res_lines.append(lines[l_idx - 1])
        last_l = l_idx

    rendered = "\n".join(res_lines)
    return rendered, count_exact_tokens(rendered)

def extract_outline(content: str, path: str) -> tuple[str, int]:
    lines = content.splitlines()
    outline = [l for l in lines if l.strip().startswith((
        "class ", "def ", "async def ", "func ", "pub fn ", "fn ", "impl ", "struct ",
        "interface ", "type ", "import ", "from ", "package ", "export ", "public ", "private "
    ))]
    rendered = "\n".join(outline[:80])
    return rendered, count_exact_tokens(rendered)

ARB_DIR = Path("external/agent-retrieval-bench")
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest = {}
for line in open(manifest_path, encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        manifest[(r["repo"], r["base_commit"])] = ARB_DIR / r["chunks_path"]

queries = []
with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        queries.append(json.loads(line))

dev_queries = queries[::7][:50]
corpus_cache = {}
for q in dev_queries:
    key = (q["repo"], q["commit"])
    if key not in corpus_cache:
        cpath = manifest[key]
        file_chunks = {}
        with open(cpath, "r", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                if c.get("kind") == "file":
                    file_chunks[c["path"]] = c.get("text", "")
        corpus_cache[key] = file_chunks

# Multi-Tier CUD-Pack implementation
def multi_tier_cud_pack(q, file_chunks, B, mode="complete"):
    selected = []
    selected_paths = set()
    selected_dirs = defaultdict(int)
    used = 0

    def get_dir(p):
        parts = p.split("/")
        return "/".join(parts[:-1]) if len(parts) > 1 else ""

    q_text = q["query_text"]
    q_terms = set(re.findall(r"[A-Za-z0-9_]+", q_text.lower()))

    # Rank-ordered candidate iteration
    for rank, c in enumerate(q["candidates"][:60], 1):
        p = c["path"]
        if p in selected_paths:
            continue
        text = file_chunks.get(p, "")
        if not text:
            continue

        rem_budget = B - used
        if rem_budget <= 35:
            break

        # Sizing options:
        # 1. Full file
        full_wrapped, full_pkg = package_file(p, text)
        
        # 2. Focus span
        span_content, _ = extract_focus_span(text, p, q_terms)
        span_wrapped, span_pkg = package_file(p, span_content)

        # 3. Outline
        outline_content, _ = extract_outline(text, p)
        outline_wrapped, outline_pkg = package_file(p, outline_content)

        # Decision:
        # In COMPLETE mode (8k):
        # - If full file fits comfortably in remaining budget (<= rem_budget and <= B * 0.65 for non-rank-1), take FULL!
        # - If full file does NOT fit, but focus span fits, take FOCUS_SPAN!
        # - If focus span does not fit, take OUTLINE!
        chosen = None
        if mode == "complete":
            if full_pkg <= rem_budget and (rank == 1 or full_pkg <= B * 0.60):
                chosen = ("full", full_pkg, text)
            elif span_pkg <= rem_budget and span_pkg < full_pkg * 0.75:
                chosen = ("focus_span", span_pkg, span_content)
            elif outline_pkg <= rem_budget and outline_pkg < full_pkg * 0.40:
                chosen = ("outline", outline_pkg, outline_content)
        else:
            # COMPACT mode (4k):
            # Prioritize focus spans and compact full files (<= 1200 tokens)
            if full_pkg <= rem_budget and full_pkg <= 1000 and (rank == 1 or full_pkg <= rem_budget * 0.5):
                chosen = ("full", full_pkg, text)
            elif span_pkg <= rem_budget:
                chosen = ("focus_span", span_pkg, span_content)
            elif outline_pkg <= rem_budget:
                chosen = ("outline", outline_pkg, outline_content)

        if chosen:
            tier, pkg_tok, cont = chosen
            selected.append({"path": p, "tier": tier, "pkg_tokens": pkg_tok, "rank": rank})
            selected_paths.add(p)
            selected_dirs[get_dir(p)] += 1
            used += pkg_tok

    return selected

print("\n" + "=" * 80)
print("TESTING MULTI-TIER CUD-PACK ON DEV SPLIT (N=50)")
print("=" * 80)
for mode in ["compact", "complete"]:
    for B in [2048, 4096, 8192]:
        complete_full_c = 0
        complete_any_c = 0
        gold_retrieved_full = 0
        gold_retrieved_any = 0
        total_golds = sum(len(q["gold_files"]) for q in dev_queries)
        overflows = 0
        tot_pkg_all = 0
        gold_pkg_all = 0

        for q in dev_queries:
            golds = set(q["gold_files"])
            file_chunks = corpus_cache[(q["repo"], q["commit"])]
            sel = multi_tier_cud_pack(q, file_chunks, B, mode=mode)
            
            tot_pkg = sum(s["pkg_tokens"] for s in sel)
            if tot_pkg > B:
                overflows += 1
            tot_pkg_all += tot_pkg

            sel_map = {s["path"]: s["tier"] for s in sel}
            matched_golds = golds.intersection(sel_map.keys())
            matched_full_golds = {g for g in matched_golds if sel_map[g] == "full"}

            if len(matched_golds) == len(golds):
                complete_any_c += 1
            if len(matched_full_golds) == len(golds):
                complete_full_c += 1

            gold_retrieved_any += len(matched_golds)
            gold_retrieved_full += len(matched_full_golds)

            for s in sel:
                if s["path"] in golds:
                    gold_pkg_all += s["pkg_tokens"]

        print(f"Mode: {mode:8} | Budget {B:>4} | Complete (Full): {complete_full_c/50:6.2%} | Complete (Any): {complete_any_c/50:6.2%} | MicroRec (Full): {gold_retrieved_full/total_golds:6.2%} | MicroRec (Any): {gold_retrieved_any/total_golds:6.2%} | Yield: {gold_pkg_all/tot_pkg_all:6.2%} | Overflows: {overflows}")

