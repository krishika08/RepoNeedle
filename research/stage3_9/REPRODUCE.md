# REPONEEDLE STAGE 3.9: COMPREHENSIVE REPRODUCTION GUIDE

This guide provides deterministic, step-by-step instructions to reproduce all Gate A reconciliation artifacts and Gate B cascaded ranking ablation experiments for RepoNeedle Stage 3.9.

---

## 1. PRE-FLIGHT ENVIRONMENT & WORKSPACE CHECK

Verify the repository state:
```bash
git checkout research-program
git rev-parse HEAD
# Expected base: 174c26048e31fff73d780f0528797485e352b860 (Stage 3.8 commit)
```

Confirm that frozen baseline and candidate tags remain untouched:
```bash
git rev-parse "v0.1.0-baseline^{commit}"
# Must output: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse "stage3-candidate-freeze^{commit}"
# Must output: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

Ensure Python dependencies are installed:
```bash
python -m pip install -e .
python -m pip install numpy scipy networkx pytest
```

---

## 2. REPRODUCING GATE A: PROVENANCE & METRIC RECONCILIATION

Gate A reconciles the historical metric discrepancies between Stage 3.5 ($MRR = 0.2152$) and Stage 3.8 ($MRR = 0.1351$).

To execute the Gate A provenance reconciliation and clean-room independent verifier:
```bash
python research/stage3_9/generate_gate_a_deliverables.py
```

Outputs generated in `research/stage3_9/`:
- `PROVENANCE_AUDIT.md`: Complete Git lineage analysis proving `4f78cc3` (Stage 3.5) is a direct ancestor of `174c260` (Stage 3.8).
- `METRIC_RECONCILIATION.csv`: 4-system reconciliation matrix identifying the exact causes of metric divergences.
- `PER_QUERY_RANKING_DIFFERENCES.csv`: Row-level comparison across all 345 positive ARB v2 queries tracking reciprocal rank deltas.
- `INDEPENDENT_METRIC_VERIFICATION.md`: Clean-room metric calculation validated against hand-calculated multi-gold fixtures.
- `STAGE3_9_GATE_A_DECISION.md`: Formal Gate A sign-off verdict: `PASS — METRICS RECONCILED`.

---

## 3. REPRODUCING GATE B: CASCADED RETRIEVAL ABLATION EXPERIMENTS

Gate B evaluates the `CascadedRanker` architecture (`reponeedle/core/cascade.py`), which freezes BM25 top-3 ranks and applies degree-normalized graph expansion only to eligible ranks ($\ge 4$).

### A. Run Regression Unit Tests (9 Tests)
```bash
pytest tests/test_stage3_9_cascade.py -v
```
Verifies:
1. Top-3 BM25 ranking preservation invariant (100.0% guarantee).
2. Degree normalization ($1/\sqrt{d_{\text{out}} \cdot d_{\text{in}}}$) attenuation of hub nodes.
3. Package fencing preventing cross-package symbol pollution.
4. Same-name symbol collision isolation.
5. Evidence-backed test-to-implementation discovery for `code2test`.
6. Safe handling of empty, disconnected, and single-file graphs.
7. Multi-language manifest parsing (`Cargo.toml`, `go.mod`, `package.json`).
8. Deterministic ranking across repeated invocations.
9. Full backwards compatibility of the public API.

### B. Run Full Regression Suite (126 Tests)
```bash
pytest tests/
```
Confirms all 126 tests across the entire repository pass with 0 failures.

### C. Run Full-Corpus Ablation Matrix (345 Positive ARB v2 Queries)
```bash
python research/stage3_9/evaluate_cascade_ablation.py
```
Evaluates 7 configurations across all 345 positive instances and 218 repository snapshots:
1. `BASE-BM25` (Canonical baseline)
2. `BASE-REPOMAP` (Pinned version `9e4d689`)
3. `CAND-C` (Canonical Stage 3.7 baseline)
4. `CAND-F` (Canonical Stage 3.7 baseline)
5. `CAND-CASCADE` (Full proposed cascaded architecture)
6. `CASCADE-NO-GRAPH` (Ablation: Top-3 freeze without graph expansion)
7. `CASCADE-UNNORMALIZED` (Diagnostic control: Top-3 freeze with unnormalized diffusion)

Outputs generated in `research/stage3_9/`:
- `CASCADE_ABLATIONS.csv`: Aggregate metrics summary table (MRR, Recall@5/10/20, Hit@20, P@5, BCY@8k, Latency p50).
- `PER_QUERY_CASCADE_RESULTS.csv`: Per-query reciprocal ranks and first relevant rank comparisons.
- `LATENCY_AND_MEMORY.csv`: Latency distribution percentiles (p50, p95, mean) and memory footprint.

### D. Generate Task and Language Breakdowns & Failure Analysis
```bash
python research/stage3_9/generate_gate_b_deliverables.py
```
Outputs generated in `research/stage3_9/`:
- `TASK_AND_LANGUAGE_BREAKDOWNS.csv`: Detailed breakdowns across the 4 task tracks (`code2test`, `comment2context`, `trace2code`, `edit2ripple`) and 5 languages (Python, Go, Rust, TypeScript, JavaScript).
- `FAILURE_ANALYSIS.md`: Win/tie/loss ledger and ranking dynamics analysis.
- `STAGE3_9_DECISION_REPORT.md`: Authoritative synthesis answering all evaluation questions.
