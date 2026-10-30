# Stage 3.21 Authoritative Reproduction Guide

**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Starting Commit:** `0b8ce84`  

This guide provides exact terminal commands to reproduce all forensic findings, parity audits, memory measurements, and test suites in Stage 3.21.

---

## 1. Environment & Pre-requisite Verification

```powershell
# 1. Verify clean git status and starting commit
git status
git log -1 --format="%H %s"

# 2. Verify frozen immutable baseline tags
git rev-parse "v0.1.0-baseline^{commit}" "stage3-candidate-freeze^{commit}"
# Expected:
# 8e0042553a14b6e3c6cf5b35823c4da84181a8e9
# cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 2. Full Test Suite Execution

Run the complete 236-test regression and production-quality test suite:

```powershell
pytest tests/
# Expected: 236 passed in ~10s
```

---

## 3. ARB v2 Task Distribution & Query Manifest Reproduction

Recompute the task counts and verify the 345 positive benchmark queries directly from raw source files:

```powershell
python -c "
import json
from pathlib import Path
from collections import Counter

arb_dir = Path('external/agent-retrieval-bench')
subsets = ['v2_code2test', 'v2_comment2context', 'v2_trace2code', 'v2_edit2ripple']

samples = []
for s in subsets:
    for line in open(arb_dir / 'data' / 'benchmark' / s / 'samples.jsonl', encoding='utf-8'):
        if line.strip():
            row = json.loads(line)
            row['task'] = s
            samples.append(row)

print('Total Samples:', len(samples))
print('Task Distribution:', Counter(s['task'] for s in samples))
"
# Expected:
# Total Samples: 345
# Task Distribution: Counter({'v2_code2test': 106, 'v2_trace2code': 101, 'v2_comment2context': 80, 'v2_edit2ripple': 58})
```

---

## 4. ARM-101 Bit-for-Bit Research-to-Production Parity Verification

Verify exact mathematical parity between production and research ARM-101:

```powershell
python research/stage3_21/verify_parity.py
# Expected:
# Total Queries Audited:      345
# Exact Matches (Delta == 0): 345 / 345
# Aggregate Delta:            0.0000000000
# Overall Run Fingerprint:    25769a23a06bbb68588e8be0f52c5e1c2c13344bee825257ecaf1f4059d4b295
```

---

## 5. Multi-Process Isolated Memory Profiling

Measure isolated process RSS, peak working set, and Python heap across Click, Caddy, and etcd in fresh subprocesses:

```powershell
python research/stage3_21/benchmark_isolated_memory.py
```

---

## 6. Official ContextBench Ingestion Status Check

Verify that the external validation gate remains correctly guarded:

```powershell
python research/external_data/contextbench/validate_contextbench.py
# Expected exit code: 1 / 2 (BLOCKED - DATA ACCESS)
```
