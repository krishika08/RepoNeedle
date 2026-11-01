"""
Production and regression test suite for RepoNeedle CUD-Pack.
Verifies all failure modes, boundary invariants, and polyglot extraction rules.
"""

import json
import gzip
from pathlib import Path
import pytest

from reponeedle.core.packer import (
    BENCHMARK_TOKEN_PATTERN,
    CodeSpanExtractor,
    CUDPackOptimizer,
    ExactTokenizer,
    filter_query_terms,
)
from reponeedle.models import BudgetConfig, ContextTier, FileDoc, ScoredFile


def test_exact_tokenizer_accounting():
    tok = ExactTokenizer()
    text = "def hello_world(x: int) -> bool:\n    return x > 0\n"
    count = tok.count_tokens(text, "test.py")
    assert count > 0
    # Memoization check
    assert tok.count_tokens(text, "test.py") == count

    overhead = tok.packaging_overhead("pkg/foo/bar.py", "py")
    assert overhead > 0

    rendered = tok.render_packaged_block("pkg/foo/bar.py", text)
    rendered_toks = tok.count_tokens(rendered)
    assert rendered_toks == count + overhead


def test_budget_hard_invariant_boundary():
    optimizer = CUDPackOptimizer()
    docs = [
        (FileDoc(path=f"file_{i}.py", content=f"def func_{i}():\n    return {i * 10}\n" * 15), 1.0 / (i + 1), {})
        for i in range(25)
    ]

    for budget in [100, 250, 500, 1024, 2048, 4096]:
        selected = optimizer.pack_context(
            candidate_files=docs,
            budget_tokens=budget,
            query_text="func_5 func_12",
        )
        total_tokens = sum(sf.token_count for sf in selected)
        assert total_tokens <= budget, f"Budget {budget} overflowed: {total_tokens}"
        prompt = optimizer.tokenizer.render_prompt(selected)
        exact_prompt_toks = optimizer.tokenizer.count_tokens(prompt)
        assert exact_prompt_toks == total_tokens
        assert exact_prompt_toks <= budget


def test_ast_extraction_and_syntax_error_fallback():
    extractor = CodeSpanExtractor()
    # 1. Valid Python with query match in second function
    code_valid = (
        "import os\nimport sys\n\n"
        "def first_helper():\n    return 1\n\n"
        "def target_logic():\n    '''Performs target computation.'''\n    x = 42\n    return x\n"
    )
    span, lines = extractor.extract_focus_span(code_valid, "logic.py", {"target", "computation"})
    assert "target_logic" in span
    assert "import os" in span

    # 2. Syntax-error Python code (e.g. unclosed parentheses)
    code_syntax_err = (
        "def broken(\n"
        "    a, b,\n"
        "def target_func():\n"
        "    return 'rescued'\n"
    )
    span_err, lines_err = extractor.extract_focus_span(code_syntax_err, "broken.py", {"target", "func"})
    assert "target_func" in span_err


def test_polyglot_languages():
    extractor = CodeSpanExtractor()

    # Go
    go_code = (
        "package main\n\n"
        "import (\n\t\"fmt\"\n\t\"time\"\n)\n\n"
        "func ProcessTransaction(id string) error {\n"
        "\tfmt.Println(id)\n"
        "\treturn nil\n"
        "}\n"
    )
    go_span, _ = extractor.extract_focus_span(go_code, "server.go", {"transaction", "process"})
    assert "package main" in go_span
    assert "ProcessTransaction" in go_span

    # Rust
    rs_code = (
        "use std::collections::HashMap;\n\n"
        "pub fn calculate_checksum(data: &[u8]) -> u64 {\n"
        "    let mut sum = 0u64;\n"
        "    sum\n"
        "}\n"
    )
    rs_span, _ = extractor.extract_focus_span(rs_code, "checksum.rs", {"checksum", "calculate"})
    assert "pub fn calculate_checksum" in rs_span

    # TypeScript
    ts_code = (
        "import { Request, Response } from 'express';\n\n"
        "export function handleWebhook(req: Request, res: Response): void {\n"
        "    res.status(200).send('OK');\n"
        "}\n"
    )
    ts_span, _ = extractor.extract_focus_span(ts_code, "handler.ts", {"webhook", "handle"})
    assert "export function handleWebhook" in ts_span


