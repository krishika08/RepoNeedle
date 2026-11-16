"""
Runtime/grammar ABI compatibility probe: loads each grammar with the installed tree-sitter runtime and
parses a small sample. Used to establish the runtime floor (REPORT.md section 1). Prints one JSON object.

    pip install "tree-sitter==<version>" tree-sitter-typescript tree-sitter-go tree-sitter-rust \
        tree-sitter-java tree-sitter-cpp
    python abi_probe.py
"""

import importlib
import importlib.metadata as md
import json
import sys

import tree_sitter as ts

SAMPLES = {
    "tree_sitter_typescript": ("language_typescript", b"export function f(a: number): number { return g(a); }"),
    "tree_sitter_typescript:tsx": ("language_tsx", b"export const C = () => <div>{f(1)}</div>;"),
    "tree_sitter_go": ("language", b"package main\nfunc main() { fmt.Println(1) }\n"),
    "tree_sitter_rust": ("language", b"fn main() { helper::run(1); }"),
    "tree_sitter_java": ("language", b"class A { void m() { b.c(); } }"),
    "tree_sitter_cpp": ("language", b"int main() { std::cout << f(1); return 0; }"),
}

out = {
    "python": sys.version.split()[0],
    "tree_sitter": md.version("tree-sitter"),
    "runtime_abi_range": [getattr(ts, "MIN_COMPATIBLE_LANGUAGE_VERSION", None), getattr(ts, "LANGUAGE_VERSION", None)],
    "grammars": {},
}
for key, (factory, src) in SAMPLES.items():
    module_name = key.split(":")[0]
    try:
        module = importlib.import_module(module_name)
        lang = ts.Language(getattr(module, factory)())
        abi = getattr(lang, "abi_version", None) or getattr(lang, "version", None)
        tree = ts.Parser(lang).parse(src)
        out["grammars"][key] = {"package": md.version(module_name.replace("_", "-")), "abi": abi,
                                "parsed_without_errors": not tree.root_node.has_error}
    except Exception as exc:  # incompatible ABI or missing package
        out["grammars"][key] = {"error": f"{type(exc).__name__}: {exc}"[:200]}
print(json.dumps(out))
