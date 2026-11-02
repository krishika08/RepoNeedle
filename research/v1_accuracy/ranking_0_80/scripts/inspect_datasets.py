"""
Inspection script for Baseline, Candidates, and Benchmark queries.
"""
import gzip
import json
import os
import sys

def inspect_datasets():
    print("=== INSPECTING DATASETS ===")
    
    # 1. PER_SAMPLE_RESULTS.jsonl
    with open("reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl", "r", encoding="utf-8") as f:
        first_line = f.readline()
        data = json.loads(first_line)
        print("PER_SAMPLE_RESULTS keys:", list(data.keys()))
        print("Sample query_id:", data.get("query_id"))
        print("Sample repo:", data.get("repo"))
        print("Sample gold_targets:", data.get("gold_targets"))
        print("Sample reponeedle metrics:", {k: v for k, v in data.items() if "reponeedle" in k or "mrr" in k or "rank" in k})

    # 2. Frozen candidates
    with gzip.open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        first_line = f.readline()
        data = json.loads(first_line)
        print("\nfrozen_m1_candidates keys:", list(data.keys()))
        print("query_id:", data.get("query_id"))
        print("num candidates:", len(data.get("candidates", [])))
        if data.get("candidates"):
            print("First candidate:", json.dumps(data["candidates"][0], indent=2))

    # 3. Check queries and manifests
    manifest_path = "external/agent-retrieval-bench/data/corpus/v2_selective_mixed/corpus_manifest.jsonl"
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            print("\nManifest first line:", f.readline()[:200])

    # 4. Check query source files in ARB or elsewhere
    arb_dir = "external/agent-retrieval-bench"
    print(f"\nChecking {arb_dir}:")
    for root, dirs, files in os.walk(arb_dir):
        for file in files:
            if file.endswith((".jsonl", ".json", ".csv")):
                path = os.path.join(root, file)
                print(f"  {path} ({os.path.getsize(path)} bytes)")

if __name__ == "__main__":
    inspect_datasets()

