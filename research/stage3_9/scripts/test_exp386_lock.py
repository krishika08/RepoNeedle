import json
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "external" / "agent-retrieval-bench" / "src"))
sys.path.insert(0, str(ROOT))

from agent_retrieval_bench.baseline import (
    read_jsonl,
    target_gold_files,
    hard_negative_files,
    query_text_for_eval,
    sample_metrics,
)
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex

# Load stage 3.8 per-query reference
s38_ref = {}
for line in open("research/stage3_8/PER_QUERY_RESULTS.jsonl", encoding="utf-8"):
    r = json.loads(line)
    s38_ref[r["query_id"]] = r["systems"]["EXP-386"]

ARB_DIR = ROOT / "external" / "agent-retrieval-bench"
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest_raw = {}
for line in open(manifest_path, encoding="utf-8"):
    if line.strip():
        row = json.loads(line)
        manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

subsets_def = [
    ("code2test", ARB_DIR / "data" / "benchmark" / "v2_code2test" / "samples.jsonl"),
    ("comment2context", ARB_DIR / "data" / "benchmark" / "v2_comment2context" / "samples.jsonl"),
    ("trace2code", ARB_DIR / "data" / "benchmark" / "v2_trace2code" / "samples.jsonl"),
    ("edit2ripple", ARB_DIR / "data" / "benchmark" / "v2_edit2ripple" / "samples.jsonl"),
]
all_samples = []
seen_qids = set()
for sname, spath in subsets_def:
    for r in read_jsonl(spath):
        if r["id"] not in seen_qids:
            seen_qids.add(r["id"])
            r["_subset_name"] = sname
            all_samples.append(r)

by_corpus = defaultdict(list)
for s in all_samples:
    by_corpus[(s["repo"], s["base_commit"])].append(s)

matches = 0
tested = 0
for (repo, base_commit), repo_samples in list(by_corpus.items())[:10]:
    chunks_path = manifest_raw.get((repo, base_commit))
    if not chunks_path or not chunks_path.is_file():
        continue
    chunks = read_jsonl(chunks_path)
    file_texts = {}
    for c in chunks:
        p = c.get("path")
        t = c.get("text", "")
        if p and (p not in file_texts or len(t) > len(file_texts[p])):
            file_texts[p] = t

    path_to_chunks = defaultdict(list)
    for c in chunks:
        p = c.get("path")
        if p:
            path_to_chunks[p].append(c)

    docs = []
    for p, t in file_texts.items():
        content = t[:25000]
        syms, imps = RepoGraph.extract_polyglot_symbols(content, p)
        docs.append(FileDoc(path=p, content=content, symbols=syms, imports=imps))

    num_docs = len(docs)
    doc_paths = [d.path for d in docs]
    path_to_idx = {d.path: i for i, d in enumerate(docs)}

    bm25 = BM25Index(decouple_symbols=True).fit(docs)
    semantic_index = SubwordSemanticIndex().fit(docs)
    rg = RepoGraph().fit(docs)
    G = rg.graph

    doc_paths_lower = [p.lower() for p in doc_paths]
    is_doc_file = np.array([
        any(seg in p for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or
        p.endswith((".md", ".rst", ".txt", ".adoc", ".html"))
        for p in doc_paths_lower
    ], dtype=bool)

    is_test_file = np.array([
        "test" in p or "spec" in p or p.startswith("tests/")
        for p in doc_paths_lower
    ], dtype=bool)

    is_manifest_file = np.array([
        p.endswith(("cargo.toml", "pyproject.toml", "package.json", "go.mod", "setup.py"))
        for p in doc_paths_lower
    ], dtype=bool)

    def eval_ranking(scores_vec, gold_files, hard_neg_files, budget_tokens=8000):
        ranked_indices = np.argsort(-scores_vec)
        ranked_paths = [doc_paths[i] for i in ranked_indices]
        ranked_chunks = []
        seen = set()
        for p in ranked_paths:
            if p in path_to_chunks and p not in seen:
                ranked_chunks.extend(path_to_chunks[p])
                seen.add(p)
        for p, chs in path_to_chunks.items():
            if p not in seen:
                ranked_chunks.extend(chs)
                seen.add(p)

        m = sample_metrics(gold_files, ranked_chunks, context_budget=budget_tokens, hard_negative_files=hard_neg_files)
        return m["MRR"], m["gold_coverage@8k"], ranked_paths[:3]

    for s in repo_samples:
        s_id = s["id"]
        gold = target_gold_files(s)
        hard_neg = hard_negative_files(s)
        q_text = query_text_for_eval(s)
        t_type = s["_subset_name"]

        lex = bm25.score(q_text)
        sm = semantic_index.score(q_text)
        base = (lex + sm) / 2.0
        base[is_doc_file] *= 0.5
        hits = lex + sm

        q_lower = q_text.lower()
        query_is_test_seeking = ("test" in q_lower or "assert" in q_lower or "spec" in q_lower) and t_type != "trace2code"

        boost_386 = np.zeros(num_docs, dtype=np.float32)
        if G.number_of_edges() > 0 and len(hits) > 0 and float(np.max(hits)) > 0:
            top_seeds = np.argsort(hits)[::-1][:5]
            for s_idx in top_seeds:
                sp = doc_paths[s_idx]
                sv = float(hits[s_idx])
                if sv <= 0 or sp not in G:
                    continue
                for pred in G.predecessors(sp):
                    if pred in path_to_idx:
                        n_idx = path_to_idx[pred]
                        out_deg = max(1, G.out_degree(pred))
                        bwd_raw = float(sv * 0.20 / np.sqrt(out_deg))
                        edge_mult = 1.0
                        if is_manifest_file[n_idx]:
                            edge_mult = 0.05
                        elif not query_is_test_seeking and is_test_file[n_idx] and not is_test_file[s_idx]:
                            edge_mult = 0.15
                        elif query_is_test_seeking and is_test_file[n_idx]:
                            edge_mult = 1.25
                        bwd_386 = bwd_raw * edge_mult
                        boost_386[n_idx] = max(boost_386[n_idx], bwd_386)

        sc_vec = base + 0.15 * boost_386
        mrr, bcy, paths = eval_ranking(sc_vec, gold, hard_neg)
        ref = s38_ref[s_id]
        tested += 1
        mrr_match = abs(mrr - ref["mrr"]) < 1e-5
        bcy_match = abs(bcy - ref["bcy_8k"]) < 1e-5
        if mrr_match and bcy_match:
            matches += 1
        else:
            print(f"MISMATCH on {s_id}: MRR={mrr:.4f} vs ref={ref['mrr']:.4f}, BCY={bcy:.4f} vs ref={ref['bcy_8k']:.4f}")

print(f"Tested {tested} queries across 10 corpora: {matches}/{tested} matched bit-for-bit!")

