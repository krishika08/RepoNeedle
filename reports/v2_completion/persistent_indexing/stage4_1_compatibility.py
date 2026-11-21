"""Stage 4.1 cache compatibility: a cache written by each revision is read by each revision (forward and rollback).

usage: python stage4_1_compatibility.py <repo> <out.json> name=code_root [name=code_root ...]
Each reader runs on a copy of the writer's cache (cold build by the writer first). Recorded per cell: reuse counters,
the semantic work counters, and the complete index-and-retrieval digest (PYTHONHASHSEED=0), plus every revision's
uncached digest.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage3_benchmark as s3  # noqa: E402
import stage4_benchmark as s4  # noqa: E402

repo, out = Path(sys.argv[1]), Path(sys.argv[2])
revs = dict(a.split("=", 1) for a in sys.argv[3:])
revs = {k: Path(v) for k, v in revs.items()}
env = {"BENCH_VERIFY": "1", "PYTHONHASHSEED": "0"}
limit = 12 * 1024 ** 3
work = Path(tempfile.mkdtemp(prefix="rn_s41_compat_"))
result = {"revisions": {k: s4.git_revision(v) for k, v in revs.items()}, "dataset": s4.dataset_manifest(
    repo, sum(1 for p in repo.rglob("*") if p.is_file()), "reduced", {}), "uncached": {}, "cells": {}}
awake = s3.keep_awake(True)
try:
    for name, root in revs.items():
        r = s4.run_phase(root, repo, work / "unused", "uncached", limit, None, env=env)
        result["uncached"][name] = r.get("state_digest")
    for writer, wroot in revs.items():
        wcache = work / f"w_{writer}"
        cold = s4.run_phase(wroot, repo, wcache, "cached", limit, None)
        for reader, rroot in revs.items():
            rcache = work / f"r_{writer}_{reader}"
            shutil.copytree(wcache, rcache)
            r = s4.run_phase(rroot, repo, rcache, "cached", limit, None, env=env)
            rep = r.get("report", {})
            sem = rep.get("work_counters", {}).get("semantic", {})
            result["cells"][f"{writer}->{reader}"] = {
                "writer_state": cold.get("report", {}).get("state"), "state": rep.get("state"),
                "files": r.get("files"), "files_reused": rep.get("files_reused"),
                "files_extracted": rep.get("files_extracted"), "artifacts_written": rep.get("artifacts_written"),
                "semantic_feature_cache_hits": sem.get("feature_cache_hits"),
                "semantic_documents_reextracted": sem.get("documents_reextracted"),
                "digest": r.get("state_digest"), "error": r.get("failed") or r.get("aborted")}
            print(writer, "->", reader, json.dumps(result["cells"][f"{writer}->{reader}"])[:300], flush=True)
finally:
    s3.keep_awake(False)
    shutil.rmtree(work, ignore_errors=True)
digests = set(result["uncached"].values()) | {c["digest"] for c in result["cells"].values()}
result["all_digests_identical"] = len(digests) == 1 and None not in digests
result["full_reuse_everywhere"] = all(c["files_reused"] == c["files"] and c["semantic_documents_reextracted"] == 0
                                      for c in result["cells"].values())
out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
print("identical", result["all_digests_identical"], "full reuse", result["full_reuse_everywhere"])
