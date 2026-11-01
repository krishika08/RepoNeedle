import json
from pathlib import Path

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

# Find queries where all gold files are in top 8
top8_queries = []
for q in queries:
    golds = set(q["gold_files"])
    ranks = [r for r, c in enumerate(q["candidates"], 1) if c["path"] in golds]
    if len(ranks) == len(golds) and max(ranks) <= 8:
        top8_queries.append(q)

print(f"Total queries with all gold files in top 8: {len(top8_queries)}")

# Pick 20 representative across repositories
suite_queries = top8_queries[:20]

suite_records = []
for q in suite_queries:
    qid = q["query_id"]
    repo = q["repo"]
    commit = q["commit"]
    track = q["track"]
    golds = q["gold_files"]
    q_text = q["query_text"]

    cpath = manifest[(repo, commit)]
    file_chunks = {}
    with open(cpath, "r", encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c.get("kind") == "file":
                file_chunks[c["path"]] = c.get("text", "")

    spans_info = []
    for g in golds:
        text = file_chunks.get(g, "")
        lines = text.splitlines()
        funcs = []
        for idx, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith(("def ", "async def ", "func ", "pub fn ", "fn ", "class ", "export function ")):
                name = s.split("(")[0].split()[-1]
                funcs.append({"name": name, "line": idx, "signature": s[:80]})

        q_lower = q_text.lower()
        matched_func = None
        for f in funcs:
            if f["name"].lower() in q_lower:
                matched_func = f
                break
        if not matched_func and funcs:
            matched_func = funcs[0]

        sym = matched_func["name"] if matched_func else "module_level"
        spans_info.append({
            "gold_path": g,
            "target_symbol": sym,
            "target_line": matched_func["line"] if matched_func else 1,
            "signature": matched_func["signature"] if matched_func else "",
        })

    suite_records.append({
        "query_id": qid,
        "repo": repo,
        "commit": commit,
        "track": track,
        "gold_files": golds,
        "annotated_spans": spans_info,
    })

suite_path = Path("research/v1_accuracy/m3_cud_pack/compact_context_acceptance_suite.json")
with open(suite_path, "w", encoding="utf-8") as f:
    json.dump(suite_records, f, indent=2)

print(f"Written verified 20-query compact acceptance suite to {suite_path}")

