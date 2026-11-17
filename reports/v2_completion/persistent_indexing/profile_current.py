"""
Stage-by-stage profile of the CURRENT (non-persistent) indexing pipeline. Measurement only: nothing here persists or
changes indexing behaviour.

    python reports/v2_completion/persistent_indexing/profile_current.py [--out profile_results.json]

Workloads: a pinned snapshot of this repository (``--snapshot``, default HEAD, exported with ``git archive`` to a
temporary directory by snapshot.py; default ignores, max_files raised so nothing is truncated) and
deterministic synthetic repositories (Python/TypeScript/Go files with cross-file imports and calls) of several sizes.
For each, it times discovery+read+per-file extraction (from_directory minus its _fit, measured in the same call),
every fit stage cold and then warm (per-document caches hot: the stage's global work only), and update_documents()
for one modified file. time.perf_counter, best of --repeats per figure.
"""

import argparse
import json
import platform
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reponeedle.engine import RepoNeedleEngine  # noqa: E402
from reponeedle.models import FileDoc  # noqa: E402
from snapshot import Snapshot, check_out_path, package_matches_commit  # noqa: E402


def write_synthetic_repo(root: Path, n_files: int, seed: int = 7) -> None:
    rng = random.Random(seed)
    words = ["order", "cart", "price", "user", "session", "cache", "token", "route", "parse", "render",
             "invoice", "ledger", "stock", "report", "query", "index", "graph", "event", "queue", "mail"]
    for i in range(n_files):
        pkg = f"pkg{i % 40}"
        w1, w2 = rng.choice(words), rng.choice(words)
        kind = i % 3
        if kind == 0:
            dep = f"pkg{rng.randrange(40)}.mod{rng.randrange(max(1, i))}"
            body = [f"from {dep} import helper_{rng.randrange(max(1, i))}", "import os", "",
                    f"class {w1.title()}{w2.title()}{i}:", f"    def {w1}_{i}(self, x):",
                    f"        return helper_{rng.randrange(max(1, i))}(x) + {i}", ""]
            body += [f"def {w2}_{i}_{k}(value):\n    return value * {k}  # {w1} {w2}\n" for k in range(12)]
            path = root / pkg / f"mod{i}.py"
        elif kind == 1:
            body = [f'import {{ fn{rng.randrange(max(1, i))} }} from "../pkg{rng.randrange(40)}/comp{rng.randrange(max(1, i))}";', ""]
            body += [f"export function {w1}{i}_{k}(v: number): number {{\n  return v * {k}; // {w2}\n}}\n" for k in range(12)]
            path = root / pkg / f"comp{i}.ts"
        else:
            body = [f"package {pkg}", "", 'import "fmt"', ""]
            body += [f"func {w1.title()}{i}{k}(v int) int {{\n\tfmt.Sprint(\"{w2}\")\n\treturn v * {k}\n}}\n"
                     for k in range(12)]
            path = root / pkg / f"svc{i}.go"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(body) + "\n", encoding="utf-8")


def profile(repo: str, repeats: int):
    best = {}
    real_fit = RepoNeedleEngine._fit
    for _ in range(repeats):
        fit_time = []

        def timed_fit(self, docs, _real=real_fit):
            t = time.perf_counter()
            _real(self, docs)
            fit_time.append(time.perf_counter() - t)

        RepoNeedleEngine._fit = timed_fit
        try:
            t0 = time.perf_counter()
            scan_engine = RepoNeedleEngine.from_directory(repo, max_files=10 ** 7)   # scan + every fit stage
            total = time.perf_counter() - t0
        finally:
            RepoNeedleEngine._fit = real_fit
        scan_time = total - sum(fit_time)            # measured within the same call
        docs = scan_engine.docs
        e = RepoNeedleEngine()
        stages = {}
        for name, fn in (("lexical.fit (BM25)", lambda: e.lexical_index.fit(docs)),
                         ("semantic.fit (subword TF-IDF)", lambda: e.semantic_index.fit(docs)),
                         ("repo_graph.fit (imports, tests, PageRank)", lambda: e.repo_graph.fit(docs)),
                         ("function_graph.build_graph", lambda: e.function_graph.build_graph(docs)),
                         ("abstainer.fit", lambda: e.abstainer.fit(docs))):
            t = time.perf_counter()
            fn()
            stages[name] = time.perf_counter() - t
            # Same stage again on the same instance: every per-document cache is warm, so this is the cost of
            # the stage's global (whole-corpus) work alone. repo_graph has no per-document cache.
            t = time.perf_counter()
            fn()
            stages[name + " [warm refit: global work only]"] = time.perf_counter() - t
        stages["scan + read + per-file symbol extraction (from_directory, before fit)"] = scan_time
        target = next(d for d in docs if d.path.endswith((".py", ".ts", ".go")))
        modified = FileDoc(**{**target.model_dump(), "content": target.content + "\n# edited\n"})
        t = time.perf_counter()
        scan_engine.update_documents([modified])
        stages["update_documents (one modified file, warm per-document caches)"] = time.perf_counter() - t
        stages["from_directory total (cold)"] = total
        for k, v in stages.items():
            best[k] = min(best.get(k, v), v)
    return {"files": len(docs), "bytes": sum(len(d.content.encode()) for d in docs),
            "seconds": {k: round(v, 3) for k, v in best.items()}}, docs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--sizes", type=int, nargs="+", default=[1000, 3000])
    ap.add_argument("--snapshot", default="HEAD", help="commit of this repository to measure")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    with Snapshot(args.snapshot) as snap:
        check_out_path(args.out, snap.path)
        row, docs = profile(str(snap.path), args.repeats)
        row["snapshot"] = snap.describe(docs)
        row["snapshot"]["package_code_matches_commit"] = package_matches_commit(snap.commit)
    rows = {"this repository (pinned snapshot)": row}
    for n in args.sizes:
        tmp = Path(tempfile.mkdtemp(prefix="rn_profile_"))
        try:
            write_synthetic_repo(tmp, n)
            rows[f"synthetic {n} files"] = profile(str(tmp), args.repeats)[0]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    result = {"environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                              "processor": platform.processor() or platform.machine(), "repeats": args.repeats},
              "workloads": rows}
    print(json.dumps(result, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
