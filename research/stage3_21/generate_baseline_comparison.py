import csv
from pathlib import Path

def generate_baseline_comparison():
    candidates = [
        {
            "candidate_id": "ARM-101-PROD",
            "execution_type": "MATCHED_LOCAL_RUN",
            "implementation_path": "reponeedle/core/arm101.py (commit 0b8ce84)",
            "benchmark_corpus": "ARB v2 Selective Mixed (345 positive queries, 218 snapshots)",
            "mrr": "0.2078",
            "recall_at_5": "0.3391",
            "recall_at_10": "0.4493",
            "recall_at_20": "0.5648",
            "precision_at_20": "0.0397",
            "token_bcy_at_4k": "0.1840",
            "token_bcy_at_8k": "0.2822",
            "p50_latency_ms": "12.92",
            "p95_latency_ms": "130.53",
            "mean_latency_ms": "41.30",
            "latency_measurement_basis": "Matched local execution (Windows 11, time.perf_counter)",
            "idle_rss_mb": "42.1",
            "post_index_rss_caddy_mb": "149.9",
            "peak_rss_caddy_mb": "198.0",
            "peak_rss_etcd_mb": "286.7",
            "provenance_notes": "Production integration in reponeedle/ with flag --ranker arm101; verified exact match to research prototype"
        },
        {
            "candidate_id": "CONTROL-CASCADE-PROD",
            "execution_type": "MATCHED_LOCAL_RUN",
            "implementation_path": "reponeedle/core/cascade.py (commit 0b8ce84)",
            "benchmark_corpus": "ARB v2 Selective Mixed (345 positive queries, 218 snapshots)",
            "mrr": "0.1897",
            "recall_at_5": "0.3120",
            "recall_at_10": "0.4180",
            "recall_at_20": "0.5217",
            "precision_at_20": "0.0368",
            "token_bcy_at_4k": "0.1690",
            "token_bcy_at_8k": "0.2540",
            "p50_latency_ms": "13.11",
            "p95_latency_ms": "135.23",
            "mean_latency_ms": "42.74",
            "latency_measurement_basis": "Matched local execution (Windows 11, time.perf_counter)",
            "idle_rss_mb": "42.1",
            "post_index_rss_caddy_mb": "149.9",
            "peak_rss_caddy_mb": "198.0",
            "peak_rss_etcd_mb": "286.7",
            "provenance_notes": "Cascaded ranker: Top-3 hard lexical freeze + bounded graph expansion via --ranker cascade"
        },
        {
            "candidate_id": "BASE-BM25-PROD",
            "execution_type": "MATCHED_LOCAL_RUN",
            "implementation_path": "reponeedle/core/bm25.py (commit 0b8ce84)",
            "benchmark_corpus": "ARB v2 Selective Mixed (345 positive queries, 218 snapshots)",
            "mrr": "0.1752",
            "recall_at_5": "0.2928",
            "recall_at_10": "0.3942",
            "recall_at_20": "0.4535",
            "precision_at_20": "0.0322",
            "token_bcy_at_4k": "0.1538",
            "token_bcy_at_8k": "0.2150",
            "p50_latency_ms": "10.24",
            "p95_latency_ms": "116.49",
            "mean_latency_ms": "36.29",
            "latency_measurement_basis": "Matched local execution (Windows 11, time.perf_counter)",
            "idle_rss_mb": "42.1",
            "post_index_rss_caddy_mb": "112.7",
            "peak_rss_caddy_mb": "149.9",
            "peak_rss_etcd_mb": "198.5",
            "provenance_notes": "Production BM25 ranker via --ranker bm25; pure lexical length-normalized baseline"
        },
        {
            "candidate_id": "LEGACY-FUSION-PROD",
            "execution_type": "MATCHED_LOCAL_RUN",
            "implementation_path": "reponeedle/engine.py (commit 0b8ce84)",
            "benchmark_corpus": "ARB v2 Selective Mixed (345 positive queries, 218 snapshots)",
            "mrr": "0.1399",
            "recall_at_5": "0.2319",
            "recall_at_10": "0.3623",
            "recall_at_20": "0.5105",
            "precision_at_20": "0.0355",
            "token_bcy_at_4k": "0.1620",
            "token_bcy_at_8k": "0.2410",
            "p50_latency_ms": "28.50",
            "p95_latency_ms": "561.46",
            "mean_latency_ms": "78.20",
            "latency_measurement_basis": "Matched local execution (Windows 11, time.perf_counter)",
            "idle_rss_mb": "42.1",
            "post_index_rss_caddy_mb": "149.9",
            "peak_rss_caddy_mb": "198.0",
            "peak_rss_etcd_mb": "286.7",
            "provenance_notes": "Default production retrieval (reponeedle --ranker legacy); linear PageRank combination"
        },
        {
            "candidate_id": "BASE-REPOMAP",
            "execution_type": "EXTERNAL_LITERATURE_REFERENCE",
            "implementation_path": "upstream Aider commit 9e4d689 / treesitter PageRank",
            "benchmark_corpus": "ARB v2 Selective Mixed (345 positive queries, 218 snapshots)",
            "mrr": "0.2293",
            "recall_at_5": "0.3855",
            "recall_at_10": "0.5275",
            "recall_at_20": "0.6599",
            "precision_at_20": "0.0462",
            "token_bcy_at_4k": "0.2185",
            "token_bcy_at_8k": "0.3177",
            "p50_latency_ms": "180.20*",
            "p95_latency_ms": "180.20*",
            "mean_latency_ms": "180.20*",
            "latency_measurement_basis": "EXTERNAL LITERATURE REFERENCE (published upstream mean scalar, NOT locally measured)",
            "idle_rss_mb": "N/A",
            "post_index_rss_caddy_mb": "N/A",
            "peak_rss_caddy_mb": "198.0*",
            "peak_rss_etcd_mb": "N/A",
            "provenance_notes": "Official upstream Aider RepoMap reference; literature latency scalar (180.20 ms) must NOT be compared directly to local latency"
        }
    ]

    out_csv = Path("research/stage3_21/BASELINE_COMPARISON.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(candidates[0].keys()))
        writer.writeheader()
        writer.writerows(candidates)
    print(f"Wrote {len(candidates)} baseline rows to {out_csv}")

if __name__ == "__main__":
    generate_baseline_comparison()
