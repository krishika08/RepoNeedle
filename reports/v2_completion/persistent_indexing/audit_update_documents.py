"""
Audit of today's update path against a fresh build. Measurement only: no behaviour is changed.

    python reports/v2_completion/persistent_indexing/audit_update_documents.py [--out audit_results.json]

A. Modify a file with update_documents()            -> compare every index with a fresh build (expected: identical).
B. Add a file with update_documents()               -> compare document order and indexes with a fresh
                                                       from_directory() of the same files.
C. Remove a file                                    -> the engine has no removal API; only a rebuild can drop it.
D. Rebuild one FunctionGraphEngine on a smaller set -> module_to_path / package_to_files keep entries of files
                                                       that are gone; check whether resolution can use them.
E. Python's hash() of the same content in two processes (the value today's per-document caches key on).
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from reponeedle.core.function_graph import FunctionGraphEngine  # noqa: E402
from reponeedle.engine import RepoNeedleEngine  # noqa: E402
from reponeedle.models import FileDoc  # noqa: E402

FILES = {
    "app/alpha.py": "from app.zeta import helper\n\ndef run():\n    return helper(1)\n",
    "app/zeta.py": "def helper(x):\n    return x + 1\n\ndef other():\n    return 2\n",
    "app/omega.py": "import app.zeta\n\ndef go():\n    return app.zeta.helper(3)\n",
    "tests/test_zeta.py": "from app.zeta import helper\n\ndef test_helper():\n    assert helper(1) == 2\n",
}
NEW = ("app/middle.py", "from app.zeta import helper\n\ndef middle_task():\n    return helper(5)\n")
QUERIES = ["helper function", "middle task", "run alpha", "test helper", "zeta other"]


def state(engine):
    lex, sem, rg, fg = engine.lexical_index, engine.semantic_index, engine.repo_graph, engine.function_graph
    return {
        "doc_order": [d.path for d in engine.docs],
        "lexical.avg_doc_len": float(lex.avg_doc_len),
        "lexical.idf": lex.idf,
        "semantic.vocabulary_order": list(sem.vocabulary),
        "semantic.idf": sem.idf.tolist(),
        "repo_graph.edges": sorted(rg.graph.edges()),
        "repo_graph.pagerank_by_path": dict(zip(rg.doc_paths, map(float, rg.pagerank_scores))),
        "function_graph.edges": sorted((e.source_path, e.target_path, e.edge_type) for e in fg.edges),
        "rankings": {q: engine.retrieve(q, budget_tokens=2000).ranked_files for q in QUERIES},
    }


def diff(a, b):
    return sorted(k for k in a if a[k] != b[k])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = {}
    tmp = Path(tempfile.mkdtemp(prefix="rn_audit_"))
    try:
        for rel, text in FILES.items():
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(text, encoding="utf-8")

        # A. modify in place
        eng = RepoNeedleEngine.from_directory(str(tmp))
        old = eng.path_to_doc["app/zeta.py"]
        (tmp / "app/zeta.py").write_text(FILES["app/zeta.py"] + "\ndef extra():\n    return 3\n", encoding="utf-8")
        fresh = RepoNeedleEngine.from_directory(str(tmp))
        eng.update_documents([fresh.path_to_doc["app/zeta.py"]])
        out["A_modify"] = {"differences_vs_fresh": diff(state(eng), state(fresh)), "old_symbols": old.symbols}

        # B. add a file
        eng = RepoNeedleEngine.from_directory(str(tmp))
        (tmp / NEW[0]).write_text(NEW[1], encoding="utf-8")
        fresh = RepoNeedleEngine.from_directory(str(tmp))
        eng.update_documents([fresh.path_to_doc[NEW[0]]])
        s_inc, s_fresh = state(eng), state(fresh)
        out["B_add"] = {"differences_vs_fresh": diff(s_inc, s_fresh),
                        "doc_order_update_documents": s_inc["doc_order"], "doc_order_fresh": s_fresh["doc_order"],
                        "rankings_equal": s_inc["rankings"] == s_fresh["rankings"],
                        "same_vocabulary_set": set(s_inc["semantic.vocabulary_order"]) == set(
                            s_fresh["semantic.vocabulary_order"]),
                        "semantic_idf_equal_as_sets": sorted(s_inc["semantic.idf"]) == sorted(s_fresh["semantic.idf"])}

        # C. removal
        out["C_remove"] = {"engine_has_removal_api": any(hasattr(RepoNeedleEngine, n) for n in
                                                          ("remove_document", "remove_documents", "delete_document"))}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # D. FunctionGraphEngine state surviving a rebuild
    fg = FunctionGraphEngine()
    docs = [FileDoc(path=p, content=c) for p, c in FILES.items()]
    fg.build_graph(docs)
    smaller = [d for d in docs if d.path != "app/zeta.py"]
    fg.build_graph(smaller)
    present = {d.path for d in smaller}
    stale_modules = sorted(k for k, v in fg.module_to_path.items() if v not in present)
    edges_to_missing = sorted({(e.source_path, e.target_path) for e in fg.edges if e.target_path not in present})
    fresh_fg = FunctionGraphEngine().build_graph(smaller)
    out["D_function_graph_rebuild"] = {
        "stale_module_keys_after_rebuild": stale_modules,
        "stale_package_entries": sorted({p for v in fg.package_to_files.values() for p in v if p not in present}),
        "edges_to_files_not_in_the_build": edges_to_missing,
        "edges_equal_to_fresh_instance": sorted((e.source_path, e.target_path, e.edge_type) for e in fg.edges)
        == sorted((e.source_path, e.target_path, e.edge_type) for e in fresh_fg.edges),
    }

    # E. hash() across processes
    code = "print(hash('def helper(x):\\n    return x + 1\\n'))"
    values = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip()
              for _ in range(3)}
    out["E_hash_randomisation"] = {"distinct_values_over_3_processes": len(values)}

    print(json.dumps(out, indent=1, default=str))
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
