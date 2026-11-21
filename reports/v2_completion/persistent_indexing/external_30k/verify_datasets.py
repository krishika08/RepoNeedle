"""
Regenerates RepoNeedle benchmark corpora with the candidate revision's own generator and manifest code
(stage1_benchmark.generate, seed 7; stage4_benchmark.dataset_manifest) and compares each manifest with the value
recorded in expected.json. Nothing in the repository is modified; corpora are generated in a temporary directory and
deleted afterwards.

    python verify_datasets.py --candidate-root <Stage 4.1 worktree> [--workload "reduced 30000"] [--out file.json]
"""

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-root", required=True)
    ap.add_argument("--workload", action="append", default=None,
                    help='"<profile> <files>", repeatable; default: every workload in expected.json')
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    expected = json.loads((PACKAGE / "expected.json").read_text(encoding="utf-8"))["datasets"]
    bench = Path(args.candidate_root).resolve() / "reports" / "v2_completion" / "persistent_indexing"
    sys.path.insert(0, str(bench))
    import stage1_benchmark as s1        # noqa: E402
    import stage4_benchmark as s4        # noqa: E402

    wanted = args.workload or [f"{v['profile']} {v['requested_files']}" for v in expected.values()]
    results, ok = {}, True
    for spec in wanted:
        profile, n = spec.split()[0], int(spec.split()[1])
        key = f"{profile} {n} files"
        if key not in expected:
            print(f"{key}: no expected manifest recorded", flush=True)
            ok = False
            continue
        work = Path(tempfile.mkdtemp(prefix=f"rn_verify_{profile}_{n}_"))
        try:
            t = time.perf_counter()
            gen = s1.generate(work / "pristine", n, profile)
            gen["generation_seconds"] = round(time.perf_counter() - t, 1)
            m = s4.dataset_manifest(work / "pristine", n, profile, gen)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        exp = expected[key]
        checks = {f: m[f] == exp[f] for f in ("manifest_sha256", "file_count", "dataset_id", "generator_version", "seed")}
        checks["size_bytes_total"] = m["size_bytes"]["total"] == exp["size_bytes_total"]
        checks["language_distribution"] = m["language_distribution"] == exp["language_distribution"]
        match = all(checks.values())
        ok &= match
        results[key] = {"match": match, "checks": checks, "manifest_sha256": m["manifest_sha256"],
                        "expected_manifest_sha256": exp["manifest_sha256"], "file_count": m["file_count"],
                        "size_bytes_total": m["size_bytes"]["total"], "generation_seconds": m["generation_seconds"]}
        print(f"{key}: {'MATCH' if match else 'MISMATCH'} {m['manifest_sha256']} "
              f"({m['file_count']} files, {m['size_bytes']['total']} bytes, {m['generation_seconds']} s)", flush=True)
    if args.out:
        Path(args.out).write_text(json.dumps({"all_match": ok, "datasets": results}, indent=1) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
