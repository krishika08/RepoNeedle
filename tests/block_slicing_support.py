"""
Shared helpers for the AST block-slicing tests (not a test module).

``legacy_snapshot(packer_module)`` computes the outputs that must not change for the default
``focus_span_strategy="legacy"``: focus spans, skeletons and full ``pack_context`` results over the block-slicing
and Tree-sitter fixtures. ``tests/fixtures/block_slicing/legacy_golden.json`` was produced by running it against
the *baseline* packer from ``main`` at 0c0effe (see reports/v2_completion/ast_block_slicing/make_legacy_golden.py).
"""

import hashlib
import re
from pathlib import Path
from typing import Dict, List

from reponeedle.core import block_slicing as bs

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BLOCK_FIXTURES = FIXTURES / "block_slicing"
GOLDEN = BLOCK_FIXTURES / "legacy_golden.json"

LANGUAGE_FIXTURES = {
    "python": "python/inventory.py",
    "typescript": "typescript/inventory.ts",
    "tsx": "typescript/InventoryTable.tsx",
    "go": "go/inventory.go",
    "rust": "rust/inventory.rs",
    "java": "java/Inventory.java",
    "cpp": "cpp/inventory.cpp",
}
REAL_PYTHON = ("python/packer_snapshot.py", "python/function_graph_snapshot.py")

QUERIES = [
    ["reserve"],
    ["restock", "threshold"],
    ["discounted", "value"],
    ["nothing_matches_this_term"],
    ["residual", "backfill", "skeleton"],
    ["resolve", "import", "graph"],
]
BUDGETS = [150, 500, 1000, 2000, 4096, 8192]


def read(rel: str) -> str:
    return (BLOCK_FIXTURES / rel).read_text(encoding="utf-8")


def fixture_corpus() -> Dict[str, str]:
    """
    Every block-slicing and Tree-sitter fixture file (paths relative to tests/fixtures), ordered by the POSIX path
    string. Sorting Path objects is case-insensitive on Windows and case-sensitive elsewhere, which would change the
    candidate order (and therefore the golden packs) between platforms.
    """
    files = {}
    for root in (BLOCK_FIXTURES, FIXTURES / "tree_sitter"):
        found = [p for p in root.rglob("*") if p.is_file() and p.suffix not in (".json", ".md")]
        for p in sorted(found, key=lambda q: q.relative_to(FIXTURES).as_posix()):
            files[p.relative_to(FIXTURES).as_posix()] = p.read_text(encoding="utf-8")
    return files


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def legacy_snapshot(packer, config=None) -> Dict[str, List]:
    """Focus spans, skeletons and packs computed by ``packer`` (a module exposing the CUD-Pack classes)."""
    corpus = fixture_corpus()
    extractor = packer.CodeSpanExtractor()
    spans, skeletons = [], []
    for path, content in corpus.items():
        for q in QUERIES:
            terms = set(q)
            text, tokens = extractor.extract_focus_span(content, path, terms)
            spans.append([path, " ".join(q), tokens, _digest(text)])
            text, tokens = extractor.extract_skeleton(content, path, terms)
            skeletons.append([path, " ".join(q), tokens, _digest(text)])
    candidates = [{"path": p, "content": c, "rank": i, "score": 1.0 / i}
                  for i, (p, c) in enumerate(corpus.items(), start=1)]
    packs = []
    for mode in ("compact", "complete"):
        for budget in BUDGETS:
            for q in QUERIES[:3]:
                optimizer = packer.CUDPackOptimizer(config) if config is not None else packer.CUDPackOptimizer()
                selected = optimizer.pack_context(candidates, budget, query_text=" ".join(q), mode=mode)
                packs.append([mode, budget, " ".join(q),
                              [[s.path, s.tier.value, s.token_count, _digest(s.rendered_content or "")]
                               for s in selected]])
    return {"focus_spans": spans, "skeletons": skeletons, "packs": packs}


MARKER = re.compile(r"^\s*(#|//) \.\.\. \[lines? (\d+)(?:-(\d+))? elided\] \.\.\.$")


def assert_exact(text: str, content: str) -> None:
    """Every output line is the next source line verbatim, or one marker covering exactly the skipped lines."""
    lines = bs.split_lines(content)
    pointer = 1
    for out in text.split("\n"):
        m = MARKER.match(out)
        if m and (pointer > len(lines) or lines[pointer - 1] != out):
            a, b = int(m.group(2)), int(m.group(3) or m.group(2))
            assert a == pointer, f"marker {out!r} starts at {a}, expected {pointer}"
            assert any(line.strip() for line in lines[a - 1:b]), "blank-only gaps must be emitted verbatim"
            pointer = b + 1
        else:
            assert pointer <= len(lines) and lines[pointer - 1] == out, f"line {pointer}: {out!r} is not exact source"
            pointer += 1
    assert pointer == len(lines) + 1, "the output must account for every source line"
