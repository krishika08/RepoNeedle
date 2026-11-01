import sys, time, json, pathlib
sys.path.insert(0, "external/agent-retrieval-bench/src")
sys.path.insert(0, ".")
from agent_retrieval_bench.baseline import read_jsonl, query_text_for_eval, target_gold_files
from reponeedle.models import FileDoc
from research.v1_accuracy.m1_candidate_generation.candidate_engine import MultiChannelCandidateEngine

cat_a_qids = [
    "0978d6fdeb5a091c654607c7",
    "0a166358bf317488838726c8",
    "210933147c231644eeebdaae",
    "8360be1c075445a4b64aa109",
    "9aa10bc61432e4ebe7b7a30f",
    "9c3a21b87845b6155070778a",
    "a4b5977e7992227a6ad72eef",
    "c8318e728513c1a4c1bd4c9d",
    "eb415665c7189dd5c704b2dd",
]

manifest_path = "external/agent-retrieval-bench/data/corpus/v2_selective_mixed/corpus_manifest.jsonl"
manifest = {}
for line in open(manifest_path, encoding="utf-8"):
    r = json.loads(line)
    manifest[(r["repo"], r["base_commit"])] = pathlib.Path("external/agent-retrieval-bench/" + r["chunks_path"])

all_samples = []
for s_track in ["v2_code2test", "v2_comment2context", "v2_trace2code", "v2_edit2ripple"]:
    all_samples.extend(read_jsonl(pathlib.Path(f"external/agent-retrieval-bench/data/benchmark/{s_track}/samples.jsonl")))

q_map = {s["id"]: s for s in all_samples}

# Group by corpus
by_corpus = {}
for qid in cat_a_qids:
    s = q_map[qid]
    key = (s["repo"], s["base_commit"])
    if key not in by_corpus:
        by_corpus[key] = []
    by_corpus[key].append(s)

print(f"Testing {len(cat_a_qids)} Category A queries across {len(by_corpus)} corpora...")

total_golds = 0
found_golds = 0

for (repo, commit), samples in by_corpus.items():
    chunks_path = manifest[(repo, commit)]
    chunks = read_jsonl(chunks_path)
    file_texts = {}
    for c in chunks:
        p = c.get("path")
        t = c.get("text", "")
        if p and (p not in file_texts or len(t) > len(file_texts[p])):
            file_texts[p] = t
    docs = [FileDoc(path=p, content=t[:25000]) for p, t in file_texts.items()]
    t0 = time.perf_counter()
    engine = MultiChannelCandidateEngine().fit(docs)
    t1 = time.perf_counter()
    print(f"Loaded and indexed {repo} ({len(docs)} files) in {t1-t0:.2f}s")
    for s in samples:
        q_text = query_text_for_eval(s)
        golds = target_gold_files(s)
        total_golds += len(golds)
        cands = engine.generate_candidates(q_text)
        cand_paths = [c.filepath for c in cands]
        cand_set = set(cand_paths)
        found = [g for g in golds if g in cand_set]
        found_golds += len(found)
        print(f"Query {s['id']} ({s['task_type']}): {len(found)}/{len(golds)} golds found in candidates (candidates={len(cand_set)}/{len(docs)})")
        for g in golds:
            if g in cand_set:
                rank = cand_paths.index(g) + 1
                item = cands[rank - 1]
                print(f"   FOUND: {g} at rank {rank} (score={item.combined_score:.4f}, prov={item.channel_provenance})")
            else:
                print(f"   MISSING: {g}")

print(f"\nFinal Category A Candidate Recall: {found_golds}/{total_golds} ({found_golds/total_golds*100:.1f}%)")

