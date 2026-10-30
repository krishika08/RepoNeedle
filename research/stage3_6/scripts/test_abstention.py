import os
import sys
import json
import time
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT_DIR = Path(r"F:\RepoNeedle")
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl, query_text_for_eval
from reponeedle.models import FileDoc, Query, AblationConfig
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.abstention import SelectiveAbstainer

def main():
    print("Loading data...")
    # Corpus manifest
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest_raw = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest_raw[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]

    # Positive samples (345 across 4 tracks)
    pos_tracks = ["v2_code2test", "v2_comment2context", "v2_trace2code", "v2_edit2ripple"]
    pos_samples = []
    for t in pos_tracks:
        p = ARB_DIR / "data" / "benchmark" / t / "samples.jsonl"
        items = read_jsonl(p)
        for it in items:
            it["eval_track"] = t
        pos_samples.extend(items)
    print(f"Loaded {len(pos_samples)} positive samples.")

    # Abstention samples (82: 50 natural, 32 counterfactual)
    abstention_samples = read_jsonl(ARB_DIR / "data" / "benchmark" / "v2_abstention" / "samples.jsonl")
    print(f"Loaded {len(abstention_samples)} abstention samples.")

    # Index repositories
    # Collect all needed repos
    needed_repos = set()
    for s in pos_samples:
        needed_repos.add((s["repo"], s["base_commit"]))
    for s in abstention_samples:
        needed_repos.add((s["repo"], s["base_commit"]))

    print(f"Total unique (repo, commit) pairs: {len(needed_repos)}")

    # We will build engine for each repo
    # To keep it fast, cache engine per (repo, commit)
    engines = {}

    def get_engine(repo, commit):
        key = (repo, commit)
        if key in engines:
            return engines[key]
        chunks_file = manifest_raw.get(key)
        if not chunks_file or not chunks_file.exists():
            raise FileNotFoundError(f"Missing chunks for {key}: {chunks_file}")
        
        # Load chunks and build FileDocs
        docs = []
        for line in open(chunks_file, encoding="utf-8"):
            if not line.strip():
                continue
            chunk = json.loads(line)
            docs.append(FileDoc(
                path=chunk.get("path", chunk.get("file_path", "")),
                content=chunk.get("content", chunk.get("text", "")),
                symbols=chunk.get("symbols", []),
            ))
        cfg = AblationConfig.candidate_f()
        engine = RepoNeedleEngine(docs, ablation_config=cfg)
        engines[key] = engine
        return engine

    # Evaluate positive queries
    pos_results = []
    print("Evaluating positive queries...")
    for idx, s in enumerate(pos_samples):
        if (idx + 1) % 50 == 0:
            print(f"  Pos query {idx+1}/{len(pos_samples)}...")
        eng = get_engine(s["repo"], s["base_commit"])
        q_text = query_text_for_eval(s)
        res = eng.retrieve(Query(text=q_text))
        pos_results.append({
            "id": s["id"],
            "repo": s["repo"],
            "track": s["eval_track"],
            "is_positive": True,
            "abstained": res.abstained,
            "confidence": getattr(res, "confidence_score", 0.0),
            "reason": getattr(res, "explanation", ""),
            "files_retrieved": len(res.selected_files),
        })

    # Evaluate abstention queries
    neg_results = []
    print("Evaluating abstention queries...")
    for idx, s in enumerate(abstention_samples):
        eng = get_engine(s["repo"], s["base_commit"])
        q_text = query_text_for_eval(s)
        res = eng.retrieve(Query(text=q_text))
        is_natural = s.get("metadata", {}).get("organic", True)
        subtype = "natural" if is_natural else "counterfactual"
        neg_results.append({
            "id": s["id"],
            "repo": s["repo"],
            "subtype": subtype,
            "is_positive": False,
            "abstained": res.abstained,
            "confidence": getattr(res, "confidence_score", 0.0),
            "reason": getattr(res, "explanation", ""),
            "files_retrieved": len(res.selected_files),
        })

    print("Completed evaluation!")
    with open(r"F:\RepoNeedle\research\stage3_6\scratch_abstention.json", "w", encoding="utf-8") as out:
        json.dump({"pos": pos_results, "neg": neg_results}, out, indent=2)

if __name__ == "__main__":
    main()
