# RepoNeedle Stage 3.20 — Resource & Timing Methodology

## 1. Benchmarking Protocol

All memory and latency measurements follow the canonical Stage 3.19 protocol:
- **Hardware Platform**: Windows 11 Enterprise (64-bit AMD64), Intel Core i-series (18 logical cores), 16 GB RAM.
- **Physical Memory Tracking**: Win32 PSAPI (`K32GetProcessMemoryInfo`) recording true OS Working Set and Peak Working Set.
- **Heap Tracking**: Python standard library `tracemalloc` isolating retained index structures from C-extension buffers.
- **High-Resolution Timer**: `time.perf_counter()` recording cold indexing duration and warm per-query latency.
- **Decoupled Architecture**: Strict separation between cold-start indexing (once per session) and warm retrieval.

## 2. Audited Repositories

1. `pallets/click` (Small, Python): 136 files, ~14k LOC
2. `caddyserver/caddy` (Medium, Go): 605 files, ~74k LOC
3. `etcd-io/etcd` (Large, Go): 1,431 files, ~162k LOC
