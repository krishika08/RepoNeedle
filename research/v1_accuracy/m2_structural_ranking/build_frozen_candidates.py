import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, str(Path(".").resolve()))
from research.v1_accuracy.m1_candidate_generation.candidate_engine import (
    MultiChannelCandidateEngine,
    FileDoc,
)
from research.v1_accuracy.m1_candidate_generation.eval_m1 import (
    ARB_DIR,
    read_jsonl,
    target_gold_files,
    query_text_for_eval,
)

OUT_DIR = Path("research/v1_accuracy/m2_structural_ranking")
OUT_DIR.mkdir(parents=True, exist_ok=True)
FROZEN_CANDIDATES_PATH = OUT_DIR / "frozen_m1_candidates.jsonl"


def build_frozen_candidates():
    print("=" * 80)
    print("BUILDING FROZEN M1 CANDIDATE SNAPSHOT FOR ALL 345 QUERIES")
    print("=" * 80)

    # 1. Load manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest: Dict[Tuple[str, str], Path] = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

    # 2. Load benchmark positive samples
    tracks = ["v2_code2test", "v2_comment2context", "v2_trace2code", "v2_edit2ripple"]
    all_samples = []
    seen_ids = set()
    for t in tracks:
        p = ARB_DIR / "data" / "benchmark" / t / "samples.jsonl"
        for s in read_jsonl(p):
            if s["id"] not in seen_ids:
                seen_ids.add(s["id"])
                s["_track"] = t
                all_samples.append(s)

    # Group queries by corpus
    by_corpus: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for s in all_samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    corpus_keys = list(by_corpus.keys())
    print(f"Loaded {len(all_samples)} queries across {len(corpus_keys)} unique corpora.")

    # Check existing completed queries in frozen snapshot if resuming
    existing_qids = set()
    if FROZEN_CANDIDATES_PATH.exists():
        for line in open(FROZEN_CANDIDATES_PATH, "r", encoding="utf-8"):
            if line.strip():
                try:
                    obj = json.loads(line)
                    existing_qids.add(obj["query_id"])
                except Exception:
                    pass
        print(f"Existing snapshot has {len(existing_qids)} completed queries.")

    out_file = open(FROZEN_CANDIDATES_PATH, "a", encoding="utf-8")
    total_processed = len(existing_qids)
    t_start = time.perf_counter()

    for c_idx, (repo, commit) in enumerate(corpus_keys, 1):
        samples_in_corpus = by_corpus[(repo, commit)]
        needed = [s for s in samples_in_corpus if s["id"] not in existing_qids]
        if not needed:
            continue

        chunks_path = manifest.get((repo, commit))
        if not chunks_path or not chunks_path.is_file():
            print(f"[{c_idx}/{len(corpus_keys)}] WARNING: Missing chunks path for {repo} @ {commit[:8]}")
            continue

        # Load file chunks
        file_texts: Dict[str, str] = {}
        path_symbols: Dict[str, Set[str]] = defaultdict(set)
        for line in open(chunks_path, encoding="utf-8"):
            if line.strip():
                c = json.loads(line)
                p = c.get("path")
                if not p:
                    continue
                t = c.get("text", "")
                if p not in file_texts or len(t) > len(file_texts[p]):
                    file_texts[p] = t
                sym = c.get("symbol")
                if sym and sym not in ("if", "for", "while", "try", "except", "with", "return", "raise", "pass", "isinstance", "ValueError"):
                    path_symbols[p].add(sym)

        docs = [
            FileDoc(path=p, content=t[:25000], symbols=list(path_symbols[p]))
            for p, t in file_texts.items()
        ]

        # Fit MultiChannelCandidateEngine with all_channels
        t_fit0 = time.perf_counter()
        engine = MultiChannelCandidateEngine().fit(docs)
        t_fit1 = time.perf_counter()

        for s in needed:
            qid = s["id"]
            track = s["_track"]
            gold_files = target_gold_files(s)
            q_text = query_text_for_eval(s)

            t_gen0 = time.perf_counter()
            cands = engine.generate_candidates(
                q_text,
                enable_exact_symbols=True,
                enable_field_bm25=True,
                enable_subwords=True,
                enable_structural_expansion=True,
            )
            t_gen1 = time.perf_counter()

            cand_paths = [c.filepath for c in cands]
            cand_set = set(cand_paths)

            # Assert 100% Candidate Recall for M1 baseline integrity
            golds_found = [g for g in gold_files if g in cand_set]
            if len(golds_found) != len(gold_files):
                missing = [g for g in gold_files if g not in cand_set]
                print(f"WARNING: Query {qid} missing gold files: {missing}")

            # Record candidates
            cand_records = []
            for rank_idx, c in enumerate(cands, 1):
                cand_records.append({
                    "path": c.filepath,
                    "m1_rank": rank_idx,
                    "m1_score": round(c.combined_score, 5),
                    "channels": sorted(list(c.channel_provenance)),
                    "scores": {k: round(v, 5) for k, v in c.channel_scores.items()},
                    "evidence": c.structural_evidence if c.structural_evidence else None,
                })

            query_snapshot = {
                "query_id": qid,
                "repo": repo,
                "commit": commit,
                "track": track,
                "gold_files": gold_files,
                "corpus_files": len(docs),
                "query_text": q_text,
                "gen_latency_ms": round((t_gen1 - t_gen0) * 1000.0, 2),
                "total_candidates": len(cand_records),
                "candidates": cand_records,
            }

            out_file.write(json.dumps(query_snapshot) + "\n")
            out_file.flush()
            total_processed += 1

        if c_idx % 25 == 0 or c_idx == len(corpus_keys):
            elapsed = time.perf_counter() - t_start
            print(f"[{c_idx}/{len(corpus_keys)}] Processed {total_processed}/345 queries ({elapsed:.1f}s)")

    out_file.close()
    print(f"Completed frozen candidate snapshot generation: {total_processed} queries written to {FROZEN_CANDIDATES_PATH}")


if __name__ == "__main__":
    build_frozen_candidates()

