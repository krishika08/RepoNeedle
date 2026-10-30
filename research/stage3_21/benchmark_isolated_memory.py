"""
Stage 3.21: Isolated Multi-Process Memory & Resource Measurement.
Spawns fresh, isolated Python subprocesses for each repository to measure:
- Idle process RSS
- Post-indexing RSS
- Peak indexing RSS
- Peak query RSS
- Total peak process working set
- Python heap (tracemalloc)
- Retained index memory
"""

import sys
import os
import gc
import json
import time
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ARB_DIR = ROOT_DIR / "external" / "agent-retrieval-bench"

WORKER_SCRIPT = """
import sys
import os
import gc
import json
import time
import ctypes
from ctypes import wintypes
from pathlib import Path
import tracemalloc

ROOT_DIR = Path(sys.argv[1])
sys.path.insert(0, str(ROOT_DIR))

from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.engine import RepoNeedleEngine

class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]

def get_mem_mb():
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x0410, False, os.getpid())
        if not h:
            return 0.0, 0.0
        c = PROCESS_MEMORY_COUNTERS_EX()
        c.cb = ctypes.sizeof(c)
        ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
        ctypes.windll.kernel32.CloseHandle(h)
        return c.WorkingSetSize / (1024.0 * 1024.0), c.PeakWorkingSetSize / (1024.0 * 1024.0)
    except Exception as e:
        return 0.0, 0.0

repo_filter = sys.argv[2]
chunks_path = Path(sys.argv[3])

gc.collect()
idle_rss, _ = get_mem_mb()

# Load chunks
chunks = [json.loads(l) for l in open(chunks_path, encoding='utf-8') if l.strip()]
file_texts = {}
for c in chunks:
    p = c.get('path')
    t = c.get('text', '')
    if p and (p not in file_texts or len(t) > len(file_texts[p])):
        file_texts[p] = t

docs = []
for p, t in file_texts.items():
    syms, imps = RepoGraph.extract_polyglot_symbols(t[:25000], p)
    docs.append(FileDoc(path=p, content=t[:25000], symbols=syms, imports=imps, is_test='test' in p.lower()))

tracemalloc.start()
t0_idx = time.perf_counter()
engine = RepoNeedleEngine.from_documents(docs)
idx_time = time.perf_counter() - t0_idx

retained_heap, peak_heap = tracemalloc.get_traced_memory()
tracemalloc.stop()

post_idx_rss, peak_idx_rss = get_mem_mb()

queries = ["handle request server", "parse options configuration", "error handler context", "client session connect", "storage backend log"]

# Run queries
for q in queries:
    _ = engine.retrieve(q, ranker="arm101")

peak_query_rss, total_peak_ws = get_mem_mb()

result = {
    "repository": repo_filter,
    "file_count": len(file_texts),
    "indexing_time_s": round(idx_time, 2),
    "idle_rss_mb": round(idle_rss, 1),
    "post_indexing_rss_mb": round(post_idx_rss, 1),
    "peak_indexing_rss_mb": round(peak_idx_rss, 1),
    "peak_query_rss_mb": round(peak_query_rss, 1),
    "total_peak_working_set_mb": round(total_peak_ws, 1),
    "python_heap_retained_mb": round(retained_heap / (1024.0 * 1024.0), 1),
    "python_heap_peak_mb": round(peak_heap / (1024.0 * 1024.0), 1),
}
print(json.dumps(result), flush=True)
"""

def run_isolated_benchmarks():
    manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
    targets = [
        ("pallets/click", "click"),
        ("caddyserver/caddy", "caddy"),
        ("etcd-io/etcd", "etcd"),
    ]

    manifest = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            manifest[row["repo"]] = ARB_DIR / row["chunks_path"]

    results = []

    worker_file = ROOT_DIR / "research" / "stage3_21" / "_mem_worker.py"
    with open(worker_file, "w", encoding="utf-8") as f:
        f.write(WORKER_SCRIPT)

    for repo_name, short_name in targets:
        chunks_path = manifest.get(repo_name)
        if not chunks_path or not chunks_path.exists():
            print(f"Skipping {repo_name}, not found in manifest", flush=True)
            continue

        print(f"Running isolated memory measurement for {repo_name}...", flush=True)
        proc = subprocess.run(
            [sys.executable, str(worker_file), str(ROOT_DIR), repo_name, str(chunks_path)],
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            print(f"ERROR in worker for {repo_name}:\n{proc.stderr}", flush=True)
            continue

        data = json.loads(proc.stdout.strip())
        print(f"  -> {repo_name}: idle={data['idle_rss_mb']}MB, post_idx={data['post_indexing_rss_mb']}MB, peak_query={data['peak_query_rss_mb']}MB, total_peak_ws={data['total_peak_working_set_mb']}MB, heap_retained={data['python_heap_retained_mb']}MB", flush=True)
        results.append(data)

    if worker_file.exists():
        worker_file.unlink()

    return results

if __name__ == "__main__":
    res = run_isolated_benchmarks()
    print("\nSummary Results:", flush=True)
    print(json.dumps(res, indent=2), flush=True)
