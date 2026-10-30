# RepoNeedle Stage 3.20 — Executive Decision Report

**Document ID**: `STAGE3-20-DECISION-001`  
**Stage**: Stage 3.20 (Research-to-Production Reconciliation, ARM-101 Integration & End-to-End Parity)  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Starting Commit**: `89a3ef4`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`) — **VERIFIED UNCHANGED**  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`) — **VERIFIED UNCHANGED**  

---

## 1. Formal Decision Verdict

```
================================================================================
FINAL GOVERNANCE VERDICT:
[A — PRODUCTION-INTEGRATED AND INTERNALLY VERIFIED]
================================================================================
```

### 1.1 Decision Rationale
1. **Architectural Gap Closed**: The research-to-production gap identified in Stage 3.19 is fully resolved. ARM-101 and the verified function-call graph engine have been implemented directly inside the core library:
   - `reponeedle/core/attenuation.py`
   - `reponeedle/core/function_graph.py`
   - `reponeedle/core/arm101.py`
   - Zero imports from `research/` inside `reponeedle/` (100% decoupling).
2. **Deterministic Parity Across 5 Languages and Edge Cases**: Multi-language fixtures (Python, Rust, Go, TypeScript, Java) and adversarial edge cases (cyclic imports, duplicate symbol names, syntax errors, empty repositories, large files) confirm 100% exact ranking parity between the research prototype and production code (`PRODUCTION_PARITY_RESULTS.csv`).
3. **Full ARB v2 Benchmark Parity Gate Passed**:
   - Production ARM-101 MRR: **`0.2078`**
   - Research ARM-101 MRR: **`0.2078`**
   - Parity Delta: **`0.000010`** ($\le 0.0010$ requirement strictly satisfied).
   - Exact query-level match rate: **345 / 345 (100.0%)**.
4. **Controlled Production Deployment via Feature Flag**:
   - Production ranker activated via `--ranker arm101` / `engine.retrieve(..., ranker="arm101")`.
   - Default retrieval behavior remains `"legacy"` until external validation is complete, ensuring 100% backward compatibility.
5. **Real Isolated Resource Footprint Verified**:
   - Measured via Win32 PSAPI: `pallets/click` (104.9 MB RSS, P50 14.1 ms), `caddyserver/caddy` (149.9 MB RSS, P50 6.7 ms), `etcd-io/etcd` (286.7 MB RSS, P50 18.9 ms).
   - High index compaction confirmed with index heap <40 MB on medium repos.
6. **Package Packaging & Isolated Installation Smoke Tests Verified**:
   - Built PEP 517 wheel `dist/reponeedle-0.1.0-py3-none-any.whl`.
   - Installed in clean isolated virtual environment; executed CLI binary verifying fail-closed abstention and high-precision graph retrieval.
7. **External ContextBench Gate Maintained**:
   - ContextBench status remains **`BLOCKED — OFFICIAL DATA ACQUISITION`**. ARB v2 is recognized strictly as an internal development benchmark.

---

## 2. Canonical Production Leaderboard

| Rank | System ID | Status | MRR | Recall@5 | Recall@20 | Hit@20 | Token BCY@8k | Latency Mean (ms) | Isolated RSS Caddy (MB) |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `BASE-REPOMAP` | EXTERNAL_REFERENCE_LEADER | **0.2293** | **0.3855** | **0.6599** | **0.7478** | **0.3177** | 180.20 | 198.0 |
| 2 | **`ARM-101-PROD`** | **PRODUCTION_INTEGRATED_VERIFIED** | **0.2078** | **0.3391** | **0.5648** | **0.6493** | **0.2822** | **41.30** | **149.9** |
| — | `ARM-101-RESEARCH` | RESEARCH_PROTOTYPE_CHAMPION | 0.2078 | 0.3391 | 0.5648 | 0.6493 | 0.2822 | 41.30 | 198.0 |
| 3 | `BASE-BM25-PROD` | PRODUCTION_BASELINE_VERIFIED | 0.1752 | 0.2928 | 0.4535 | 0.5275 | 0.2150 | 36.29 | 149.9 |
| 4 | `LEGACY-FUSION-PROD` | PRODUCTION_LEGACY_REFERENCE | 0.1399 | 0.2319 | 0.5105 | 0.5826 | 0.2410 | 78.20 | 149.9 |
| 5 | `CAND-F` | FORMALLY_INVALIDATED | 0.1351 | 0.2290 | 0.5078 | 0.5797 | 0.2336 | 82.50 | 198.0 |

---

## 3. Direction for Subsequent Research

1. **ContextBench Official Acquisition**: The sole remaining blocker to external validation is obtaining the official ContextBench dataset.
2. **Default Ranker Transition Gate**: Following external validation on ContextBench, promote `arm101` from opt-in feature flag to standard engine default.
