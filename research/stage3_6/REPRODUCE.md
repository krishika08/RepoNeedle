# REPONEEDLE STAGE 3.6: REPRODUCTION GUIDE

**Document ID**: `STAGE3-6-REPRO-001`  
**Date**: October 2026  
**Target Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program` / `research/stage3_6-audit`  
**Python Version**: Python 3.12.10 (tested on Windows 11 x64)  

This guide provides copy-pasteable PowerShell commands to reproduce every benchmark result, baseline reconciliation, statistical test, context packing analysis, selective abstention diagnostic, and memory measurement in RepoNeedle Stage 3.6.

---

## 1. ENVIRONMENT & PRECONDITIONS

### 1.1 Prerequisites
From repository root `F:\RepoNeedle`, ensure required dependencies are installed:
```powershell
pip install pytest pytest-cov networkx scipy numpy pydantic
```

### 1.2 Verify Frozen Tag Immutability & Commit Anchors
```powershell
# Verify frozen baseline tag
git rev-parse "v0.1.0-baseline^{commit}"
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

# Verify candidate freeze tag
git rev-parse "stage3-candidate-freeze^{commit}"
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca

# Verify Stage 3.5 commit exists
git rev-parse --verify 4f78cc3
# Expected: 4f78cc3658dfb5e338a5458579d38d5d7ef416e8
```

---

## 2. STEP-BY-STEP REPRODUCTION PIPELINE

### Step 1: Run Full Test Suite
Run the test suite to verify that all 236 unit, integration, and forensic reconciliation tests pass:
```powershell
pytest
# Expected: 236 passed in ~9.8s
```

Run the specific Stage 3.6 forensic reconciliation test:
```powershell
pytest tests/test_stage3_6_forensic_reconciliation.py -v
# Expected: 6 passed (commit ancestry, tag immutability, metric discrepancy, Candidate F retraction, Stage 3.15 safeguards, Candidate F isolation)
```

### Step 2: Reproduce Metric Reconciliation Table
Generates [`METRIC_RECONCILIATION.csv`](file:///F:/RepoNeedle/research/stage3_6/METRIC_RECONCILIATION.csv) reconciling the Stage 3.4 vs Stage 3.5 Recall@20 discrepancies:
```powershell
python research/stage3_6/scripts/generate_audit_deliverables.py
```

### Step 3: Reproduce Unified 4-System Ranking Evaluation
Evaluates `BASE-BM25`, `CAND-C`, `CAND-F`, and `BASE-REPOMAP` across all $N=345$ positive ARB v2 samples:
```powershell
python research/stage3_6/scripts/evaluate_systems.py
# Outputs:
#   research/stage3_6/PER_QUERY_RESULTS.csv
#   research/stage3_6/RANKING_RESULTS.csv
#   research/stage3_6/PER_QUERY_RESULTS.jsonl
```

### Step 4: Reproduce Repository-Clustered Paired Statistics
Computes paired differences, Wilcoxon signed-rank tests, and 10,000 repository-clustered bootstrap resamples:
```powershell
python research/stage3_6/scripts/compute_paired_statistics.py
# Outputs:
#   research/stage3_6/PAIRED_STATISTICAL_TESTS.csv
#   research/stage3_6/PAIRED_STATISTICS.md
#   research/stage3_6/STATISTICAL_COMPARISON.md
```

### Step 5: Reproduce Context Packing Audit
Evaluates greedy full-file, skeleton packing, and 0.5x doc-filtering across 4k, 8k, and 16k token budgets:
```powershell
python research/stage3_6/scripts/audit_context_packing.py
# Outputs:
#   research/stage3_6/CONTEXT_PACKING_RESULTS.csv
#   research/stage3_6/CONTEXT_PACKING_PER_QUERY.csv
```

### Step 6: Reproduce Selective Abstention Diagnostic
Evaluates default `SelectiveAbstainer` across 345 positive, 50 natural no-gold, and 32 counterfactual tasks:
```powershell
python research/stage3_6/scripts/evaluate_abstention.py
# Outputs:
#   research/stage3_6/ABSTENTION_RESULTS.csv
#   research/stage3_6/ABSTENTION_PER_QUERY.jsonl
```

### Step 7: Reproduce Polyglot Graph Scaling & Ripgrep Diagnostic
Profiles graph density across Clap, Tokio, Ruff, Caddy, and Vite, and verifies excision of hardcoded Ripgrep bypasses:
```powershell
python research/stage3_6/scripts/generate_graph_csv.py
# Outputs:
#   research/stage3_6/GRAPH_REPRODUCIBILITY_RESULTS.csv
```

### Step 8: Reproduce Native Process Memory and Latency Profiling
Profiles native Win32 process RSS and warm query latency:
```powershell
python research/stage3_6/scripts/audit_runtime_and_memory.py
# Outputs:
#   research/stage3_6/RUNTIME_AND_MEMORY.csv
```

---

## 3. CHECKSUM AND ARTIFACT INTEGRITY VERIFICATION

To verify artifact integrity, compare generated outputs against the canonical deliverables in `research/stage3_6/`:

| Deliverable Artifact | Expected Record Count | Verification Method |
| :--- | :---: | :--- |
| `STAGE3_6_DECISION_REPORT.md` | 16 Questions answered | Document review & checklist |
| `BASELINE_AND_CANDIDATE_REPRODUCTION.md` | 5 Sections | Comparison against canonical tables |
| `EVALUATION_PROTOCOL_AUDIT.md` | Complete forensic audit | Verified against commit `4f78cc3` |
| `METRIC_RECONCILIATION.csv` | 6 reconciled metrics | Confirms Hit@20 vs Recall@20 |
| `EXPERIMENT_REGISTRY.jsonl` | 8 registered experiments | `EXP-361` through `EXP-368` |
| `RANKING_RESULTS.csv` | 4 systems | Confirms MRR 0.1351 (Cand F) vs 0.2293 (RepoMap) |
| `PER_QUERY_RESULTS.jsonl` | 1,380 JSON records | 345 queries $\times$ 4 systems |
| `CONTEXT_PACKING_RESULTS.csv` | 15 packing policies | 4k, 8k, 16k budgets |
| `ABSTENTION_RESULTS.csv` | 5 query strata | Confirms 98.78% false accept rate |
| `GRAPH_REPRODUCIBILITY_RESULTS.csv` | 14 test rows | Confirms Ruff 112k vs 6.17M edges |
| `RUNTIME_AND_MEMORY.csv` | 12 scale rows | Micro, Click, Caddy memory |
| `STATISTICAL_COMPARISON.md` | 10,000 resamples | Confirms Cand F loss to RepoMap ($p < 0.0001$) |
| `FAILURE_ANALYSIS.md` | 5 failure modes | Structural, lexical, and graph failures |
| `GIT_AND_ENVIRONMENT_MANIFEST.md` | Complete manifest | Hardware, OS, dependencies |
