import json
import numpy as np

with open("research/v1_accuracy/m3_context_optimization/M3_BASELINE_SUMMARY.json", "r", encoding="utf-8") as f:
    s = json.load(f)

for b in ["2048", "4096", "8192", "16384", "32768"]:
    lat = s["budget_performance_summary"][b]["latency_ms"]
    print(f"Budget {b:>5}: Mean={lat['mean_latency_ms']:.2f} ms | Median={lat['median_latency_ms']:.2f} ms | P95={lat['p95_latency_ms']:.2f} ms | Max={lat['max_latency_ms']:.2f} ms")

print(f"Total evaluation time: {s['metadata']['total_evaluation_time_seconds']:.2f} seconds")

