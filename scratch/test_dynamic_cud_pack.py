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
    if len(lines) <= 60:
        return content, count_exact_tokens(content)

    if path.endswith(".py"):
        try:
            tree = ast.parse(content)
            selected_lines = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    selected_lines.add(node.lineno)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = node.name.lower()
                    if any(t in name for t in q_terms if len(t) > 2):
                        end_l = getattr(node, "end_lineno", node.lineno + 35)
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

    # Polyglot line matching
    matched_lines = set()
    for idx, l in enumerate(lines, 1):
        stripped = l.strip().lower()
        if any(t in stripped for t in q_terms if len(t) > 2):
            for k in range(max(1, idx - 3), min(len(lines) + 1, idx + 4)):
                matched_lines.add(k)

    if not matched_lines:
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

# Test dynamic distractor dampening
def dynamic_cud_pack(q, file_chunks, B, target_full_ratio=0.55):
    selected = []
    selected_paths = set()
    used = 0

    q_text = q["query_text"]
    q_terms = set(re.findall(r"[A-Za-z0-9_]+", q_text.lower()))

    # Candidate representations pre-scoring
    # We evaluate candidates in priority order, but we dynamically select FULL vs FOCUS_SPAN:
    # If candidate is Rank 1: ALWAYS FULL (unless exceeds 60% of budget)
    # If candidate is Rank 2-5: FULL if tokens <= 800 and fits, else FOCUS_SPAN
    # If candidate is Rank 6+: FOCUS_SPAN or compact full
    
    for rank, c in enumerate(q["candidates"][:75], 1):
        p = c["path"]
        if p in selected_paths:
            continue
        text = file_chunks.get(p, "")
        if not text:
            continue

        rem = B - used
        if rem <= 35:
            break

        full_w, full_tok = package_file(p, text)
        span_c, _ = extract_focus_span(text, p, q_terms)
        span_w, span_tok = package_file(p, span_c)

        chosen = None
        # Rank 1: Full file priority
        if rank == 1:
            if full_tok <= rem and full_tok <= B * 0.70:
                chosen = ("full", full_tok)
            elif span_tok <= rem:
                chosen = ("focus_span", span_tok)
        elif rank <= 5:
            # Top tier: if full file is compact (<= 1000 tokens) and fits comfortably
            if full_tok <= rem and full_tok <= 1000 and full_tok <= rem * target_full_ratio:
                chosen = ("full", full_tok)
            elif span_tok <= rem:
                chosen = ("focus_span", span_tok)
            elif full_tok <= rem:
                chosen = ("full", full_tok)
        else:
            # Lower tier: focus span first to preserve budget
            if span_tok <= rem and span_tok < full_tok * 0.6:
                chosen = ("focus_span", span_tok)
            elif full_tok <= rem and full_tok <= 700:
                chosen = ("full", full_tok)
            elif span_tok <= rem:
                chosen = ("focus_span", span_tok)

        if chosen:
            tier, tok_cnt = chosen
            selected.append({"path": p, "tier": tier, "pkg_tokens": tok_cnt, "rank": rank})
            selected_paths.add(p)
            used += tok_cnt

    return selected

print("\n" + "=" * 80)
print("DYNAMIC CUD-PACK RESULTS ON DEV SET (N=50)")
print("=" * 80)
for B in [2048, 4096, 8192, 16384]:
    complete_full = 0
    complete_any = 0
    gold_full = 0
    gold_any = 0
    tot_g = sum(len(q["gold_files"]) for q in dev_queries)
    overflows = 0

    for q in dev_queries:
        golds = set(q["gold_files"])
        fc = corpus_cache[(q["repo"], q["commit"])]
        sel = dynamic_cud_pack(q, fc, B)

        tot_pkg = sum(s["pkg_tokens"] for s in sel)
        if tot_pkg > B: overflows += 1

        sel_map = {s["path"]: s["tier"] for s in sel}
        matched = golds.intersection(sel_map.keys())
        matched_full = {g for g in matched if sel_map[g] == "full"}

        if len(matched) == len(golds): complete_any += 1
        if len(matched_full) == len(golds): complete_full += 1

        gold_any += len(matched)
        gold_full += len(matched_full)

    print(f"Budget {B:>5}: Complete (Full): {complete_full/50:6.2%} | Complete (Any): {complete_any/50:6.2%} | MicroRec (Full): {gold_full/tot_g:6.2%} | MicroRec (Any): {gold_any/tot_g:6.2%} | Overflows: {overflows}")
print("=" * 80)

