# RepoNeedle Stage 3.13: Reproduction Guide

This guide provides clean, copy-pasteable commands to reproduce all Stage 3.13 evidence reconciliation artifacts, data tables, memory profiles, and test suite executions.

## 1. Verify Git State & Frozen Baseline Tags

```powershell
# Verify current branch and clean working tree
git status

# Verify immutable baseline tags
git rev-parse "v0.1.0-baseline^{commit}"
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse "stage3-candidate-freeze^{commit}"
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 2. Execute the Full Regression Test Suite

Run the full project test suite synchronously:

```powershell
pytest
```

Expected output:
- **171 passed** in ~7–8 seconds.

---

## 3. Regenerate Stage 3.13 Reconciliation Deliverables

To reassemble all cross-stage per-query comparisons, statistical tests, discrepancy ledgers, and runtime memory tables:

```powershell
python research/stage3_13/generate_stage3_13_reconciliation.py
```

Generated deliverables:
- `research/stage3_13/RECONCILIATION_REPORT.md`
- `research/stage3_13/METRIC_DISCREPANCIES.csv`
- `research/stage3_13/CANONICAL_PROTOCOL.md`
- `research/stage3_13/RUN_PROVENANCE.json`
- `research/stage3_13/PER_QUERY_RESULTS.csv`
- `research/stage3_13/STATISTICAL_ANALYSIS.json`
- `research/stage3_13/RUNTIME_AND_MEMORY.csv`
- `research/stage3_13/TEST_AUDIT.md`
- `research/stage3_13/FAILURE_ANALYSIS.md`
- `research/stage3_13/DECISION_REPORT.md`

---

## 4. Run Isolated Memory & Latency Profiling

To profile fresh, isolated process memory and query latency on Click, Caddy, and Etcd:

```powershell
python -c "
import os, sys, json, tracemalloc, ctypes
from ctypes import wintypes
from pathlib import Path

ROOT_DIR = Path('.')
ARB_DIR = ROOT_DIR / 'external' / 'agent-retrieval-bench'
sys.path.insert(0, str(ARB_DIR / 'src'))
sys.path.insert(0, str(ROOT_DIR))

from agent_retrieval_bench.baseline import read_jsonl
from reponeedle.models import FileDoc
from reponeedle.core.graph import RepoGraph
from reponeedle.engine import RepoNeedleEngine
from research.stage3_11.function_graph_engine import FunctionGraphEngine

class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]

def get_rss():
    h = ctypes.windll.kernel32.OpenProcess(0x0410, False, os.getpid())
    c = PROCESS_MEMORY_COUNTERS_EX()
    c.cb = ctypes.sizeof(c)
    ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
    ctypes.windll.kernel32.CloseHandle(h)
    return c.WorkingSetSize / (1024*1024), c.PeakWorkingSetSize / (1024*1024)

tracemalloc.start()
base_rss, _ = get_rss()
print(f'Baseline Python Interpreter RSS: {base_rss:.1f} MB')

manifest_path = ARB_DIR / 'data' / 'corpus' / 'v2_selective_mixed' / 'corpus_manifest.jsonl'
manifest = {json.loads(l)['repo']: ARB_DIR / json.loads(l)['chunks_path'] for l in open(manifest_path, encoding='utf-8') if l.strip()}

for target in ['pallets/click', 'caddyserver/caddy', 'etcd-io/etcd']:
    chunks = read_jsonl(manifest[target])
    docs = [FileDoc(path=c['path'], content=c.get('text','')[:25000], symbols=[], imports=[]) for c in chunks if c.get('path')]
    engine = RepoNeedleEngine.from_documents(docs)
    fg = FunctionGraphEngine()
    fg.build_graph(docs)
    rss, peak = get_rss()
    heap_cur, _ = tracemalloc.get_traced_memory()
    print(f'{target:20s} | Docs: {len(docs):4d} | RSS: {rss:.1f} MB | Peak: {peak:.1f} MB | Heap: {heap_cur/(1024*1024):.1f} MB')
"
```
