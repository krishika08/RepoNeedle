import json
import re
import sys
sys.path.insert(0, ".")
from research.v1_accuracy.m3_cud_pack.cud_pack_engine import CUDPackOptimizer, ExactTokenizer, filter_query_terms
from pathlib import Path

ARB_DIR = Path("external/agent-retrieval-bench")
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest = {}
for line in open(manifest_path, encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        manifest[(r["repo"], r["base_commit"])] = ARB_DIR / r["chunks_path"]

with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        q = json.loads(line)
        if q["query_id"].startswith("4efdeafc"):
            break

cpath = manifest[(q["repo"], q["commit"])]
for line in open(cpath, encoding="utf-8"):
    c = json.loads(line)
    if c.get("path") == "binding/binding_test.go" and c.get("kind") == "file":
        text = c.get("text", "")
        break

opt = CUDPackOptimizer(ExactTokenizer())
terms = filter_query_terms(q["query_text"])
span, tok = opt.extractor.extract_focus_span(text, "binding/binding_test.go", terms)
print("Terms:", terms)
print("Span tokens:", tok)
print("First 15 lines of span:\n", "\n".join(span.splitlines()[:15]))

