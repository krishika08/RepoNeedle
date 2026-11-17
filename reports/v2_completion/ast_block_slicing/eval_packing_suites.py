"""
Packing-level comparison of focus-span strategies on the frozen CUD-Pack suites (no retrieval is re-run).

    python reports/v2_completion/ast_block_slicing/eval_packing_suites.py [--out results.json]

Requires the external Agent Retrieval Bench corpus (external/agent-retrieval-bench) and the frozen M1 candidate
pools in research/v1_accuracy/. For each annotated query of the curated regression suite and the held-out suite
(40 queries: Go, Rust, Python), the *same frozen candidate list* is packed with each strategy, and we record whether
every gold file was packed, whether every annotated gold symbol appears in the packed text of its gold file, the
tokens used, and which tier/fallback produced each gold file's representation.

This measures what CUD-Pack shows for a fixed ranking. It is not a retrieval-quality evaluation.
"""

import argparse
import gzip
import json
import statistics
import sys
from collections import Counter
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from reponeedle.core import block_slicing  # noqa: E402
from reponeedle.core.packer import CUDPackOptimizer  # noqa: E402
from reponeedle.models import BudgetConfig  # noqa: E402

SUITES = {
    "curated": ROOT / "research/v1_accuracy/m3_cud_pack/curated_cud_pack_regression_suite.json",
    "held_out": ROOT / "research/v1_accuracy/m3_cud_pack/held_out_cud_pack_evaluation_suite.json",
}
ARB = ROOT / "external/agent-retrieval-bench"
MANIFEST = ARB / "data/corpus/v2_selective_mixed/corpus_manifest.jsonl"
CANDIDATES = ROOT / "research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl"


def load_candidates():
    path = CANDIDATES if CANDIDATES.exists() else Path(str(CANDIDATES) + ".gz")
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return {json.loads(line)["query_id"]: json.loads(line) for line in f}


def load_manifest():
    out = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[(r["repo"], r["base_commit"])] = ARB / r["chunks_path"]
    return out


def file_texts(chunks_path, cache={}):
    if chunks_path not in cache:
        texts = {}
        for line in open(chunks_path, encoding="utf-8"):
            r = json.loads(line)
            if r.get("kind") == "file":
                texts[r["path"]] = r.get("text", "")
        cache[chunks_path] = texts
    return cache[chunks_path]


VARIANTS = {
    "legacy": ("legacy", None),
    "ast_blocks (defaults)": ("ast_blocks", None),
    "ast_blocks (80/100 lines)": ("ast_blocks", {"max_block_lines": 80, "max_total_lines": 100}),
}


def run(budgets, modes):
    q_map, manifest = load_candidates(), load_manifest()
    original = block_slicing.slice_blocks
    rows = []
    for variant, (strategy, limits) in VARIANTS.items():
        block_slicing.slice_blocks = partial(original, **limits) if limits else original
        try:
            for suite_name, suite_path in SUITES.items():
                suite = json.loads(suite_path.read_text(encoding="utf-8"))
                for mode, budget in zip(modes, budgets):
                    paths_ok = symbols_ok = 0
                    tokens, files, tiers, notes = [], [], Counter(), Counter()
                    for item in suite:
                        q = q_map[item["query_id"]]
                        texts = file_texts(manifest[(item["repo"], item["commit"])])
                        pool = [dict(c, content=texts.get(c["path"], "")) for c in q["candidates"][:85]]
                        opt = CUDPackOptimizer(BudgetConfig(focus_span_strategy=strategy))
                        selected = opt.pack_context(pool, budget_tokens=budget, query_text=q["query_text"], mode=mode)
                        total = sum(s.token_count for s in selected)
                        assert total <= budget
                        tokens.append(total)
                        files.append(len(selected))
                        by_path = {s.path: s for s in selected}
                        spans = item["annotated_spans"]
                        if all(sp["gold_path"] in by_path for sp in spans):
                            paths_ok += 1
                        if all(sp["gold_path"] in by_path and sp["target_symbol"].lower()
                               in (by_path[sp["gold_path"]].rendered_content or "").lower() for sp in spans):
                            symbols_ok += 1
                        for sp in spans:
                            s = by_path.get(sp["gold_path"])
                            tiers[s.tier.value if s else "not_packed"] += 1
                            if s and "[ast_blocks" in s.explanation:
                                notes[s.explanation.split("[", 1)[1].split("]", 1)[0].split(":")[0]
                                      + (": " + s.explanation.split("fallback: ", 1)[1].split("]")[0]
                                         if "fallback" in s.explanation else "")] += 1
                    rows.append({
                        "variant": variant, "suite": suite_name, "mode": mode, "budget": budget,
                        "queries": len(suite), "all_gold_files_packed": paths_ok,
                        "all_gold_symbols_visible": symbols_ok,
                        "mean_tokens_used": round(statistics.mean(tokens), 1),
                        "mean_files_packed": round(statistics.mean(files), 2),
                        "gold_file_tiers": dict(tiers), "gold_file_span_notes": dict(notes),
                    })
        finally:
            block_slicing.slice_blocks = original
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if not MANIFEST.exists():
        sys.exit("external/agent-retrieval-bench corpus not found")
    rows = run([4096, 8192], ["compact", "complete"])
    for r in rows:
        print(f"{r['variant']:<26} {r['suite']:<9} {r['mode']:<8} {r['budget']:>5}  files ok {r['all_gold_files_packed']:>2}/"
              f"{r['queries']}  symbols ok {r['all_gold_symbols_visible']:>2}/{r['queries']}  tokens {r['mean_tokens_used']:>7}"
              f"  files {r['mean_files_packed']:>5}  tiers {r['gold_file_tiers']}  notes {r['gold_file_span_notes']}")
    if args.out:
        Path(args.out).write_text(json.dumps({"rows": rows}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
