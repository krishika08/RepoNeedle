"""Audit of modified historical research artifacts against HEAD.
"""

import subprocess
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent

def get_head_bytes(rel_path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"HEAD:{rel_path}"], cwd=ROOT)

def get_work_bytes(rel_path: str) -> bytes:
    with open(ROOT / rel_path, "rb") as f:
        return f.read()

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

files = [
    "research/stage3_7/PER_QUERY_RESULTS.jsonl",
    "research/stage3_7/EXPERIMENT_REGISTRY.jsonl",
    "research/stage3_8/EXPERIMENT_REGISTRY.jsonl",
    "research/stage3_7/REPRODUCE.md",
    "research/stage3_7/STAGE3_7_DECISION_REPORT.md",
    "research/stage3_8/REPRODUCE.md",
    "research/stage3_8/STAGE3_8_DECISION_REPORT.md"
]

print("=== SHA-256 Checksums ===")
for p in files:
    hb = get_head_bytes(p)
    wb = get_work_bytes(p)
    print(f"\nFile: {p}")
    print(f"  HEAD: bytes={len(hb)}, SHA256={sha256_bytes(hb)}")
    print(f"  WORK: bytes={len(wb)}, SHA256={sha256_bytes(wb)}")
    print(f"  Byte-match: {hb == wb}")

print("\n=== Detailed Analysis of Priority JSONL Files ===")

# 1. research/stage3_7/PER_QUERY_RESULTS.jsonl
print("\n--- research/stage3_7/PER_QUERY_RESULTS.jsonl ---")
head_lines_pqr = get_head_bytes("research/stage3_7/PER_QUERY_RESULTS.jsonl").decode("utf-8").strip().split("\n")
work_lines_pqr = get_work_bytes("research/stage3_7/PER_QUERY_RESULTS.jsonl").decode("utf-8").strip().split("\n")
print(f"Record count: HEAD={len(head_lines_pqr)}, WORK={len(work_lines_pqr)}")

head_objs_pqr = [json.loads(l) for l in head_lines_pqr if l.strip()]
work_objs_pqr = [json.loads(l) for l in work_lines_pqr if l.strip()]

head_qids = [o["query_id"] for o in head_objs_pqr]
work_qids = [o["query_id"] for o in work_objs_pqr]
print(f"Query IDs exact order match: {head_qids == work_qids}")
print(f"Unique queries: HEAD={len(set(head_qids))}, WORK={len(set(work_qids))}")

# Check baseline systems
base_systems = ["BASE-BM25", "CAND-C", "CAND-F", "BASE-REPOMAP"]
baseline_diffs = []
for h_o, w_o in zip(head_objs_pqr, work_objs_pqr):
    qid = h_o["query_id"]
    for s in base_systems:
        h_sys = h_o["systems"][s]
        w_sys = w_o["systems"][s]
        for k, v in h_sys.items():
            if w_sys.get(k) != v:
                baseline_diffs.append((qid, s, k, v, w_sys.get(k)))

print(f"Discrepancies in baseline systems ({', '.join(base_systems)}): {len(baseline_diffs)}")

work_sys_set = set()
for o in work_objs_pqr:
    work_sys_set.update(o["systems"].keys())
print(f"Systems present in WORK: {sorted(list(work_sys_set))}")

# 2. research/stage3_7/EXPERIMENT_REGISTRY.jsonl
print("\n--- research/stage3_7/EXPERIMENT_REGISTRY.jsonl ---")
head_lines_reg7 = get_head_bytes("research/stage3_7/EXPERIMENT_REGISTRY.jsonl").decode("utf-8").strip().split("\n")
work_lines_reg7 = get_work_bytes("research/stage3_7/EXPERIMENT_REGISTRY.jsonl").decode("utf-8").strip().split("\n")
print(f"Record count: HEAD={len(head_lines_reg7)}, WORK={len(work_lines_reg7)}")
head_objs_reg7 = [json.loads(l) for l in head_lines_reg7 if l.strip()]
work_objs_reg7 = [json.loads(l) for l in work_lines_reg7 if l.strip()]
print("HEAD records:")
for o in head_objs_reg7:
    print(f"  {o.get('experiment_id')}: candidate={o.get('candidate')} status={o.get('status')} desc={o.get('description')}")
print("WORK records:")
for o in work_objs_reg7:
    print(f"  {o.get('experiment_id')}: system_name={o.get('system_name')} mrr={o.get('metrics', {}).get('mrr')} desc={o.get('description')}")

# 3. research/stage3_8/EXPERIMENT_REGISTRY.jsonl
print("\n--- research/stage3_8/EXPERIMENT_REGISTRY.jsonl ---")
head_lines_reg8 = get_head_bytes("research/stage3_8/EXPERIMENT_REGISTRY.jsonl").decode("utf-8").strip().split("\n")
work_lines_reg8 = get_work_bytes("research/stage3_8/EXPERIMENT_REGISTRY.jsonl").decode("utf-8").strip().split("\n")
print(f"Record count: HEAD={len(head_lines_reg8)}, WORK={len(work_lines_reg8)}")
head_objs_reg8 = [json.loads(l) for l in head_lines_reg8 if l.strip()]
work_objs_reg8 = [json.loads(l) for l in work_lines_reg8 if l.strip()]
print("HEAD records:")
for o in head_objs_reg8:
    print(f"  {o.get('experiment_id')}: desc={o.get('description')}")
print("WORK records:")
for o in work_objs_reg8:
    print(f"  {o.get('experiment_id')}: system_name={o.get('system_name')} mrr={o.get('metrics', {}).get('mrr')} desc={o.get('description')}")