def test_duplicate_file_repression():
    optimizer = CUDPackOptimizer()
    candidates = [
        {"path": "core/engine.py", "content": "def run(): pass\n", "rank": 1, "score": 0.9},
        {"path": "core/engine.py", "content": "def run(): pass\n", "rank": 2, "score": 0.8},
        {"path": "core/utils.py", "content": "def util(): pass\n", "rank": 3, "score": 0.7},
    ]
    selected = optimizer.pack_context(candidates, budget_tokens=2000, query_text="run engine")
    paths = [s.path for s in selected]
    assert len(paths) == len(set(paths)), "Duplicate file paths selected!"
    assert paths.count("core/engine.py") == 1


def test_unicode_and_unusual_filenames():
    optimizer = CUDPackOptimizer()
    candidates = [
        {"path": "src/español/módulo.py", "content": "# Español\ndef saludar(): return 'hola'\n", "rank": 1, "score": 0.9},
        {"path": "src/日本語/処理.go", "content": "package nihongo\nfunc Syori() {}\n", "rank": 2, "score": 0.8},
        {"path": "tests/path with spaces/test 1.py", "content": "def test(): pass\n", "rank": 3, "score": 0.7},
    ]
    selected = optimizer.pack_context(candidates, budget_tokens=2000, query_text="saludar nihongo")
    prompt = optimizer.tokenizer.render_prompt(selected)
    assert "módulo.py" in prompt
    assert "日本語" in prompt
    assert "path with spaces" in prompt


def test_empty_and_malformed_candidates():
    optimizer = CUDPackOptimizer()
    candidates = [
        {"path": "", "content": "no path", "rank": 1, "score": 0.9},
        {"path": "empty.py", "content": "", "rank": 2, "score": 0.8},
        {"path": "whitespace.py", "content": "   \n\n\t  ", "rank": 3, "score": 0.7},
        {"path": "valid.py", "content": "x = 1\n", "rank": 4, "score": 0.6},
    ]
    selected = optimizer.pack_context(candidates, budget_tokens=2000, query_text="valid")
    assert len(selected) == 1
    assert selected[0].path == "valid.py"


def test_compact_vs_complete_modes():
    optimizer = CUDPackOptimizer()
    large_content = "def big_function():\n    x = 1\n" + ("    print(x)\n" * 200)
    candidates = [
        {"path": "big.py", "content": large_content, "rank": 1, "score": 0.9},
    ]

    # Compact Mode (at 1000 tokens): should deliver FOCUS_SPAN
    compact_sel = optimizer.pack_context(candidates, budget_tokens=1000, query_text="big_function", mode="compact")
    assert len(compact_sel) == 1
    assert compact_sel[0].tier == ContextTier.FOCUS_SPAN
    assert compact_sel[0].token_count < 500

    # Complete Mode (at 8000 tokens): should deliver FULL_FILE or FULL
    complete_sel = optimizer.pack_context(candidates, budget_tokens=8000, query_text="big_function", mode="complete")
    assert len(complete_sel) == 1
    assert complete_sel[0].tier in (ContextTier.FULL, ContextTier.FULL_FILE)


