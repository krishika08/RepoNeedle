"""Render markdown tables for the supplemental product-aligned evaluation from its JSON outputs.

Reads reports/experimental/phase1_product_aligned_evaluation/{aggregate,confidence_intervals,fidelity}.json
and writes TABLES.md next to them, so every number in REPORT.md is traceable to machine-readable output.
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "reports" / "experimental" / "phase1_product_aligned_evaluation"
GROUPS = ["overall", "comment2context", "code2test", "trace2code", "edit2ripple"]
SYS_LABEL = {
    "rn_fragment": "RepoNeedle, fragment input",
    "rn_wholefile": "RepoNeedle, whole-file input",
    "bm25_fragment": "BM25, fragment input (file unit)",
    "bm25_wholefile": "BM25, whole-file input (file unit)",
    "bm25_chunks": "BM25, all chunks → file by max (official baseline)",
}
METRICS = ["mrr", "recall@5", "recall@10", "recall@20"]


def main():
    agg = json.loads((OUT / "aggregate.json").read_text(encoding="utf-8"))
    cis = json.loads((OUT / "confidence_intervals.json").read_text(encoding="utf-8"))
    lines = ["# Tables (generated from aggregate.json and confidence_intervals.json)", ""]
    for g in GROUPS:
        a = agg[g]
        lines += [f"## {g} (queries = {a['n_queries']}, repositories = {a['n_repositories']})", "",
                  "| System | MRR | Recall@5 | Recall@10 | Recall@20 |", "| :--- | :---: | :---: | :---: | :---: |"]
        for s, label in SYS_LABEL.items():
            lines.append(f"| {label} | " + " | ".join(f"{a[s][m]:.4f}" for m in METRICS) + " |")
        lines += ["", "| Packed context (CUD-Pack, 8,000 tokens) | Files packed | Utilisation | Gold coverage | Queries with ≥1 gold packed | Unselected files |",
                  "| :--- | :---: | :---: | :---: | :---: | :---: |"]
        for rep in ["fragment", "wholefile"]:
            p = a[f"packed_{rep}"]
            lines.append(f"| {rep} input | {p['n_files']:.1f} | {p['utilisation']:.1%} | {p['gold_coverage']:.1%} | {p['success']:.1%} | {p['unselected_files']:.0f} (no positions assigned) |")
        lines += ["", "| Comparison (paired, repo-clustered 95% CI) | Metric | Mean Δ | W / T / L | 95% CI | CI excludes 0 |",
                  "| :--- | :--- | :---: | :---: | :---: | :---: |"]
        for c in cis[g]:
            lines.append(f"| {c['label']} | {c['metric']} | {c['mean_diff']:+.4f} | {c['wins']} / {c['ties']} / {c['losses']} | "
                         f"[{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}] | {'**yes**' if c['excludes_zero'] else 'no'} |")
        lat = a["latency_ms"]
        lines += ["", "| Latency per query (ms, 4 concurrent shards) | Mean | p50 |", "| :--- | :---: | :---: |"]
        for k, v in lat.items():
            lines.append(f"| {k} | {v['mean']:.1f} | {v['p50']:.1f} |")
        lines.append("")
    (OUT / "TABLES.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT / 'TABLES.md'}")


if __name__ == "__main__":
    main()
