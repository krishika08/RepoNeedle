# RepoNeedle Stage 3.19 — Memory and Scalability Audit

**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Date:** 2026-10-30  
**Audit Status:** COMPLETE  
**Primary Conclusion:** Universal <100 MB Process RSS claim is empirically invalidated; Retained Index Heap ($<20\text{ MB}$) is explicitly decoupled from Process Working Set ($198\text{--}364\text{ MB}$).

---

## 1. Executive Summary & Status of Historical Claims

Historical Stage 3.5 research claimed that RepoNeedle operates under a universal $100\text{ MB}$ process memory ceiling. Stage 3.14 through Stage 3.18 formally retracted this claim. This Stage 3.19 audit independently verifies memory consumption using authentic, unclipped repository corpora.

### Key Empirical Findings:
1. **The 100 MB Ceiling is Invalid for Complete Repositories:** In a 64-bit Python 3.12 / NumPy / SciPy environment, CPython and standard imported libraries consume $72\text{--}78\text{ MB}$ of working set at idle baseline before any repository files are loaded.
2. **Artificial Clamping in Historical Benchmarks:** Stage 3.5 achieved $<100\text{ MB}$ by artificially capping `caddyserver/caddy` to 250 files and truncating file content to 25,000 characters (omitting 58.7% of the codebase).
3. **True Process RSS:** When Caddy's full 605-file codebase is loaded and indexed without clamping, isolated process RSS is **`198.0 MB`** (with peak working set reaching **`272.8 MB`** during graph compilation and matrix factorization).
4. **Index Heap vs. Working Set Separation:** Pure Python index structures (BM25 posting lists, token dictionaries, and CSR arrays) consume only **`19.98 MB`** on Caddy, but OS virtual memory paging, OpenBLAS threads, and native runtime overhead require an additional $178\text{ MB}$ of physical working set.

---

## 2. Empirical Scalability Across Repository Scales

Measurements were performed on live unconstrained repositories across Python, Go, and Rust:

| Repository | Scale Category | Language | File Count | LOC | Retained Index Heap | Peak Python Heap | Process RSS (Baseline) | Process RSS (Post-Index) | Peak Process RSS | Indexing Time (s) | Query P50 (ms) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `pallets/click` | Small | Python | 136 | 14,092 | 4.13 MB | 14.8 MB | 72.4 MB | **112.7 MB** | 113.4 MB | 0.85 s | 1.55 ms |
| `gin-gonic/gin` | Small / Medium | Go | 122 | 11,756 | 3.70 MB | 13.2 MB | 72.8 MB | **118.5 MB** | 120.0 MB | 0.71 s | 1.05 ms |
| `caddyserver/caddy` | Medium / Large | Go | 605 | 73,837 | 19.98 MB | 48.6 MB | 75.5 MB | **198.0 MB** | **272.8 MB** | 18.25 s | 12.92 ms |
| `tokio-rs/tokio` | Large | Rust | 767 | 94,743 | 23.16 MB | 56.4 MB | 76.2 MB | **245.0 MB** | **317.4 MB** | 22.40 s | 18.45 ms |
| `etcd-io/etcd` | Very Large | Go | 1,431 | 161,747 | 52.58 MB | 118.2 MB | 78.0 MB | **364.1 MB** | **609.2 MB** | 42.10 s | 25.10 ms |

---

## 3. Dissecting Heap vs. Resident Set Size (RSS)

A persistent source of benchmark confusion was the conflation of Python heap allocations (measured via `tracemalloc`) with operating system Process Resident Set Size (measured via Win32 PSAPI `K32GetProcessMemoryInfo`):

```mermaid
flowchart TD
    subgraph Total Process Working Set: 198.0 MB (Caddy)
        subgraph CPython & Native Runtime Overhead: ~178 MB
            A[Base CPython 3.12 Runtime: ~75 MB]
            B[NumPy / SciPy C-Extensions: ~45 MB]
            C[OpenBLAS Thread Buffers & Page Tables: ~35 MB]
            D[Native AST & Regex C-Buffers: ~23 MB]
        end
        subgraph Tracked Python Objects: ~20 MB
            E[BM25 Term Inverted Lists: ~6.2 MB]
            F[Subword Vocabulary & Hash Dict: ~4.5 MB]
            G[Function Call Graph Adjacency Lists: ~5.1 MB]
            H[FileDoc Metadata & Paths: ~4.1 MB]
        end
    end
```

### Methodological Rule:
> [!CAUTION]
> Never substitute Python heap size for Process RSS. AI coding agent sidecars run inside containerized or local user environments where operating system memory limits (cgroups or process quotas) kill processes based on total **Process Resident Set Size (RSS)**, not Python heap.

---

## 4. Scalability Limits & Engineering Recommendations

1. **Working Set Guidance:**
   - For repositories under 200 files: allocate $150\text{ MB}$ RSS.
   - For repositories up to 1,000 files: allocate $350\text{ MB}$ RSS.
   - For repositories $>1,000$ files (e.g. `etcd`): allocate $500\text{--}700\text{ MB}$ peak RSS.
2. **Memory Growth Scaling Law:**
   - Index heap scales near-linearly: $\approx 35\text{ KB}$ per indexed source file.
   - Process peak working set scales superlinearly during graph matrix construction if dense arrays or unpruned global edges are constructed.
3. **Zero Clamping Mandate:** Future benchmarks must never truncate source files or artificially cap discovery counts to manufacture a lower memory footprint.
