# REPONEEDLE STAGE 3.5: EXPERIMENTAL REPRODUCTION GUIDE

This guide provides step-by-step instructions to reproduce all Stage 3.5 experiments, metrics, and CSV deliverables on Windows using PowerShell and Python 3.11+.

---

## 1. PRE-REQUISITES & ENVIRONMENT VERIFICATION

Open PowerShell in the repository root (`F:\RepoNeedle`):

```powershell
# 1. Verify working directory
cd F:\RepoNeedle

# 2. Verify git branch and commit status
git status
git branch --show-current
# Expected: On branch research-program

# 3. Verify immutable frozen tags are intact
git rev-parse v0.1.0-baseline
# Expected: 8e004257be7eb95455d3f27f8a37f5b3fc019054

git rev-parse stage3-candidate-freeze
# Expected: cd7f3b0631ce1b0aa447d216503c0dd5eb3526a6

# 4. Verify existing unit test suite passes 100%
python -m pytest tests/ -q
# Expected: 44 passed in ~3.5s
```

---

## 2. REPRODUCE POLYGLOT GRAPH RETRIEVAL EXPERIMENTS

### 2.1 Verify Polyglot Graph Connectivity
Tests manifest parsing (`Cargo.toml`, `go.mod`, `package.json`) and crate entrypoint linking across 5 multi-crate polyglot codebases:

```powershell
python -u research\stage3_5\test_polyglot_graph.py
```
**Expected Output:**
- `astral-sh/ruff`: 56 crates detected, 112,665 structural edges (pruned from 6.17M).
- `tokio-rs/tokio`: 11 crates detected, 15,222 structural edges.
- `clap-rs/clap`: 7 crates detected, 2,439 structural edges.
- `caddyserver/caddy`: Go modules detected, 4,833 structural edges.
- `vitejs/vite`: 250 packages detected, 2,670 structural edges.

### 2.2 Run Polyglot Graph Evaluator (`GRAPH_RETRIEVAL_RESULTS.csv`)
Evaluates the diagnostic `BurntSushi/ripgrep` failure, 232 polyglot samples, and the full 345 positive ARB v2 samples across BM25, Candidate A, Candidate C, Candidate E, Candidate F, and RepoMap:

```powershell
python -u -W ignore research\stage3_5\evaluate_graph_retrieval.py
```
**Generated Artifact**: `research/stage3_5/GRAPH_RETRIEVAL_RESULTS.csv`  
**Expected Highlights:**
- Ripgrep Diagnostic MRR: Candidate C $= 0.0000 \to$ Candidate F $= \mathbf{1.0000}$.
- Polyglot Subset MRR ($N=232$): Candidate C $= 0.1965 \to$ Candidate F $= \mathbf{0.2125}$ (+8.1% relative gain).
- Full ARB v2 MRR ($N=345$): Candidate C $= 0.2040 \to$ Candidate F $= \mathbf{0.2152}$ (matches/exceeds RepoMap 0.2140).

---

## 3. REPRODUCE CONTROLLED CONTEXT PACKING EVALUATION

Evaluates the 5 context packing policies across 4k, 8k, and 16k token budgets on budget-saturating codebases (`pallets/click`, `caddyserver/caddy`, `tokio-rs/tokio`, $N=77$ queries):

```powershell
python -u -W ignore research\stage3_5\evaluate_context_packing.py
```
**Generated Artifact**: `research/stage3_5/CONTEXT_PACKING_RESULTS.csv`  
**Expected Highlights:**
- **4k Budget**: Skeletons increase file recall from $0.1602$ (Full Files Only) to $\mathbf{0.3474}$ (+116.8% gain).
- **8k Budget**: Skeletons + 0.5x Doc Filter achieves $\mathbf{0.4762}$ file recall vs. $0.3658$ for Full Files Only (+30.2% gain), while retaining $0.3835$ BCY token yield.
- **Documentation Filter**: Reduces distractor doc files from $0.8$ to $0.0$, doubling the source-to-documentation token ratio to $7,669$.

---

## 4. REPRODUCE PROCESS WORKING SET (RSS) & RESOURCE AUDIT

Profiles literal Process Working Set (RSS) via Windows kernel API (`K32GetProcessMemoryInfo`), Python heap peak via `tracemalloc`, and query latency across Micro, Medium, and Large repository scales:

```powershell
python -u -W ignore research\stage3_5\audit_memory_reduction.py
```
**Generated Artifact**: `research/stage3_5/RUNTIME_AND_MEMORY.csv`  
**Expected Highlights:**
- Micro Fixture (Synthetic Django, 5 files): Process RSS $\mathbf{81.7\text{ MB}}$ (PASSED $\le 100\text{ MB}$).
- Medium Repo (pallets/click, 133 files): Process RSS $\mathbf{98.6\text{ MB}}$ (PASSED $\le 100\text{ MB}$).
- Large Repo (caddyserver/caddy, 250 files): Process RSS $\mathbf{103.1\text{ MB}}$ (FAILED by $+3.1\text{ MB}$ over literal ceiling).
- Index Data Structure Retained Heap: $5.94\text{ MB}$ (Click) and $7.61\text{ MB}$ (Caddy).

---

## 5. REPRODUCE BASELINE VERIFICATION & REGISTRY AUDIT

Inspect the machine-readable experiment registry and baseline reconciliation report:

```powershell
# Inspect experiment registry
Get-Content research\stage3_5\EXPERIMENT_REGISTRY.jsonl

# Review baseline reproduction report
Get-Content research\stage3_5\BASELINE_REPRODUCTION.md
```

All figures match the historical Stage 2 ablation matrix and Stage 3 candidate freeze records.

