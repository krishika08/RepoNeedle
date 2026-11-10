"""
Verify that historical ARB v2 results remain reproducible after RepoNeedle 1.2 made the
experimental abstention heuristic opt-in (disabled by default).

Read-only: compares fresh runs against the historical checkpoints in
reports/full_arb_validation/ (produced by benchmarks/run_complete_arb_evaluation.py under the
1.1 default, where the heuristic was always active). Nothing under reports/ is modified.

Checks (determine pass/fail)
---------------------------
Selective split (N=82, v2_abstention):
  * With explicit opt-in, the abstain decision matches the historical checkpoint for every
    sample (historically 0/82 correctly abstained).
  * With 1.2 defaults (opt-in absent), no sample abstains.
Positive split (N=345, --positives):
  * The heuristic abstains on no positive query when opted in.
  * Selected files are identical with and without the opt-in (the default change is harmless).

Informational (reported, do not determine pass/fail)
----------------------------------------------------
  * Whether confidence values and top-20 lists still equal the historical 2026-10-28 records.
    They do not for 1.1.0 or later: the historical checkpoints were produced by the engine at
    commit 8e00425 (tag `v0.1.0-baseline`), and engine changes before the 1.1.0 release changed
    the rankings. Those differences are real ranking drift, not an effect of abstention; see
    docs/BENCHMARK_CONFIGURATION.md, Section 7. Running this script against a checkout of
    `v0.1.0-baseline` reproduces both exactly.

Usage
-----
    python scripts/verify_abstention_reproducibility.py               # selective only (~minutes)
    python scripts/verify_abstention_reproducibility.py --positives   # + positives (slow)
    python scripts/verify_abstention_reproducibility.py --positives --out summary.json

Requires the Agent Retrieval Bench checkout at external/agent-retrieval-bench. Exit code 0 when
every check passes, 1 on any mismatch, 2 when required data is missing.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"
REPORT_DIR = ROOT_DIR / "reports" / "full_arb_validation"
sys.path.insert(0, str(ARB_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

CONF_TOL = 1e-6


def _load_manifest():
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    manifest = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest[(row["repo"], row["base_commit"])] = ARB_DIR / row["chunks_path"]
    return manifest


def _docs_from_chunks(chunks, FileDoc):
    """Identical document construction to benchmarks/run_complete_arb_evaluation.py."""
    file_texts = {}
    for c in chunks:
        p = c.get("path")
        t = c.get("text", "")
        if p and (p not in file_texts or len(t) > len(file_texts[p])):
            file_texts[p] = t
    return [FileDoc(path=p, content=t[:25000], is_test="test" in p.lower()) for p, t in file_texts.items()]


def _read_checkpoint(name):
    path = REPORT_DIR / name
    return {json.loads(l)["sample_id"]: json.loads(l) for l in open(path, encoding="utf-8") if l.strip()}


def verify_selective(manifest, read_jsonl, query_text_for_eval, FileDoc, RepoNeedleEngine):
    historical = _read_checkpoint("checkpoint_selective.jsonl")
    samples = read_jsonl(ARB_DIR / "data" / "benchmark" / "v2_abstention" / "samples.jsonl")
    by_corpus = defaultdict(list)
    for s in samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    out = {"total": 0, "decision_matches": 0, "confidence_matches": 0, "opt_in_abstained": 0,
           "historical_abstained": 0, "default_abstained": 0, "max_conf_abs_diff": 0.0, "mismatches": []}
    for (repo, commit), sel in by_corpus.items():
        cpath = manifest.get((repo, commit))
        if cpath and cpath.is_file():
            docs = _docs_from_chunks(read_jsonl(cpath), FileDoc)
        else:
            docs = [FileDoc(path=f"{repo}/src/main.py", content=f"# {repo} main module")]
        engine = RepoNeedleEngine.from_documents(docs)
        for s in sel:
            q = query_text_for_eval(s)
            on = engine.retrieve(query=q, budget_tokens=8000, enable_experimental_abstention=True)
            off = engine.retrieve(query=q, budget_tokens=8000)
            hist = historical.get(s["id"])
            out["total"] += 1
            out["opt_in_abstained"] += int(on.abstained)
            out["default_abstained"] += int(off.abstained)
            if hist is None:
                out["mismatches"].append({"sample_id": s["id"], "issue": "missing from historical checkpoint"})
                continue
            out["historical_abstained"] += int(bool(hist["abstained"]))
            diff = abs(float(on.confidence_score) - float(hist["confidence"]))
            out["max_conf_abs_diff"] = max(out["max_conf_abs_diff"], diff)
            dec_ok = bool(on.abstained) == bool(hist["abstained"])
            out["decision_matches"] += int(dec_ok)
            out["confidence_matches"] += int(diff <= CONF_TOL)  # informational (engine drift)
            if not dec_ok:
                out["mismatches"].append({"sample_id": s["id"], "opt_in_abstained": on.abstained,
                                          "historical_abstained": hist["abstained"]})
    out["passed"] = (out["total"] > 0 and not out["mismatches"] and out["default_abstained"] == 0)
    return out


def verify_positives(manifest, read_jsonl, query_text_for_eval, target_gold_files,
                     unique_ranked_paths, FileDoc, TaskType, RepoNeedleEngine):
    historical = _read_checkpoint("checkpoint_positive.jsonl")
    subsets = ["code2test", "comment2context", "trace2code", "edit2ripple"]
    samples = []
    for name in subsets:
        for r in read_jsonl(ARB_DIR / "data" / "benchmark" / f"v2_{name}" / "samples.jsonl"):
            r["_subset_name"] = name
            samples.append(r)
    by_corpus = defaultdict(list)
    for s in samples:
        by_corpus[(s["repo"], s["base_commit"])].append(s)

    enum = {"code2test": TaskType.CODE2TEST, "trace2code": TaskType.TRACE2CODE,
            "edit2ripple": TaskType.EDIT2RIPPLE}
    out = {"total": 0, "opt_in_abstained": 0, "selected_identical": 0, "top_files_match": 0,
           "top_files_mismatch_ids": [], "abstained_ids": []}
    t0 = time.time()
    for i, ((repo, commit), group) in enumerate(by_corpus.items(), start=1):
        cpath = manifest.get((repo, commit))
        if not cpath or not cpath.is_file():
            continue
        chunks = read_jsonl(cpath)
        engine = RepoNeedleEngine.from_documents(_docs_from_chunks(chunks, FileDoc))
        path_to_chunks = defaultdict(list)
        for c in chunks:
            if c.get("path"):
                path_to_chunks[c["path"]].append(c)
        for s in group:
            if not target_gold_files(s):
                continue
            t_enum = enum.get(s.get("task_type", s["_subset_name"]), TaskType.COMMENT2CONTEXT)
            q = query_text_for_eval(s)
            off = engine.retrieve(query=q, budget_tokens=8000, task_type=t_enum)
            on = engine.retrieve(query=q, budget_tokens=8000, task_type=t_enum,
                                 enable_experimental_abstention=True)
            out["total"] += 1
            if on.abstained:
                out["opt_in_abstained"] += 1
                out["abstained_ids"].append(s["id"])
            if [f.path for f in on.selected_files] == [f.path for f in off.selected_files]:
                out["selected_identical"] += 1
            # Rebuild top-20 exactly as the harness does (selected files first, then corpus order).
            ranked, seen = [], set()
            for sf in off.selected_files:
                if sf.path in path_to_chunks and sf.path not in seen:
                    ranked.extend(path_to_chunks[sf.path])
                    seen.add(sf.path)
            for p, chs in path_to_chunks.items():
                if p not in seen:
                    ranked.extend(chs)
                    seen.add(p)
            top = unique_ranked_paths(ranked)[:20]
            hist = historical.get(s["id"], {}).get("reponeedle", {}).get("top_files")
            if hist == top:  # informational: equals the 2026-10-28 engine's output
                out["top_files_match"] += 1
            else:
                out["top_files_mismatch_ids"].append(s["id"])
        if i % 25 == 0:
            print(f"  positives: {i}/{len(by_corpus)} snapshots, {out['total']} samples, "
                  f"{time.time() - t0:.0f}s", file=sys.stderr, flush=True)
    out["passed"] = (out["total"] > 0 and out["opt_in_abstained"] == 0
                     and out["selected_identical"] == out["total"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--positives", action="store_true", help="Also verify the N=345 positive split (slow).")
    ap.add_argument("--out", type=str, default=None, help="Optional path to write the JSON summary.")
    args = ap.parse_args(argv)

    required = [ARB_DIR / "src", REPORT_DIR / "checkpoint_selective.jsonl"]
    if args.positives:
        required.append(REPORT_DIR / "checkpoint_positive.jsonl")
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("Missing required data: " + ", ".join(missing), file=sys.stderr)
        return 2

    from agent_retrieval_bench.baseline import (
        read_jsonl, query_text_for_eval, target_gold_files, unique_ranked_paths,
    )
    from reponeedle.models import FileDoc, TaskType
    from reponeedle.engine import RepoNeedleEngine

    manifest = _load_manifest()
    t0 = time.time()
    summary = {"selective": verify_selective(manifest, read_jsonl, query_text_for_eval, FileDoc, RepoNeedleEngine)}
    print(f"selective done in {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
    if args.positives:
        summary["positive"] = verify_positives(manifest, read_jsonl, query_text_for_eval, target_gold_files,
                                               unique_ranked_paths, FileDoc, TaskType, RepoNeedleEngine)
    summary["passed"] = all(v["passed"] for v in summary.values() if isinstance(v, dict))
    summary["elapsed_s"] = round(time.time() - t0, 1)

    text = json.dumps(summary, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
