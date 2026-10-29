# RepoNeedle Stage 3.14: Runtime and Memory Reconciliation Audit

**Stage**: Stage 3.14 — Reproducibility, Historical Errata, and Independent Validation Gate  
**Date**: October 2026  
**Status**: Authoritative Technical Reconciliation  
**Branch**: `research-program`  
**Base Commit**: `bf7f4c8`  

---

## 1. Executive Summary

In Stage 3.5, memory profiling reported:
- `pallets/click`: 133 files, 98.6 MB process RSS (claimed under 100 MB ceiling).
- `caddyserver/caddy`: 250 files, 103.1 MB process RSS (+3.1 MB over 100 MB ceiling).

In Stage 3.12 and Stage 3.13, rigorous end-to-end benchmarking reported:
- `pallets/click`: 136 files, 113.4 MB peak process RSS.
- `caddyserver/caddy`: 605 files, 272.8 MB peak process RSS.

This audit establishes definitively that **the Stage 3.5 and Stage 3.13 numbers are not directly comparable because they evaluated fundamentally different repository snapshots under different corpus boundary rules.**

Specifically, the Stage 3.5 script [`research/stage3_5/audit_memory_reduction.py`](file:///F:/RepoNeedle/research/stage3_5/audit_memory_reduction.py#L109-L110) **artificially capped Caddy at 250 files** and truncated all file contents to 25,000 characters, omitting 58.7% of Caddy's true 605-file corpus. When the complete, canonical ARB v2 corpus is loaded without artificial clipping, total process Working Set is **272.8 MB**.

Furthermore, this audit confirms that **the claim of a universal 100 MB process memory ceiling is empirically invalid for large codebases in a 64-bit Python/NumPy/SciPy environment.** While pure inverted index heap structures consume $<20\text{ MB}$, the underlying CPython runtime, native shared libraries, and OS paging tables require 90–115 MB baseline working set before index structures are allocated.

---

## 2. Root Cause Analysis of Historical Discrepancies

### 2.1 Investigation Dimension 1: Repository Snapshots and File Inclusion Rules

Forensic inspection of [`research/stage3_5/audit_memory_reduction.py`](file:///F:/RepoNeedle/research/stage3_5/audit_memory_reduction.py#L96-L110) reveals the precise code that produced the Stage 3.5 numbers:

```python
# Lines 96-98: Truncation rule
docs = [
    FileDoc(path=p, content=t[:25000], is_test="test" in p.lower())
    for p, t in list(file_texts.items())[:max_files]
]

# Lines 109-110: Hardcoded caps
click_docs = load_arb_corpus_docs("pallets/click", max_files=133)
caddy_docs = load_arb_corpus_docs("caddyserver/caddy", max_files=250)
```

| Repository | Stage 3.5 Capped File Count | Stage 3.13 Canonical File Count | Omission Rate (%) | Stage 3.5 Content Clamping | Stage 3.13 Content Clamping |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `pallets/click` | 133 | 136 | 2.2% (3 files omitted) | Clamped to 25,000 chars | None (Full content) |
| `caddyserver/caddy` | 250 | 605 | **58.7% (355 files omitted)** | Clamped to 25,000 chars | None (Full content) |

In `caddyserver/caddy`, the Stage 3.5 benchmark loaded only 31,240 lines of code across 250 files, compared to 73,837 lines across 605 files in the full canonical corpus. Over 42,500 lines of Go code and their corresponding AST symbols, Go package manifests, and token vocabularies were omitted from the Stage 3.5 memory footprint.

### 2.2 Investigation Dimension 2: Machine Environment & Measurement Methods

Both Stage 3.5 and Stage 3.13 utilized the Windows kernel PSAPI `K32GetProcessMemoryInfo` API:

```python
class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ...
    ]
```

However, the execution lifecycle differed substantially:
1. **Sequential Cumulative State in Stage 3.5**:
   - `audit_memory_reduction.py` executed Django (5 files) $\to$ Click (133 files) $\to$ Caddy (250 files) sequentially within a single running Python process.
   - Although `gc.collect()` was invoked between iterations, the Windows virtual memory allocator does not immediately return decommitted memory pages back to the operating system's working set.
2. **Controlled Isolated Benchmarking in Stage 3.12 / 3.13**:
   - Measured cold start, baseline interpreter working set, peak during indexing, post-indexing retained working set, and 20 warmed retrieval iterations.
   - Verified that Python `tracemalloc` measures only tracked Python heap allocations, while Windows PSAPI `WorkingSetSize` captures all committed physical pages (including native C/C++ memory allocated by NumPy, SciPy, and OpenBLAS).

### 2.3 Investigation Dimension 3: Index Heap vs. Operating System Working Set

A critical distinction must be drawn between **Retained Index Heap** and **Process Working Set (RSS)**:

| Repository | Canonical File Count | Retained Index Heap (MB) | Python Heap Peak (MB) | Base CPython + Libs RSS (MB) | Total Process Working Set (MB) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `pallets/click` | 136 | 4.13 MB | 14.80 MB | 92.5 MB | **113.4 MB** |
| `gin-gonic/gin` | 122 | 3.70 MB | 13.20 MB | 92.5 MB | **120.0 MB** |
| `caddyserver/caddy` | 605 | 19.98 MB | 48.60 MB | 95.0 MB | **272.8 MB** |
| `tokio-rs/tokio` | 767 | 23.16 MB | 56.40 MB | 96.0 MB | **317.4 MB** |
| `etcd-io/etcd` | 1,431 | 52.58 MB | 118.20 MB | 98.0 MB | **609.2 MB** |

The actual RepoNeedle data structures (BM25 inverted index, subword vocabulary dictionary, document lengths array, and SciPy CSR matrices) are compact:
- For Click (136 files), the data structures require only **4.13 MB**.
- For Caddy (605 files), the data structures require only **19.98 MB**.

However, loading the Python runtime with `numpy`, `scipy`, and standard libraries immediately consumes ~90 MB RSS. When SciPy builds sparse CSR matrices during corpus vectorization, native C memory buffers are committed for row pointers (`indptr`), column indices (`indices`), and floating-point data (`data`), bringing peak process RSS to 272.8 MB for Caddy and 609.2 MB for etcd.

### 2.4 Investigation Dimension 4: The Fallacy of Delta RSS ($\Delta\text{RSS}$)

Stage 3.9 and Stage 3.12 uncovered an accounting anomaly where measuring "incremental RSS" (`rss_post - rss_pre`) frequently produced misleading values:
- On smaller repositories, `rss_post - rss_pre` occasionally reported **0.0 MB** because the OS memory manager satisfied allocations from pre-reserved page tables without faulting new physical frames.
- Conversely, on large repositories, deferred garbage collection and OpenBLAS thread pools caused sudden jumps in $\Delta\text{RSS}$.
- **Methodological Ruling**: Incremental $\Delta\text{RSS}$ is rejected as an unscientific metric. All future benchmarks must report **Total Process Resident Set Size (Peak Working Set)** alongside **Index Heap Delta**.

---

## 3. Disproof of the Universal 100 MB Process-Memory Ceiling

Stage 3.5 established an arbitrary target: *"Universal $\le 100\text{ MB}$ Process Working Set across all repository scales."*

Based on empirical evidence across 5 scale tiers (119 to 1,431 files):
1. **The 100 MB ceiling cannot be met on modern 64-bit CPython**: An idle Python 3.11 process with `numpy`, `scipy`, and `tiktoken` loaded occupies $80 - 95\text{ MB}$ of physical memory before any corpus data is loaded.
2. **Corpus scaling requires linear native allocations**: Vocabulary and document frequency tables scale with unique subwords ($V \approx 15,000 - 45,000$ terms). The CSR index requires $O(\text{nnz} \times 12\text{ bytes})$ plus dictionary overhead.
3. **Formal Policy**:
   > [!IMPORTANT]
   > RepoNeedle claims regarding memory are formally restricted to:
   > - **Retained Index Heap**: $\le 20\text{ MB}$ for repositories up to 600 files; $\le 55\text{ MB}$ for repositories up to 1,500 files.
   > - **Total Process Working Set (RSS)**: Scales from $110\text{ MB}$ (small repos, $\sim 100$ files) to $275\text{ MB}$ (medium repos, $\sim 600$ files) to $610\text{ MB}$ (large repos, $\sim 1,500$ files).
   > Any claim asserting a universal 100 MB process memory ceiling across arbitrary repositories is formally disproven and prohibited.

---

## 4. Comparability Ledger

A complete machine-readable audit is published in [`RUNTIME_MEMORY_RECONCILIATION.csv`](file:///F:/RepoNeedle/research/stage3_14/RUNTIME_MEMORY_RECONCILIATION.csv).

| Metric / Scenario | Stage 3.5 Artifact | Stage 3.13 Artifact | Comparability Status | Reconciliation Conclusion |
| :--- | :--- | :--- | :--- | :--- |
| `pallets/click` File Count | 133 files | 136 files | `NON_COMPARABLE` | Stage 3.5 omitted 3 files via `max_files=133`. |
| `caddyserver/caddy` File Count | 250 files | 605 files | `NON_COMPARABLE` | Stage 3.5 omitted 355 files (58.7%) via `max_files=250`. |
| File Content Processing | Clamped to 25k chars | Full file content | `NON_COMPARABLE` | Stage 3.5 truncated source code, undercounting lines. |
| Inverted Index Heap | 5.94 MB (Click), 7.61 MB (Caddy) | 4.13 MB (Click), 19.98 MB (Caddy) | `METHODOLOGICALLY_VALID` | Tracemalloc heap measurements confirm index structures are $<20\text{ MB}$. |
| Total Process RSS | 98.6 MB (Click), 103.1 MB (Caddy) | 113.4 MB (Click), 272.8 MB (Caddy) | `SUPERSEDED` | Stage 3.5 measured partial repos; Stage 3.13 measures canonical full repos. |
