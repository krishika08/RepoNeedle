import json
from pathlib import Path
import re

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

# Pick 20 representative queries across Python, Go, Rust, TS
sample_indices = [0, 5, 12, 25, 40, 55, 70, 85, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300, 320]
suite_samples = [queries[i] for i in sample_indices]

acceptance_suite = []

for q in suite_samples:
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

    # For each gold file, extract a representative essential symbol or function
    targets_info = []
    for g in golds:
        text = file_chunks.get(g, "")
        lines = text.splitlines()
        
        # Find functions / classes
        funcs = []
        for idx, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith(("def ", "async def ", "func ", "pub fn ", "fn ", "class ", "export function ")):
                name = s.split("(")[0].split()[-1]
                funcs.append({"name": name, "line": idx, "signature": s[:80]})

        # Pick the most relevant function or class based on query terms
        q_lower = q_text.lower()
        matched_func = None
        for f in funcs:
            if f["name"].lower() in q_lower:
                matched_func = f
                break
        if not matched_func and funcs:
            matched_func = funcs[0]

        targets_info.append({
            "gold_path": g,
            "target_symbol": matched_func["name"] if matched_func else "module_level",
            "target_line": matched_func["line"] if matched_func else 1,
            "signature": matched_func["signature"] if matched_func else "",
        })

    acceptance_suite.append({
        "query_id": qid,
        "repo": repo,
        "commit": commit,
        "track": track,
        "gold_files": golds,
        "annotated_spans": targets_info,
    })

out_suite_path = Path("research/v1_accuracy/m3_cud_pack/compact_context_acceptance_suite.json")
with open(out_suite_path, "w", encoding="utf-8") as f:
    json.dump(acceptance_suite, f, indent=2)

print(f"Constructed independent compact-context acceptance suite with {len(acceptance_suite)} queries at {out_suite_path}")

