"""
Produce tests/fixtures/tree_sitter/regex_mode_golden.json from a *reference* copy of
reponeedle/core/function_graph.py (the 1.2.0 / pre-Tree-sitter implementation).

Usage:
    git show d10ee704f4f0ae73145a35ac0f376f3c99ee30ca:reponeedle/core/function_graph.py > /tmp/fg_reference.py
    python make_regex_golden.py /tmp/fg_reference.py tests/fixtures/tree_sitter/regex_mode_golden.json

The golden records, for every fixture corpus, each file's extraction (functions, call sites, symbols,
imports) and the resulting edges. tests/test_tree_sitter_graph.py asserts that the current default
(regex) mode reproduces it exactly.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from reponeedle.models import FileDoc  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "tree_sitter"
CORPORA = ["python", "typescript", "go", "rust", "java", "cpp"]


def load_docs(corpus):
    root = FIXTURES / corpus
    docs = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            docs.append(FileDoc(path=rel, content=p.read_text(encoding="utf-8"), is_test="test" in rel.lower()))
    return docs


def snapshot(engine_cls):
    out = {}
    for corpus in CORPORA:
        docs = load_docs(corpus)
        fg = engine_cls()
        files = {}
        for d in docs:
            funcs, calls, syms, imps = fg.extract_polyglot(d.content, d.path)
            files[d.path] = {
                "functions": [[f.name, f.parent_class, f.is_method, f.is_test, f.start_line, f.arg_names] for f in funcs],
                "calls": [[c.callee_name, c.qualifier, c.is_attribute, c.caller_func, c.start_line] for c in calls],
                "symbols": syms,
                "imports": imps,
            }
        fg.build_graph(docs)
        edges = [[e.source_path, e.target_path, e.source_func, e.target_func, e.edge_type, e.confidence] for e in fg.edges]
        out[corpus] = {"files": files, "edges": edges}
    return out


if __name__ == "__main__":
    spec = importlib.util.spec_from_file_location("fg_reference", sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    sys.modules["fg_reference"] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    data = snapshot(module.FunctionGraphEngine)
    Path(sys.argv[2]).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print({k: (len(v["files"]), len(v["edges"])) for k, v in data.items()})
