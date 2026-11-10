"""
Phase 0 diagnostic: does the official ARB v2 harness measure RepoNeedle's full retrieval ranking?

EXPERIMENTAL DIAGNOSTIC. This does not replace or modify the official evaluation
(`benchmarks/run_complete_arb_evaluation.py`, `benchmarks/run_arb_current_engine.py`) or the
official ARB metric definitions. Outputs go to `reports/experimental/phase0_evaluator_audit/`.

For every ARB v2 positive query it records, for RepoNeedle and the official BM25 baseline, using
the same repository snapshot, candidate universe (files present in the snapshot's chunks), query
text, task label and gold files:

  OFFICIAL  The sequence the official harness evaluates for RepoNeedle: files packed by CUD-Pack
            (in packed order), followed by all remaining files in corpus (chunk-file) order.
  VIEW A    Full-ranking metrics: the complete ranking produced by the engine before packing
            (exactly the list handed to CUD-Pack), with fused and per-signal scores. For BM25,
            the official chunk ranking collapsed to unique files (best chunk score per file).
  VIEW B    Packed-context metrics: gold coverage of the files CUD-Pack actually delivered,
            success, budget utilisation; plus ARB `pack_files` BCY@8k applied to each full ranking.
  VIEW C    Remainder diagnostics: which gold files were not packed, their position in the
            official sequence (corpus order) vs. in the full ranking, and zero-score tails.

File-level MRR / Recall@K use the official ARB helpers (`reciprocal_rank`, `recall_at`).

Document modes (--doc-mode):
  official       RepoNeedle documents built exactly as the official harness does: the single longest
                 ARB chunk per path, truncated to 25,000 characters (default).
  reconstructed  DIAGNOSTIC ONLY: each file rebuilt from its ARB chunks (the `file` chunk's header
                 lines before the first symbol, then every `symbol` chunk in line order), approximating
                 the full file text RepoNeedle reads in real use. Written to a separate subdirectory.
Both modes also record ARB's own BM25 applied to whole-file pseudo-chunks of each representation
("bm25_file_longest_chunk", "bm25_file_reconstructed") to separate granularity from text coverage.

Usage:
    python benchmarks/run_arb_evaluator_audit.py --shard 0 --num-shards 3   # (x3, parallel)
    python benchmarks/run_arb_evaluator_audit.py --merge
    python benchmarks/run_arb_evaluator_audit.py --trace <sample_id> [<sample_id> ...]
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
OUT_DIR = ROOT_DIR / "reports" / "experimental" / "phase0_evaluator_audit"
CURRENT_DIR = ROOT_DIR / "reports" / "arb_v2_current_engine"
HIST_DIR = ROOT_DIR / "reports" / "full_arb_validation"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

SUBSETS = ["code2test", "comment2context", "trace2code", "edit2ripple"]
KS = (5, 10, 20)
BUDGET = 8000


def _jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def _file_metrics(gold, ranked_paths, recall_at, reciprocal_rank):
    g = set(gold)
    out = {"mrr": reciprocal_rank(g, ranked_paths)}
    for k in KS:
        out[f"recall@{k}"] = recall_at(g, ranked_paths, k)
    return out


def _load():
    from agent_retrieval_bench.baseline import read_jsonl
    manifest = {}
    for row in _jsonl(ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"):
        manifest[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]
    samples = []
    for name in SUBSETS:
        for r in read_jsonl(ARB_DIR / "data" / "benchmark" / f"v2_{name}" / "samples.jsonl"):
            r["_subset_name"] = name
            samples.append(r)
    by_corpus = defaultdict(list)
    for s in samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)
    return manifest, by_corpus


def reconstruct_file(path_chunks):
    """Header lines of the `file` chunk before the first symbol, then all symbol chunks in line order."""
    file_c = [c for c in path_chunks if c.get("kind") == "file"]
    syms = sorted((c for c in path_chunks if c.get("kind") == "symbol"), key=lambda c: c.get("start_line", 0))
    if not syms:
        return max((c.get("text", "") for c in path_chunks), key=len, default="")
    header = ""
    if file_c:
        header = "\n".join(file_c[0].get("text", "").splitlines()[: max(0, syms[0].get("start_line", 1) - 1)])
    return header + "\n" + "\n".join(c.get("text", "") for c in syms)


def evaluate_snapshot(key, group, manifest, corpus_cache, trace_ids=None, doc_mode="official"):
    """Yields one record per sample (and full traces for ids in trace_ids)."""
    from agent_retrieval_bench.baseline import (
        read_jsonl, target_gold_files, query_text_for_eval, unique_ranked_paths,
        rank_chunks_bm25_with_scores, recall_at, reciprocal_rank,
    )
    from agent_retrieval_bench.bcy_curve import pack_files
    from reponeedle.engine import RepoNeedleEngine
    from reponeedle.models import FileDoc, TaskType, Query
    from reponeedle.core.router import WorkflowRouter

    chunks = read_jsonl(manifest[key])
    file_texts = {}
    for c in chunks:
        p, t = c.get("path"), c.get("text", "")
        if p and (p not in file_texts or len(t) > len(file_texts[p])):
            file_texts[p] = t
    path_to_chunks = defaultdict(list)
    for c in chunks:
        if c.get("path"):
            path_to_chunks[c["path"]].append(c)
    reconstructed = {p: reconstruct_file(cs) for p, cs in path_to_chunks.items()}
    if doc_mode == "official":
        docs = [FileDoc(path=p, content=t[:25000], is_test="test" in p.lower()) for p, t in file_texts.items()]
    else:
        docs = [FileDoc(path=p, content=reconstructed[p], is_test="test" in p.lower()) for p in path_to_chunks]
    engine = RepoNeedleEngine.from_documents(docs)
    pseudo_longest = [{"path": p, "chunk_id": p, "text": t} for p, t in file_texts.items()]
    pseudo_recon = [{"path": p, "chunk_id": p, "text": t} for p, t in reconstructed.items()]
    corpus_order = list(path_to_chunks)          # official remainder order
    universe = set(corpus_order)

    # Capture the exact ranking handed to CUD-Pack (all files, rank order, with scores).
    captured = {}
    original_pack = engine.budget_optimizer.pack_context

    def capturing_pack(candidate_files, *a, **kw):
        captured["ranking"] = [(d.path, float(score), {k: float(v) for k, v in cs.items()})
                               for d, score, cs in candidate_files]
        return original_pack(candidate_files, *a, **kw)

    engine.budget_optimizer.pack_context = capturing_pack
    router = WorkflowRouter()
    enum = {"code2test": TaskType.CODE2TEST, "trace2code": TaskType.TRACE2CODE, "edit2ripple": TaskType.EDIT2RIPPLE}
    fm = lambda gold, paths: _file_metrics(gold, paths, recall_at, reciprocal_rank)
    bcy8 = lambda paths, gold: pack_files(key[0], key[1], paths[:20], set(gold), corpus_cache, BUDGET)["bcy"]

    for s in group:
        gold = target_gold_files(s)
        if not gold:
            continue
        task = s.get("task_type", s["_subset_name"])
        q = query_text_for_eval(s)
        captured.clear()
        res = engine.retrieve(query=q, budget_tokens=BUDGET, task_type=enum.get(task, TaskType.COMMENT2CONTEXT))
        ranking = [r for r in captured.get("ranking", []) if r[0] in universe]
        full_paths = [p for p, _, _ in ranking]
        score_of = {p: sc for p, sc, _ in ranking}
        packed = [sf.path for sf in res.selected_files if sf.path in universe]
        packed_set = set(packed)
        official = packed + [p for p in corpus_order if p not in packed_set]

        # BM25 (official baseline): chunk ranking collapsed to files, best chunk score per file.
        bm25_ranked = rank_chunks_bm25_with_scores(q, chunks)
        bm25_paths = unique_ranked_paths([c for _, c in bm25_ranked])
        bm25_score = {}
        for sc, c in bm25_ranked:
            bm25_score.setdefault(str(c.get("path", "")), float(sc))

        bm25_file_longest = [str(c["path"]) for _, c in rank_chunks_bm25_with_scores(q, pseudo_longest)]
        bm25_file_recon = [str(c["path"]) for _, c in rank_chunks_bm25_with_scores(q, pseudo_recon)]
        lex_paths = [p for p, _, _ in sorted(ranking, key=lambda r: (-r[2].get("lexical", 0.0), r[0]))]
        sem_paths = [p for p, _, _ in sorted(ranking, key=lambda r: (-r[2].get("semantic", 0.0), r[0]))]
        pos = lambda paths: {p: i for i, p in enumerate(paths, start=1)}
        p_full, p_off, p_bm25 = pos(full_paths), pos(official), pos(bm25_paths)

        gold_detail = []
        for g in gold:
            gold_detail.append({
                "path": g, "in_universe": g in universe,
                "packed": g in packed_set,
                "official_rank": p_off.get(g), "full_rank": p_full.get(g), "bm25_rank": p_bm25.get(g),
                "rn_score": score_of.get(g), "bm25_score": bm25_score.get(g),
            })
        off_top20 = set(official[:20]); full_top20 = set(full_paths[:20]); gs = set(gold)
        rec = {
            "sample_id": s["id"], "task_type": task, "repo": key[0], "base_commit": key[1],
            "n_files": len(universe), "n_gold": len(gold),
            "auto_route": router.classify_intent(Query(text=q))[0].value,
            "official": fm(gold, official),
            "rn_full": fm(gold, full_paths),
            "rn_lexical_only": fm(gold, lex_paths),
            "rn_semantic_only": fm(gold, sem_paths),
            "bm25_full": fm(gold, bm25_paths),
            "bm25_file_longest_chunk": fm(gold, bm25_file_longest),
            "bm25_file_reconstructed": fm(gold, bm25_file_recon),
            "doc_mode": doc_mode,
            "packed": {
                "n_files": len(packed), "tokens": int(res.total_tokens),
                "utilisation": res.total_tokens / BUDGET,
                "gold_coverage": len(gs & packed_set) / len(gs),
                "success": bool(gs & packed_set),
                "packed_full_rank_max": max((p_full.get(p, 0) for p in packed), default=0),
                "skipped_in_full_top_k": sum(1 for p in full_paths[:len(packed)] if p not in packed_set),
            },
            "bcy8k": {"rn_official_seq": bcy8(official, gold), "rn_full_ranking": bcy8(full_paths, gold),
                      "bm25": bcy8(bm25_paths, gold)},
            "remainder": {
                "gold_not_packed": sum(1 for g in gold if g not in packed_set),
                "official_top20_hits_from_remainder": len((off_top20 - packed_set) & gs),
                "full_top20_hits_lost_officially": len((full_top20 - off_top20) & gs),
                "rn_gold_zero_score": sum(1 for g in gold if score_of.get(g, 0.0) <= 0.0),
                "bm25_gold_zero_score": sum(1 for g in gold if bm25_score.get(g, 0.0) <= 0.0),
                "rn_zero_score_files": sum(1 for _, sc, _ in ranking if sc <= 0.0),
                "bm25_zero_score_files": sum(1 for p in bm25_paths if bm25_score.get(p, 0.0) <= 0.0),
            },
            "gold_detail": gold_detail,
        }
        if trace_ids and s["id"] in trace_ids:
            rec["trace"] = {
                "query": q,
                "rn_full_top25": [{"rank": i, "path": p, "fused": round(sc, 4),
                                   **{k: round(v, 4) for k, v in cs.items()}, "gold": p in gs, "packed": p in packed_set}
                                  for i, (p, sc, cs) in enumerate(ranking[:25], start=1)],
                "packed": [{"order": i, "path": sf.path, "tier": sf.tier.value, "tokens": sf.token_count,
                            "full_rank": p_full.get(sf.path), "gold": sf.path in gs}
                           for i, sf in enumerate(res.selected_files, start=1)],
                "official_top25": [{"rank": i, "path": p, "source": "packed" if p in packed_set else "corpus-order",
                                    "gold": p in gs} for i, p in enumerate(official[:25], start=1)],
                "bm25_top25": [{"rank": i, "path": p, "score": round(bm25_score.get(p, 0.0), 4), "gold": p in gs}
                               for i, p in enumerate(bm25_paths[:25], start=1)],
            }
        yield rec

    engine.budget_optimizer.pack_context = original_pack


def _out_dir(doc_mode):
    return OUT_DIR if doc_mode == "official" else OUT_DIR / "reconstructed_docs"


def run(shard, num_shards, trace_ids=None, only_ids=None, doc_mode="official"):
    from agent_retrieval_bench.bcy_curve import CorpusFileCache
    manifest, by_corpus = _load()
    corpus_cache = CorpusFileCache({k: Path(v) for k, v in manifest.items()})
    out_dir = _out_dir(doc_mode)
    out_dir.mkdir(parents=True, exist_ok=True)
    if only_ids:
        keys = sorted({k for k, g in by_corpus.items() for s in g if s["id"] in only_ids})
        out_path = out_dir / "traces.jsonl"
        mode = "w"
    else:
        keys = [k for i, k in enumerate(sorted(by_corpus)) if i % num_shards == shard]
        out_path = out_dir / f"shard_{shard}_of_{num_shards}.jsonl"
        mode = "a"
    done = set() if only_ids or not out_path.exists() else {r["sample_id"] for r in _jsonl(out_path)}
    t0 = time.time()
    with open(out_path, mode, encoding="utf-8") as f:
        for n, key in enumerate(keys, start=1):
            group = [s for s in by_corpus[key] if s["id"] not in done and (not only_ids or s["id"] in only_ids)]
            if not group or not manifest.get(key) or not manifest[key].is_file():
                continue
            for rec in evaluate_snapshot(key, group, manifest, corpus_cache, trace_ids, doc_mode):
                f.write(json.dumps(rec) + "\n")
            f.flush()
            corpus_cache._cache.clear()
            print(f"[audit {shard}/{num_shards}] {n}/{len(keys)} snapshots, {time.time() - t0:.0f}s",
                  file=sys.stderr, flush=True)


def _clustered_ci(diffs, groups, n_boot=5000, seed=0):
    rng = np.random.default_rng(seed)
    by = defaultdict(list)
    for d, g in zip(diffs, groups):
        by[g].append(d)
    clusters = list(by.values())
    boots = [float(np.mean(np.concatenate([clusters[i] for i in rng.integers(0, len(clusters), len(clusters))])))
             for _ in range(n_boot)]
    return [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]


def merge(doc_mode="official"):
    out_dir = _out_dir(doc_mode)
    rows = {}
    for p in sorted(out_dir.glob("shard_*.jsonl")):
        for r in _jsonl(p):
            rows[r["sample_id"]] = r
    official_ref = {}
    for p in sorted(CURRENT_DIR.glob("shard_*.jsonl")):
        for r in _jsonl(p):
            official_ref[r["sample_id"]] = r
    hist = {r["sample_id"]: r for r in _jsonl(HIST_DIR / "checkpoint_positive.jsonl")}
    ids = sorted(rows)
    mean = lambda vals: float(np.mean(vals)) if vals else 0.0

    # Fidelity checks: recomputed official sequence vs. the official current-engine run, and
    # recomputed BM25 vs. the historical official BM25 per-sample metrics.
    keys = ["mrr", "recall@5", "recall@10", "recall@20"]
    off_match = sum(all(abs(rows[i]["official"][k] - official_ref[i][k]) < 1e-12 for k in keys)
                    for i in ids if i in official_ref)
    bm25_match = sum(all(abs(rows[i]["bm25_full"][k] - hist[i]["bm25"][k]) < 1e-12 for k in keys)
                     for i in ids if i in hist)
    bcy_match = sum(abs(rows[i]["bcy8k"]["bm25"] - hist[i]["bm25"]["bcy@8k"]) < 1e-12 for i in ids if i in hist)

    def block(sel):
        out = {"n": len(sel)}
        for view in ["official", "rn_full", "rn_lexical_only", "rn_semantic_only", "bm25_full",
                     "bm25_file_longest_chunk", "bm25_file_reconstructed"]:
            if all(view in rows[i] for i in sel):
                out[view] = {k: mean([rows[i][view][k] for i in sel]) for k in keys}
        out["packed"] = {k: mean([float(rows[i]["packed"][k]) for i in sel])
                         for k in ["n_files", "utilisation", "gold_coverage", "success", "skipped_in_full_top_k"]}
        out["bcy8k"] = {k: mean([rows[i]["bcy8k"][k] for i in sel]) for k in ["rn_official_seq", "rn_full_ranking", "bm25"]}
        out["remainder"] = {k: int(sum(rows[i]["remainder"][k] for i in sel))
                            for k in ["gold_not_packed", "official_top20_hits_from_remainder",
                                      "full_top20_hits_lost_officially", "rn_gold_zero_score", "bm25_gold_zero_score"]}
        out["n_gold"] = int(sum(rows[i]["n_gold"] for i in sel))
        counts = defaultdict(int)
        for i in sel:
            counts[rows[i]["auto_route"]] += 1
        out["auto_route"] = dict(counts)
        repos = [rows[i]["repo"] for i in sel]
        out["paired"] = {}
        for a, b, k in [("rn_full", "bm25_full", "mrr"), ("rn_full", "bm25_full", "recall@20"),
                        ("official", "bm25_full", "mrr"), ("rn_full", "official", "mrr"),
                        ("rn_full", "official", "recall@20")]:
            d = np.array([rows[i][a][k] - rows[i][b][k] for i in sel])
            out["paired"][f"{a}-{b}:{k}"] = {"mean": float(d.mean()), "wins": int((d > 0).sum()),
                                              "ties": int((d == 0).sum()), "losses": int((d < 0).sum()),
                                              "repo_clustered_ci95": _clustered_ci(d, repos)}
        return out

    summary = {
        "doc_mode": doc_mode,
        "n_samples": len(ids),
        "fidelity": {"official_sequence_reproduces_current_engine_run": f"{off_match}/{len(ids)}",
                     "bm25_reproduces_historical_official_bm25": f"{bm25_match}/{len(ids)}",
                     "bm25_bcy8k_reproduces_historical": f"{bcy_match}/{len(ids)}"},
        "overall": block(ids),
        "by_task": {t: block([i for i in ids if rows[i]["task_type"] == t]) for t in SUBSETS},
    }
    (out_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase 0 ARB evaluator audit (experimental diagnostic).")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--trace", nargs="+", default=None, help="Write full traces for these sample ids.")
    ap.add_argument("--doc-mode", choices=["official", "reconstructed"], default="official")
    args = ap.parse_args(argv)
    if args.merge:
        print(json.dumps(merge(args.doc_mode), indent=2))
    elif args.trace:
        run(0, 1, trace_ids=set(args.trace), only_ids=set(args.trace), doc_mode=args.doc_mode)
    else:
        run(args.shard, args.num_shards, doc_mode=args.doc_mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
