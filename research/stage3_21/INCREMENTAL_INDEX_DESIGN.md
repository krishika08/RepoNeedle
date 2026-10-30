# Architectural Design Spec: Incremental AST Graph Indexing Engine

**Date:** 2026-10-30  
**Stage:** 3.21  
**Experiment ID:** `EXP-321-07`  
**Status:** SPECIFICATION COMPLETE (DESIGN PHASE — PRE-IMPLEMENTATION)  

---

## 1. Context & Motivation

In Stage 3.20 and Stage 3.21 resource audits, full cold-start indexing on large repositories (e.g., `etcd-io/etcd` with 1,431 files) required up to 126–229 seconds of CPU time and caused transient memory working set spikes up to 1.2 GB during full AST parsing and PageRank construction.

On production agent workflows (e.g. IDE sidecars, continuous agentic coding), re-parsing the entire codebase from scratch on every user query is unacceptable. However, typical agent edits modify only 1 to 5 files per turn. An incremental indexing architecture must achieve **sub-second warm updates** without compromising ranking determinism or graph fidelity.

---

## 2. High-Level Architecture & On-Disk Format

```
.reponeedle/
  ├── manifest.json         # Engine version, schema version, root commit, timestamp, dirty flag
  ├── index.db              # SQLite 3 in WAL mode (File metadata, symbols, call sites, edges)
  └── bm25_postings.bin     # Compact binary postings table with delta-encoded doc IDs
```

### 2.1 Schema Definition (`index.db`)
Using SQLite in Write-Ahead Logging (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`):

```sql
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    language TEXT NOT NULL,
    is_test INTEGER NOT NULL
);

CREATE TABLE symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    name TEXT NOT NULL,
    parent_class TEXT,
    is_method INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    arg_names TEXT,
    FOREIGN KEY(file_path) REFERENCES files(path) ON DELETE CASCADE
);

CREATE TABLE call_sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_path TEXT NOT NULL,
    caller_func TEXT,
    callee_name TEXT NOT NULL,
    is_attribute INTEGER NOT NULL,
    qualifier TEXT,
    start_line INTEGER NOT NULL,
    FOREIGN KEY(caller_path) REFERENCES files(path) ON DELETE CASCADE
);

CREATE TABLE edges (
    source_path TEXT NOT NULL,
    target_path TEXT NOT NULL,
    source_func TEXT,
    target_func TEXT,
    edge_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    PRIMARY KEY(source_path, target_path, source_func, target_func),
    FOREIGN KEY(source_path) REFERENCES files(path) ON DELETE CASCADE,
    FOREIGN KEY(target_path) REFERENCES files(path) ON DELETE CASCADE
);

CREATE INDEX idx_symbols_name ON symbols(name);
CREATE INDEX idx_call_sites_callee ON call_sites(callee_name);
CREATE INDEX idx_edges_source ON edges(source_path);
CREATE INDEX idx_edges_target ON edges(target_path);
```

---

## 3. Incremental Change Detection & Invalidation Strategy

### 3.1 Fast Stat Pre-Check
During incremental synchronization, RepoNeedle scans the filesystem:
1. `(file_path, st_mtime, st_size)` are compared against `files` table.
2. If `st_mtime` and `st_size` match, the file is skipped without reading disk contents ($O(N)$ directory stat).
3. If changed, SHA-256 content hash is computed. If hash matches cached `content_hash`, only metadata is updated.

### 3.2 Change Categorization
Files are partitioned into four mutation sets:
- $\Delta_{\text{add}}$: Present on disk, absent in cache.
- $\Delta_{\text{mod}}$: Present on disk and cache, hash differs.
- $\Delta_{\text{del}}$: Present in cache, absent on disk.
- $\Delta_{\text{ren}}$: Pair in $(\Delta_{\text{del}}, \Delta_{\text{add}})$ with identical SHA-256 hash.

### 3.3 Two-Tier Dependency Invalidation
When file $A$ changes:
1. **Tier 1 (Direct Purge):** Delete all records in `symbols` and `call_sites` where `file_path = A`. SQLite `ON DELETE CASCADE` automatically removes all edges where $A$ was caller or callee.
2. **Tier 2 (Referential Invalidation):**
   - Query all callers $B$ where $(B \to A) \in \text{edges}$.
   - Query all potential callers where call sites reference symbols previously defined in $A$.
   - Re-evaluate call resolution for affected call sites in $B$ without re-parsing $B$'s AST.
   - Insert new symbols and call sites extracted from $A$ and resolve against existing index.

---

## 4. Reliability, Atomicity & Concurrency

1. **Atomic Commit & Dirty Flag:**
   Before updating, `manifest.json` sets `"dirty": true`.
   All database changes execute within an SQLite transaction (`BEGIN IMMEDIATE ... COMMIT`).
   Once finalized, `manifest.json` updates `"dirty": false` atomically via file replacement (`os.replace`).
2. **Crash & Interrupted-Index Recovery:**
   If a crash occurs mid-indexing (power loss or SIGINT):
   Upon next boot, the engine detects `"dirty": true`.
   SQLite WAL safely rolls back uncommitted changes. The engine runs a standard incremental scan to reconcile disk state with the last clean transaction.
3. **Concurrent Readers:**
   SQLite WAL allows multiple reader processes (e.g., CLI queries, IDE plugins) to retrieve results concurrently while a background worker incrementally writes updates.
4. **Cache Versioning:**
   `CACHE_SCHEMA_VERSION = 1` is hardcoded. If the AST grammar, symbol extractor, or graph weights change in future releases, the version mismatch triggers an automatic clean rebuild.

---

## 5. Performance Targets & Stress Test Plan

### 5.1 Performance Budget for 10,000-File Repository

| Operation | Cold Indexing (First Run) | Warm Update (10 Files Modified) | Query Retrieval |
| :--- | :---: | :---: | :---: |
| **Duration Target** | $< 120\text{ s}$ | **$< 250\text{ ms}$** | **$< 20\text{ ms}$** |
| **Peak Working Set** | $< 400\text{ MB}$ | **$< 80\text{ MB}$** | **$< 120\text{ MB}$** |
| **On-Disk Footprint** | $< 35\text{ MB}$ | Stable | Stable |

### 5.2 Synthetic Scalability Test Plan
- **Labeling Mandate:** All generated synthetic test repositories must be explicitly labelled:
  `ENGINEERING STRESS FIXTURE — NOT BENCHMARK EVIDENCE`.
- **Harness:**
  1. Generate 1,000, 5,000, and 10,000-file polyglot mock codebases with circular dependencies and deep inheritance chains.
  2. Measure cold indexing time and initial database size.
  3. Mutate 10 core files (adding, renaming, deleting functions).
  4. Measure incremental update latency and assert graph parity with a clean rebuild.
  5. Simulate hard SIGKILL mid-index and verify clean transactional recovery.
