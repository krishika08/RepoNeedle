"""
Stage 3.7 Fail-Closed Audit Checks: Tag Immutability, Shortcut Excision, Metric Schema Segregation, and Determinism.
"""

import sys
import os
import csv
import json
import subprocess
from pathlib import Path
import pytest
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGE_DIR = ROOT_DIR / "research" / "stage3_7"
sys.path.insert(0, str(ROOT_DIR))

from reponeedle.models import FileDoc, Query, BudgetConfig, AblationConfig
from reponeedle.engine import RepoNeedleEngine


def test_frozen_tags_immutability():
    """Verify baseline and candidate freeze tags are intact and unchanged."""
    res_b = subprocess.run(
        ["git", "cat-file", "-p", "v0.1.0-baseline"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert "8e00425" in res_b.stdout, f"v0.1.0-baseline moved: {res_b.stdout}"

    res_c = subprocess.run(
        ["git", "cat-file", "-p", "stage3-candidate-freeze"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT_DIR,
    )
    assert "cd7f3b0" in res_c.stdout, f"stage3-candidate-freeze moved: {res_c.stdout}"


def test_no_hardcoded_benchmark_shortcuts_in_graph_py():
    """Verify that reponeedle/core/graph.py has no hardcoded ripgrep/core/printer cheats."""
    graph_py = ROOT_DIR / "reponeedle" / "core" / "graph.py"
    assert graph_py.exists(), "Missing graph.py"
    content = graph_py.read_text(encoding="utf-8")

    # Excision check: verify hardcoded bypass strings are absent
    assert '"core" in my_crate and "printer" in o_crate' not in content, "Unethical crate bypass remains in graph.py"
    assert '"search.rs", "standard.rs"' not in content, "Hardcoded ripgrep entrypoint cheat remains in graph.py"


def test_query_set_and_count_identical_across_systems():
    """Verify all evaluated systems scored the identical set and count of 345 positive queries."""
    s37_jsonl = STAGE_DIR / "PER_QUERY_RESULTS.jsonl"
    assert s37_jsonl.exists(), "Missing PER_QUERY_RESULTS.jsonl"

    queries = []
    with open(s37_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line))

    assert len(queries) == 345, f"Expected 345 queries, got {len(queries)}"
    expected_systems = {"BASE-BM25", "CAND-C", "CAND-F", "BASE-REPOMAP"}

    for item in queries:
        assert "systems" in item
        systems_present = set(item["systems"].keys())
        assert expected_systems.issubset(systems_present), f"Missing system in query {item['query_id']}"


def test_fractional_recall_and_binary_hit_schema_segregation():
    """Verify that CANONICAL_RESULTS.csv explicitly separates fractional Recall@20 and binary Hit@20."""
    can_csv = STAGE_DIR / "CANONICAL_RESULTS.csv"
    assert can_csv.exists(), "Missing CANONICAL_RESULTS.csv"
    rows = list(csv.DictReader(open(can_csv, encoding="utf-8")))
    assert len(rows) == 4

    fieldnames = list(rows[0].keys())
    assert "recall_at_20_fractional" in fieldnames, "Missing fractional recall column in schema"
    assert "hit_at_20_binary" in fieldnames, "Missing binary hit column in schema"

    # For all systems, binary hit must be >= fractional recall
    for r in rows:
        frac_rec = float(r["recall_at_20_fractional"])
        bin_hit = float(r["hit_at_20_binary"])
        assert bin_hit >= frac_rec, f"Binary hit ({bin_hit}) cannot be less than fractional recall ({frac_rec})"


def test_metrics_independently_recomputed_from_raw_query_jsonl():
    """Verify that aggregate CANONICAL_RESULTS.csv metrics match the mean of PER_QUERY_RESULTS.jsonl."""
    can_csv = STAGE_DIR / "CANONICAL_RESULTS.csv"
    can_rows = {r["system_id"]: r for r in csv.DictReader(open(can_csv, encoding="utf-8"))}

    s37_jsonl = STAGE_DIR / "PER_QUERY_RESULTS.jsonl"
    mrrs_by_sys = {sys_id: [] for sys_id in can_rows}
    with open(s37_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            for sys_id in can_rows:
                mrrs_by_sys[sys_id].append(obj["systems"][sys_id]["mrr"])

    for sys_id, r in can_rows.items():
        recomputed_mrr = float(np.mean(mrrs_by_sys[sys_id]))
        assert pytest.approx(float(r["mrr"]), abs=1e-4) == recomputed_mrr


def test_deterministic_scoring_and_tie_breaking():
    """Verify that engine retrieval is 100% deterministic across repeated executions."""
    docs = [
        FileDoc(path="src/a.py", content="def compute(): return 42"),
        FileDoc(path="src/b.py", content="def compute(): return 42"),
        FileDoc(path="src/c.py", content="def runner(): return None"),
    ]
    query = Query(text="compute", task_type="code2test")
    engine = RepoNeedleEngine.from_documents(docs, ablation_config=AblationConfig.bm25_baseline())

    res1 = engine.retrieve(query, budget_tokens=4000)
    res2 = engine.retrieve(query, budget_tokens=4000)

    paths1 = [f.path for f in res1.selected_files]
    paths2 = [f.path for f in res2.selected_files]
    assert paths1 == paths2, "Engine retrieval is non-deterministic"


def test_missing_or_corrupted_manifest_fails_closed(tmp_path):
    """Verify that malformed inputs cause explicit fail-closed rejection, not silent corruption."""
    script_path = ROOT_DIR / "research" / "stage3_15" / "validate_contextbench.py"
    bad_manifest = tmp_path / "bad.jsonl"
    bad_manifest.write_text('{"incomplete": true}\n', encoding="utf-8")

    res = subprocess.run(
        [sys.executable, str(script_path), "--data-dir", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 4, f"Expected code 4, got {res.returncode}"
    assert "Missing required field" in res.stdout
