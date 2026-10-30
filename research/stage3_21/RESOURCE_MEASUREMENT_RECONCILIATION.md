# Process Memory & Resource Measurement Reconciliation

**Date:** 2026-10-30  
**Stage:** 3.21  
**Experiment ID:** `EXP-321-04`  
**Status:** RECONCILED & EMPIRICALLY AUDITED  

---

## 1. Executive Summary

Phase 4 resolves the accounting discrepancy identified between the Stage 3.20 resource table (which reported etcd process RSS of `286.7 MB`) and the general leaderboard (which displayed a scalar of `198.0 MB`).

By executing multi-process benchmarks in completely isolated Python processes, Stage 3.21 measured the 7 primary memory dimensions across small (`pallets/click`), medium (`caddyserver/caddy`), and large (`etcd-io/etcd`) codebases.

---

## 2. Root Cause of the 198.0 MB vs. 286.7 MB Discrepancy

1. **The Origin of `198.0 MB`:**
   In Stage 3.19 and Stage 3.20, the single leaderboard summary column labeled "Process RSS (MB)" was populated using the empirical measurement for **`caddyserver/caddy`** (605 files, post-indexing / query RSS `~175–198 MB`).
2. **The Origin of `286.7 MB`:**
   The detailed Phase 7 resource audit specifically profiled **`etcd-io/etcd`** (1,431 files), where post-indexing RSS was measured at `286.7 MB` (and `312.1 MB` in fresh isolated cold-start).
3. **The Methodological Error:**
   Past reports conflated a single-repository benchmark (`caddyserver/caddy`) with an architectural upper bound. **There is no universal memory ceiling of 100 MB or 198 MB.** Memory scales monotonically with repository file count, AST symbol volume, and graph edge density.

---

## 3. Authoritative Isolated Process Memory Measurements

Measurements were captured via separate subprocess invocations (`subprocess.run`), ensuring zero memory contamination from preceding repository indices. Windows PSAPI (`GetProcessMemoryInfo`) and Python `tracemalloc` were queried at each lifecycle phase:

| Lifecycle Metric | Definition | `pallets/click` (136 files) | `caddyserver/caddy` (605 files) | `etcd-io/etcd` (1,431 files) |
| :--- | :--- | :---: | :---: | :---: |
| **Idle Process RSS** | Baseline Python process before loading repo chunks | 66.0 MB | 66.1 MB | 65.7 MB |
| **Post-Indexing RSS** | Working set size after index creation (`RepoNeedleEngine.from_documents`) | **105.2 MB** | **175.1 MB** | **312.1 MB** |
| **Peak Indexing RSS** | Highest working set observed during AST parsing & PageRank | 162.7 MB | 513.7 MB | 1,230.9 MB |
| **Peak Query RSS** | Working set size during warm query retrieval (`retrieve()`) | **105.9 MB** | **175.8 MB** | **312.5 MB** |
| **Total Peak Working Set** | Lifetime maximum working set (`PeakWorkingSetSize`) | 162.7 MB | 513.7 MB | 1,230.9 MB |
| **Python Retained Heap** | Net memory allocated for index structures (`tracemalloc`) | **11.1 MB** | **35.9 MB** | **96.0 MB** |
| **Peak Python Heap** | Maximum heap allocated during tokenization & AST extraction | 37.3 MB | 169.7 MB | 442.9 MB |
| **Cold Indexing Time** | Time to parse files, build AST graph, and fit BM25 | 9.61 s | 65.59 s | 229.04 s |

---

## 4. Key Engineering & Memory Scalability Insights

1. **Python Heap vs. OS Process RSS:**
   The retained Python heap allocated for index data structures (BM25 posting lists, NetworkX graphs, symbol lookup tables) is relatively small: **11.1 MB** for Click, **35.9 MB** for Caddy, and **96.0 MB** for etcd.
   However, operating systems (particularly Windows CRT allocator and CPython pymalloc) allocate memory in virtual memory pages that are not immediately released back to the OS upon garbage collection. Consequently, OS Process RSS settles at **105 MB**, **175 MB**, and **312 MB**, respectively.
2. **Indexing Spikes vs. Steady-State Querying:**
   During the one-time cold indexing phase, full AST parsing, regex evaluation, and PageRank power-iteration cause transient memory spikes (up to 513 MB on Caddy and 1.2 GB on etcd). Once indexing completes and intermediate parsing trees are garbage collected, steady-state retrieval operates with negligible memory growth during warm queries (+0.7 MB).
3. **Multi-Process Isolation Hygiene:**
   When repositories are benchmarked sequentially within a single long-lived process, CPython retains committed memory pages from earlier repositories, artificially inflating the baseline RSS for subsequent repositories (e.g., Caddy baseline appeared as 99 MB and etcd as 112 MB in sequential runs). True isolated measurement requires separate processes.
