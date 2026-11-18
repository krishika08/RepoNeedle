"""
Stage 0 performance check: does the correctness work cost anything? Measurement only.

    python reports/v2_completion/persistent_indexing/stage0_benchmark.py [--baseline 06d4fe6] [--snapshot HEAD]
                                                                         [--rounds 5] [--out stage0_benchmark.json]

Compares the baseline package code (a temporary ``git worktree`` of ``--baseline``) with this checkout's code on the
same inputs: a pinned snapshot of this repository (snapshot.py) and a synthetic 3,000-file repository. Each round
runs one fresh subprocess per code version, alternating their order, and the best (minimum) of the rounds is reported.

Measured per code version:
- cold fit of each index and warm refits (every per-document cache hit), which is where the SHA-256 signatures
  replace ``hash()``;
- three consecutive FunctionGraphEngine.build_graph() calls on one instance;
- ``update_documents()`` for one modified file.
For this checkout only (the API is new): ``remove_documents()`` of one file and of 10% of the files, and the
signature computation alone.
"""

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

from snapshot import Snapshot, check_out_path  # noqa: E402

CHILD = r'''
import json, sys, time
code_root, repo, is_new = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
sys.path.insert(0, code_root)
from reponeedle.engine import RepoNeedleEngine
from reponeedle.models import FileDoc
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex
from reponeedle.core.abstention import SelectiveAbstainer
from reponeedle.core.function_graph import FunctionGraphEngine
import reponeedle.core.lexical as lexmod
assert lexmod.__file__.startswith(code_root), (lexmod.__file__, code_root)

def t(fn):
    s = time.perf_counter(); fn(); return time.perf_counter() - s

base = RepoNeedleEngine.from_directory(repo, max_files=10 ** 7)
docs = base.docs
out = {"files": len(docs)}
for name, cls in (("lexical", BM25Index), ("semantic", SubwordSemanticIndex), ("abstainer", SelectiveAbstainer)):
    idx = cls()
    out[f"{name}.cold_fit"] = t(lambda: idx.fit(docs))
    out[f"{name}.warm_refit"] = t(lambda: idx.fit(docs))
fg = FunctionGraphEngine()
out["function_graph.cold_build"] = t(lambda: fg.build_graph(docs))
out["function_graph.3_warm_rebuilds"] = t(lambda: [fg.build_graph(docs) for _ in range(3)])
target = next(d for d in docs if d.path.endswith(".py"))
edited = FileDoc(**{**target.model_dump(), "content": target.content + "\n# edited\n"})
out["engine.update_documents_one_file"] = t(lambda: base.update_documents([edited]))
if is_new:
    from reponeedle.core.signatures import stable_signature
    lex = BM25Index()
    out["signatures.bm25_all_docs"] = t(lambda: [lex.doc_signature(d) for d in docs])
    out["signatures.old_style_hash_all_docs"] = t(lambda: [
        f"{d.path}::{len(d.content)}::{hash(d.content)}::{','.join(d.symbols)}" for d in docs])
    one = [docs[len(docs) // 2].path]
    out["engine.remove_documents_one_file"] = t(lambda: base.remove_documents(one))
    tenth = [d.path for d in base.docs[::10]]
    out["engine.remove_documents_10_percent"] = t(lambda: base.remove_documents(tenth))
print(json.dumps(out))
'''


def run(code_root: Path, repo: str, is_new: bool) -> dict:
    res = subprocess.run([sys.executable, "-c", CHILD, str(code_root), repo, "1" if is_new else "0"],
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout.strip().splitlines()[-1])


def compare(repo: str, baseline_root: Path, rounds: int) -> dict:
    best = {"baseline": {}, "stage0": {}}
    for r in range(rounds):
        order = [("baseline", baseline_root, False), ("stage0", ROOT, True)]
        for label, root, is_new in (order if r % 2 == 0 else order[::-1]):
            for k, v in run(root, repo, is_new).items():
                best[label][k] = v if k == "files" else min(best[label].get(k, v), v)
    ratio = {k: round(best["stage0"][k] / best["baseline"][k], 3)
             for k in best["baseline"] if k != "files" and best["baseline"][k] > 0}
    return {"best_seconds": {lab: {k: round(v, 4) for k, v in d.items()} for lab, d in best.items()},
            "stage0_over_baseline": ratio}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default="06d4fe6")
    ap.add_argument("--snapshot", default="HEAD")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    from profile_current import write_synthetic_repo

    work = Path(tempfile.mkdtemp(prefix="rn_stage0_bench_"))
    baseline_root = work / "baseline"
    subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach", str(baseline_root), args.baseline],
                   check=True, capture_output=True)
    result = {"environment": {"python": sys.version.split()[0], "platform": platform.platform(),
                              "rounds": args.rounds, "baseline_commit": args.baseline},
              "workloads": {}}
    try:
        with Snapshot(args.snapshot) as snap:
            check_out_path(args.out, snap.path)
            result["workloads"]["this repository (pinned snapshot)"] = {
                "snapshot": snap.commit, **compare(str(snap.path), baseline_root, args.rounds)}
        syn = work / "synthetic"
        write_synthetic_repo(syn, 3000)
        result["workloads"]["synthetic 3000 files"] = compare(str(syn), baseline_root, args.rounds)
    finally:
        subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(baseline_root)],
                       capture_output=True)
        shutil.rmtree(work, ignore_errors=True)
    print(json.dumps(result, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
