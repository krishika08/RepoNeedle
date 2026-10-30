# REPONEEDLE STAGE 3.6: DECISION REPORT

**Document ID**: `STAGE3-6-DECISION-001`  
**Date**: October 2026  
**Stage**: Stage 3.6 — Candidate F Reproducibility, Baseline Reconciliation & Evaluation Integrity Audit  
**Workspace**: `F:\RepoNeedle`  
**Active Branch**: `research-program`  
**Dedicated Audit Branch**: `research/stage3_6-audit`  
**Target Candidate**: Candidate F (`CAND-F`)  
**Historical Implementation SHA**: `4f78cc3658dfb5e338a5458579d38d5d7ef416e8` (Stage 3.5)  
**Overall Candidate Verdict**: **`NOT REPRODUCIBLE (RETRACTED ON UNCONSTRAINED CORPUS)`**  
**Independent Validation Status**: **`BLOCKED`** (Official ContextBench dataset unavailable; ARB v2 is a development/regression benchmark only)  

---

## 1. COMPREHENSIVE QUESTION-BY-QUESTION AUDIT FINDINGS

### Question 1: What was actually inspected?
The audit inspected:
- Complete Git commit history from Stage 2 through Stage 3.5 and Stage 3.21.
- All historical reports and data outputs in `research/stage3_4/`, `research/stage3_5/`, and `research/stage3_6/`.
- Production and core engine modules:
  - Lexical and BM25 index: [`reponeedle/core/lexical.py`](file:///F:/RepoNeedle/reponeedle/core/lexical.py)
  - Subword semantic retrieval: [`reponeedle/core/semantic.py`](file:///F:/RepoNeedle/reponeedle/core/semantic.py)
  - Polyglot graph construction & score diffusion: [`reponeedle/core/graph.py`](file:///F:/RepoNeedle/reponeedle/core/graph.py)
  - Context packing & token budgeting: [`reponeedle/core/budget.py`](file:///F:/RepoNeedle/reponeedle/core/budget.py)
  - Selective abstention: [`reponeedle/core/abstention.py`](file:///F:/RepoNeedle/reponeedle/core/abstention.py)
  - End-to-end orchestration: [`reponeedle/engine.py`](file:///F:/RepoNeedle/reponeedle/engine.py)
- Historical benchmark data and evaluation scripts:
  - `external/agent-retrieval-bench/` (345 positive tasks across 4 tracks + 82 selective zero-gold tasks).
  - Version-pinned official Aider RepoMap reference (`9e4d689`).
  - Stage 2 ablation records (`EXP-016` BM25 baseline).

### Question 2: Which historical commits were available?
All six historical milestone commits were verified and available:
- Stage 2: `d826152e8e515f53e8ff356c3c7b9468e2140052`
- Stage 3.1: `36879c6ec7a3b37803f2780e2d142ca1dca5cb24`
- Stage 3.2: `623c3bfcf2e65d21a97e416a2d989f6b92f7c00e`
- Stage 3.3: `50bcfd7b7dbd76ce1e98d89e5fc82ea389ceca3d`
- Stage 3.4: `878ff68cfe8f3430ac3cc13278d277184f049df6`
- Stage 3.5: `4f78cc3658dfb5e338a5458579d38d5d7ef416e8`
- Frozen Tag `v0.1.0-baseline`: `8e0042553a14b6e3c6cf5b35823c4da84181a8e9`
- Frozen Tag `stage3-candidate-freeze`: `cd7f3b01e28695f9a9357e0815069e0eae85baca`

### Question 3: Which experiments were successfully reproduced?
- **EXP-361 (Baseline Audit)**: Reconciled metric discrepancies between Stage 3.4 and Stage 3.5.
- **EXP-362 (Unified 4-System Benchmark)**: Successfully executed all 4 systems on the unconstrained 345 positive ARB v2 queries.
- **EXP-363 (Polyglot Graph Scaling)**: Reproduced graph node/edge counts across Clap, Tokio, Ruff, Caddy, and Vite.
- **EXP-364 (Context Packing Audit)**: Reproduced token yield under 4k, 8k, and 16k budgets across greedy, skeleton, and doc-filter policies.
- **EXP-365 (Runtime & Memory Profiling)**: Reproduced native Win32 process RSS and latency across Micro, Medium, and Large repos.
- **EXP-366 (Paired Bootstrap Statistics)**: Computed 10,000 repository-clustered resamples and Wilcoxon signed-rank tests.
- **EXP-367 (Selective Abstention Diagnostic)**: Evaluated 345 positive, 50 natural no-gold, and 32 counterfactual tasks.
- **EXP-368 (Ripgrep Micro-Fixture Diagnostic)**: Discovered and excised hardcoded bypasses in `reponeedle/core/graph.py`.

### Question 4: Which metrics changed between Stage 3.4 and Stage 3.5?
- **BM25 Recall@20**: Reported as `0.4467` in Stage 3.4, jumped to `0.4928` in Stage 3.5.
- **RepoMap Recall@20**: Reported as `0.6306` in Stage 3.4, dropped to `0.5681` in Stage 3.5.
- **Candidate C Recall@20**: Retained identically as `0.5516`.
- **Candidate F MRR**: Claimed `0.2152` in Stage 3.5 (beating RepoMap `0.2140`).

### Question 5: Why did they change?
1. **Binary Hit@20 vs Fractional Recall@20 Substitution**: Stage 3.5 calculated binary Hit@20 ($170/345 = 0.4928$ for BM25; $196/345 = 0.5681$ for RepoMap; $195/345 = 0.5652$ for Candidate F) and erroneously labeled it as "Recall@20". True multi-target fractional recall is `0.4549` for BM25 and `0.6599` for RepoMap.
2. **Artificial Candidate Pool Restriction**: Stage 3.5 passed `tests_only = True` for `code2test`, removing code distractors.
3. **Hardcoded Reference Constant**: Stage 3.5 hardcoded `0.2140` as a static constant for RepoMap from an older v1.1 subset. Official RepoMap actually achieves `0.2293` MRR.

### Question 6: Were all methods compared on comparable evaluation populations?
**No.** In Stage 3.5, Candidate F was evaluated with hardcoded ripgrep rules and test-only candidate filtering, while RepoMap metrics were drawn from conflicting subsets and mixed definitions. Under the Stage 3.6 canonical evaluation, all 4 methods were evaluated against the exact same 100% unconstrained candidate pool.

### Question 7: What are the reproducible Candidate F metrics?
On the clean 345-query ARB v2 benchmark:
- **MRR**: `0.1351` (Stage 3.5 claimed `0.2152`).
- **Recall@1**: `0.0116`
- **Recall@5**: `0.1824` (Stage 3.5 claimed `0.2667`).
- **Recall@10**: `0.3316` (Stage 3.5 claimed `0.3942`).
- **Recall@20**: `0.5078` (Stage 3.5 claimed `0.5652`).
- **Precision@5**: `0.0504`, **Precision@10**: `0.0452`, **Precision@20**: `0.0358`.
- **BCY@8k (Overall)**: `0.0159` (Stage 3.5 claimed `0.3184`).
- **Median Query Latency**: `32.42 ms` (Mean: `44.8 ms`, p95: `566.28 ms`).
- **Peak Process RSS**: `179.4 MB` (Stage 3.5 claimed universally `< 100 MB`).

### Question 8: Is its MRR advantage over RepoMap statistically supported?
**No. Candidate F does NOT have an advantage over RepoMap.**
Authoritative RepoMap decisively outperforms Candidate F:
- RepoMap MRR: `0.2293` vs Candidate F MRR: `0.1351` ($\Delta = -0.0942$).
- Repository-clustered 95% Bootstrap CI: `[-0.1171, -0.0579]`.
- Wilcoxon signed-rank test: $W = 10,240.0, p = 1.46 \times 10^{-13}$ (decisively favors RepoMap).
- Head-to-head queries: RepoMap wins 226, Candidate F wins 99, ties 20.

### Question 9: What are its context-packing trade-offs?
- At 8k tokens, Candidate F's structural skeleton + doc-filter packing achieves **0.3835 token yield** on queries where relevant files are retrieved, but drops to **0.0159 across all 345 queries** due to ranking dropouts.
- Full-file greedy packing achieves 0.3486 token yield on hits with 100% symbol survival, while skeleton packing achieves 0.3835 with 98.7% symbol survival (+10.0% yield improvement on retrieved files).

### Question 10: Is its abstention implementation reliable?
**No. The default `SelectiveAbstainer` fails closed on zero-gold queries:**
- Genuine Positive Queries ($N=345$): 345 accepted (100.0% accept rate, 0.0% false abstain).
- Natural No-Gold Queries ($N=50$): 1 rejected (2.0% rejection rate), 49 false accepted (**98.0% false accept rate**).
- Counterfactual Wrong-Repo ($N=32$): 0 rejected (0.0% rejection rate), 32 false accepted (**100.0% false accept rate**).
- Overall False Accept Rate on Zero-Gold: **98.78%**.
- Abstention Precision: 100.0%, Recall: 1.22%, F1: 0.0241.
- Selective Risk: 19.01% (81 of 426 accepted queries were hallucinations).
- Brier Score: 0.2050, Expected Calibration Error (ECE): 0.2376.

### Question 11: Are the polyglot graph results reproducible?
- **Yes for Manifest Parsing & Edge Scaling**: Parsing `Cargo.toml`, `go.mod`, and `package.json` is verified and resilient. Sparse entrypoint linking keeps Ruff at 112,665 edges (avoiding the 6.17M edge naive explosion).
- **No for the Ripgrep Diagnostic**: The reported 1.0000 MRR on `BurntSushi/ripgrep` was generated by hardcoded string checks in `reponeedle/core/graph.py:425-435`. Excising the bypass collapses MRR to 0.0000 because the synthetic 2-file fixture lacks manifest files.

### Question 12: Are the latency and memory measurements trustworthy?
- **Latency**: Candidate F warm query median latency is **32.42 ms** (faster than RepoMap's 180.20 ms). Cold start query latency is ~80 ms.
- **Memory**: The claim that Candidate F universally runs under 100 MB RSS is **unsupported**. While small repositories (Click: 100.3 MB) hover near the boundary, larger repositories (Caddy: 103.5 MB retained, 190.0 MB peak; Ruff: 179.4 MB peak) substantially exceed 100 MB.

### Question 13: Which reported claims remain unsupported?
1. Claim that Candidate F outperforms RepoMap in MRR (Refuted: RepoMap 0.2293 vs Cand F 0.1351).
2. Claim that Candidate F achieves 0.5652 Recall@20 (Refuted: 0.5652 was binary Hit@20; fractional recall is 0.5078).
3. Claim that Candidate F universally consumes < 100 MB RSS (Refuted: peak RSS reaches 190 MB).
4. Claim that Candidate F achieves 1.0000 MRR on Ripgrep (Refuted: resulted from hardcoded bypasses).
5. Claim that Selective Abstention reliably filters unanswerable queries (Refuted: false accept rate is 98.78%).

### Question 14: What did the test suite establish?
The entire regression test suite passes cleanly: **236 / 236 tests passed** (including `tests/test_stage3_6_forensic_reconciliation.py`). The tests prove that all historical tag immutability safeguards, manifest parsers, and component ablations function as designed.

### Question 15: What is the final Candidate F verdict?
**`NOT REPRODUCIBLE (RETRACTED ON UNCONSTRAINED CORPUS)`**  
Candidate F is formally rejected as a winning production architecture. It fails to beat pure BM25 (0.1351 vs 0.1735, $p=0.0483$), fails to beat Candidate C (0.1351 vs 0.1399, $p=0.1164$), and is decisively beaten by RepoMap (0.1351 vs 0.2293, $p < 0.0001$).

### Question 16: What should Stage 3.7 investigate?
Stage 3.7 must investigate:
1. **Component Isolation & Failure Diagnosis**: Deconstruct why polyglot graph diffusion degraded BM25 ranking (identifying hub attenuation, symbol inflation, and length normalization penalties).
2. **Decoupling Symbol Matching from BM25 Document Length**: Prevent regex symbol extraction from artificially inflating file lengths.
3. **Calibrated Confidence Thresholding for Abstention**: Implement query-length and corpus-size normalized z-scores to replace rigid fixed thresholds.

---

## 2. GOVERNANCE & METRIC RECONCILIATION SUMMARY

| System ID | Query Population | MRR | Recall@20 | BCY@8k | Median Latency | Peak RSS | Audit Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BASE-BM25`** | 345 | 0.1735 | 0.4549 | 0.0493 | 20.85 ms | 145.2 MB | **REPRODUCED** |
| **`CAND-C`** | 345 | 0.1399 | 0.5105 | 0.0188 | 31.50 ms | 168.5 MB | **REPRODUCED** |
| **`CAND-F`** | 345 | 0.1351 | 0.5078 | 0.0159 | 32.42 ms | 179.4 MB | **NOT REPRODUCED (RETRACTED)** |
| **`BASE-REPOMAP`**| 345 | 0.2293 | 0.6599 | 0.0652 | 180.20 ms | 265.0 MB | **REPRODUCED (AUTHORITATIVE WINNER)** |

*Signed and Certified by RepoNeedle Evidence Integrity Audit — October 2026*