def test_curated_regression_suite():
    suite_path = Path("research/v1_accuracy/m3_cud_pack/curated_cud_pack_regression_suite.json")
    if not suite_path.exists():
        pytest.skip("Curated regression suite not found")

    ARB_DIR = Path("external/agent-retrieval-bench")
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    if not manifest_path.exists():
        pytest.skip("Corpus manifest not found")

    manifest = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            manifest[(r["repo"], r["base_commit"])] = ARB_DIR / r["chunks_path"]

    cands_path = Path("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl")
    if not cands_path.exists():
        cands_path = Path("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz")
    open_fn = gzip.open if str(cands_path).endswith(".gz") else open
    q_map = {json.loads(l)["query_id"]: json.loads(l) for l in open_fn(cands_path, "rt", encoding="utf-8")}

    suite = json.load(open(suite_path, encoding="utf-8"))
    optimizer = CUDPackOptimizer()

    passed = 0
    for item in suite:
        qid = item["query_id"]
        q = q_map[qid]
        repo, commit, track = item["repo"], item["commit"], item["track"]
        cpath = manifest[(repo, commit)]
        file_chunks = {
            json.loads(l)["path"]: json.loads(l).get("text", "")
            for l in open(cpath, encoding="utf-8")
            if json.loads(l).get("kind") == "file"
        }
        pool = [dict(c, content=file_chunks.get(c["path"], "")) for c in q["candidates"][:85]]
        selected = optimizer.pack_context(pool, budget_tokens=4096, query_text=q["query_text"], mode="compact")

        tot_pkg = sum(s.token_count for s in selected)
        assert tot_pkg <= 4096

        sel_map = {s.path: s for s in selected}
        all_present = True
        for sp in item["annotated_spans"]:
            gp = sp["gold_path"]
            sym = sp["target_symbol"]
            if gp not in sel_map:
                all_present = False
                break
            if sym.lower() not in sel_map[gp].rendered_content.lower():
                all_present = False
                break
        if all_present:
            passed += 1

    assert passed == len(suite), f"Curated regression suite failed: {passed}/{len(suite)}"


def test_held_out_evaluation_suite():
    suite_path = Path("research/v1_accuracy/m3_cud_pack/held_out_cud_pack_evaluation_suite.json")
    if not suite_path.exists():
        pytest.skip("Held-out evaluation suite not found")

    ARB_DIR = Path("external/agent-retrieval-bench")
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    if not manifest_path.exists():
        pytest.skip("Corpus manifest not found")

    manifest = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            manifest[(r["repo"], r["base_commit"])] = ARB_DIR / r["chunks_path"]

    cands_path = Path("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl")
    if not cands_path.exists():
        cands_path = Path("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz")
    open_fn = gzip.open if str(cands_path).endswith(".gz") else open
    q_map = {json.loads(l)["query_id"]: json.loads(l) for l in open_fn(cands_path, "rt", encoding="utf-8")}

    suite = json.load(open(suite_path, encoding="utf-8"))
    optimizer = CUDPackOptimizer()

    passed = 0
    overflow_count = 0
    for item in suite:
        qid = item["query_id"]
        q = q_map[qid]
        repo, commit, track = item["repo"], item["commit"], item["track"]
        cpath = manifest[(repo, commit)]
        file_chunks = {
            json.loads(l)["path"]: json.loads(l).get("text", "")
            for l in open(cpath, encoding="utf-8")
            if json.loads(l).get("kind") == "file"
        }
        pool = [dict(c, content=file_chunks.get(c["path"], "")) for c in q["candidates"][:85]]
        selected = optimizer.pack_context(pool, budget_tokens=4096, query_text=q["query_text"], mode="compact")

        tot_pkg = sum(s.token_count for s in selected)
        if tot_pkg > 4096:
            overflow_count += 1
        assert tot_pkg <= 4096

        sel_map = {s.path: s for s in selected}
        all_present = all(sp["gold_path"] in sel_map for sp in item["annotated_spans"])
        if all_present:
            passed += 1

    assert overflow_count == 0, f"Encountered {overflow_count} overflows in held-out suite!"
    # Pass rate on held-out unseen repositories >= 90%
    assert passed >= 18, f"Held-out pass rate too low: {passed}/{len(suite)}"
