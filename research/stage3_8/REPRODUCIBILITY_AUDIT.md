# Stage 3.8: Forensic Reproducibility & Historical Discrepancy Audit

**Document ID**: `STAGE3-8-AUDIT-001`  
**Stage**: Stage 3.8 — Reproducibility Lock, Metric Reconciliation, and Evidence Audit  
**Date**: October 28, 2026  
**Status**: Authoritative Forensic Audit  
**Evaluated Revisions**:  
- Stage 3.5 Commit: `4f78cc3658dfb5e338a5458579d38d5d7ef416e8`  
- Stage 3.6 Commit: `cbe6c4919c993ea7a05f910b3c88fa9c9ba79890`  
- Stage 3.7 Commit: `60fb4c94bcdbe31bb23f417ee5c9189f08aa50fe`  
- Pinned Baseline Tag: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`)  
- Candidate Freeze Tag: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`)  

---

## 1. Executive Summary

This forensic audit investigates the historical discrepancies between the retrieval numbers published in Stage 3.5 and the newly audited results established in Stage 3.6, Stage 3.7, and Stage 3.8. Every disputed metric is evaluated individually to determine its source script, Git revision, configuration, reproducibility, physical cause, and authoritative disposition.

The audit proves that earlier inflated performance claims in Stage 3.5 arose from three compounding errors:
1. **Transcribed Historical Proxies**: In Stage 3.5, baseline numbers for Candidate C and Candidate A were copied verbatim from isolated Stage 2 micro-ablations on Python-only corpora, rather than re-computed dynamically alongside Candidate F.
2. **Structural Edge Explosion & Dilution**: In Stage 3.5, polyglot regex symbol and import extraction was introduced in `RepoGraph`. While effective on small repositories like `pallets/click`, on large Go and JavaScript repositories (`etcd-io/etcd`, `caddyserver/caddy`, `eslint/eslint`), regex parsing generated tens of thousands of spurious edges. PageRank diffused away from true targets onto generic hub files (`backend.go`, `types.go`), and BM25 document length normalization was artificially inflated by hundreds of regex symbols.
3. **Apples-to-Oranges Metric Conflation**: Token-budgeted context yield (`bcy_curve.pack_files` @ 8,000 BPE tokens) was conflated with character-budgeted chunk coverage (`sample_metrics["gold_coverage@8k"]` @ 8,000 characters $\approx$ 1,800 tokens).

---

## 2. Itemized Investigation of Disputed Historical Claims

### 2.1 Candidate F MRR: Stage 3.5 (0.2152 / 0.2078) vs. Stage 3.7/3.8 (0.1351)

1. **Source Reports & Claimed Figures**:
   - `research/stage3_5/STAGE3_5_DECISION_REPORT.md`: claimed **0.2152**.
   - `research/stage3_5/EXPERIMENT_REGISTRY.jsonl` (EXP-308): claimed **0.2152**.
   - `research/stage3_5/GRAPH_RETRIEVAL_RESULTS.csv` (Row 18): claimed **0.2078**.
2. **Generating Script & Function**:
   - `research/stage3_5/evaluate_graph_retrieval.py` (`run_graph_evaluation`, line 249: `m_cand_f = rank_and_eval(score_cand_f, gold, hard_neg)`).
   - `research/stage3_5/evaluate_context_packing.py` (`run_context_packing_evaluation` on a 3-repository subset).
3. **Git Revision & Configuration**:
   - Git Commit: `4f78cc3`.
   - Engine: `RepoNeedleEngine.from_documents` with `RepoGraph.extract_polyglot_symbols`.
   - Adjacency Linkage: Contained hardcoded ripgrep coupling (`search.rs`, `standard.rs`, and `"core" in my_crate and "printer" in o_crate`) in `reponeedle/core/graph.py` (line 425).
4. **Reproducibility Status**:
   - **NOT REPRODUCIBLE on full benchmark**. When evaluated end-to-end across all 345 positive ARB v2 samples without hardcoding, Candidate F achieves **0.1351**.
   - The figure `0.2152` was an extrapolated projection derived from evaluating Candidate F exclusively on high-performing modular repositories (`click`, `tokio`, `caddy`) where Candidate F's MRR reaches $0.21 - 0.28$.
5. **Demonstrated Cause of Discrepancy**:
   - In `evaluate_graph_retrieval.py`, Candidate F added bidirectional graph diffusion to base scores. However, on large monorepos (`etcd`, `caddy`, `ruff`), regex parsing created up to 36,508 noisy edges. On `etcd-io/etcd`, the true target `cache/cache.go` had its PageRank drop from $0.3021$ down to $0.0384$, knocking the target from rank 1 to rank 3 and causing MRR to collapse from $1.0000 \to 0.3333$.
6. **Authoritative Disposition**:
   - **MARKED INVALID / SUPERSEDED**. The figures `0.2152` and `0.2078` are invalidated. The authoritative ARB v2 MRR for Candidate F is **0.1351**.

---

### 2.2 Candidate C MRR: Stage 3.5 (0.2040) vs. Stage 3.7/3.8 (0.1399)

1. **Source Reports & Claimed Figures**:
   - `research/stage3_5/GRAPH_RETRIEVAL_RESULTS.csv` (Row 16): claimed **0.2040**.
   - `research/stage3_5/BASELINE_REPRODUCTION.md` (Table 1): claimed **0.2040**.
   - `research/stage3_4/FULL_CORPUS_RESULTS.csv` (Row 6): claimed **0.2040**.
2. **Generating Script & Function**:
   - `research/run_targeted_failure_verifications.py` (Priority 5A: `m_f05 = rank_and_eval(score_f05, gold, hard_neg)`).
   - In Stage 3.5, `evaluate_graph_retrieval.py` did not compute Candidate C dynamically; it copied the Stage 2 summary verbatim.
3. **Git Revision & Configuration**:
   - Original Source: Stage 2 commit `cd7f3b0` (`stage3-candidate-freeze`).
   - Configuration: Static Hybrid + 0.5x Documentation Filter, evaluated strictly on clean Python AST without polyglot regex symbols.
4. **Reproducibility Status**:
   - **REPRODUCIBLE UNDER CLEAN STAGE 2 CONFIGURATION** ($0.2040$), but **SUPERSEDED IN POLYGLOT ENGINE** ($0.1399$).
   - When running on clean Python AST without regex symbol extraction, Candidate C yields MRR $0.2040$ across ARB v2.
   - When running inside the polyglot engine where `FileDoc` holds extracted regex symbols, document length normalization and structural dilution reduce Candidate C MRR to **0.1399**.
5. **Demonstrated Cause of Discrepancy**:
   - The Stage 3.5 report merged two incompatible codebases: it claimed Candidate C had MRR $0.2040$ (from the clean Python AST codebase) while simultaneously running Candidate F in a polyglot environment where the base Candidate C ranking was already degraded to $0.1399$.
6. **Authoritative Disposition**:
   - **RESOLVED & SUPERSEDED**. Candidate C MRR $0.2040$ is retained as a valid historical measurement for the Stage 2 Python-only architecture, but **0.1399 is authoritative** for the unified polyglot engine.

---

### 2.3 BM25 MRR: Previously Reported (0.1705) vs. Stage 3.7/3.8 (0.1735)

1. **Source Reports & Claimed Figures**:
   - `research/stage3_5/GRAPH_RETRIEVAL_RESULTS.csv` (Row 14): claimed **0.1705**.
   - `research/STAGE2_ABLATION_RESULTS.csv` (EXP-016): claimed **0.1705**.
   - Stage 3.6 / Stage 3.7 / Stage 3.8: reproduced **0.1735**.
2. **Generating Script & Function**:
   - `research/stage3_6/evaluate_systems.py` (`lex_scores = engine.lexical_index.score(q_text)`).
3. **Git Revision & Configuration**:
   - Clean implementation of Okapi BM25 ($k_1=1.5, b=0.75$) evaluated on candidate chunk expansion.
4. **Reproducibility Status**:
   - **REPRODUCIBLE & VERIFIED**. Both figures are fully reproducible within numerical parity ($\Delta = +0.0030$).
5. **Demonstrated Cause of Discrepancy**:
   - Negligible tie-breaking order differences between the Stage 2 chunk-sorting script and the Stage 3.6/3.8 deduplication loop.
6. **Authoritative Disposition**:
   - **RECONCILED IN PARITY**. Point estimate **0.1735** is authoritative for canonical ARB v2 Okapi BM25.

---

### 2.4 Recall@5, Recall@10, and Recall@20 Differences

1. **Reported Figures**:
   - Stage 3.5 reported Candidate C Recall: R@5 = **0.2514**, R@10 = **0.3802**, R@20 = **0.5516**.
   - Stage 3.5 reported Candidate F Recall: R@5 = **0.2560** (or 0.2667), R@10 = **0.3855** (or 0.3942), R@20 = **0.5562** (or 0.5652).
   - Stage 3.7/3.8 canonical evaluation:
     - Candidate C: R@5 = **0.2111**, R@10 = **0.3196**, R@20 = **0.5105**.
     - Candidate F: R@5 = **0.1824**, R@10 = **0.3316**, R@20 = **0.5078**.
2. **Demonstrated Cause**:
   - In Stage 3.5, Recall values for Candidate C were transcribed directly from Stage 2 (`STAGE2_FAILURE_ANALYSIS.md`).
   - In live polyglot evaluation, noisy regex edges boosted non-gold structural hub files into ranks 1–20, displacing true gold targets.
   - For Candidate F, diffusion from top-5 seeds further pushed borderline lexical matches outside rank 20, causing Candidate F's Recall@20 ($0.5078$) to fall below Candidate C ($0.5105$).
3. **Authoritative Disposition**:
   - **SUPERSEDED**. Canonical live values (C: R@20 = 0.5105; F: R@20 = 0.5078) are authoritative.

---

### 2.5 Token-Budgeted BCY vs. Character-Budgeted Coverage

1. **Source Reports & Claimed Figures**:
   - Stage 3.5 reported BCY@8k: Candidate C = **0.3015**, Candidate F = **0.3060** (or **0.3184**).
   - Stage 3.6 reported BCY@8k: Candidate C = **0.0188**, Candidate F = **0.0159**, BM25 = **0.0159**, RepoMap = **0.0652**.
2. **Demonstrated Cause**:
   - Stage 3.5 invoked `agent_retrieval_bench.bcy_curve.pack_files`, which measures **Token-Budgeted Context Yield** at an 8,000 BPE token limit.
   - Stage 3.6 recorded `sample_metrics["gold_coverage@8k"]`, which is implemented in `baseline.py` as **Character-Budgeted Chunk Coverage** (`used += len(chunk_text)`) capped at 8,000 characters ($\approx$ 1,800 tokens).
3. **Authoritative Disposition**:
   - **RETAINED UNDER DISTINCT CONTRACTS**. Both measurements are physically valid but represent distinct quantities:
     - `char_cov_at_8k`: Candidate C = **0.0188**, Candidate F = **0.0159**, RepoMap = **0.0652**.
     - `token_bcy_at_8k`: Candidate C = **0.2034** (full file) / **0.3805** (skeleton), RepoMap = **0.3177** (full file) / **0.4357** (skeleton).
   - In all future work, merging these two distinct metrics under the label "BCY@8k" is prohibited.

---

### 2.6 RepoMap Reference: Frozen Paper Constant (0.2140) vs. Released Predictions (0.2293)

1. **Source Reports**:
   - Stage 3.5 used the scalar constant **0.2140** from the ARB v1.1 release paper table.
   - Stage 3.6/3.7 evaluated the per-sample predictions released in `repomap_code_only_details.jsonl` and `v2_edit2ripple/repomap_details.jsonl`.
2. **Demonstrated Cause**:
   - The paper constant ($0.2140$) reflected an earlier benchmark snapshot. The released per-sample RepoMap predictions achieve mean MRR **0.2293**, Recall@5 **0.3337**, Recall@20 **0.6599**, and Token BCY **0.3177**.
3. **Authoritative Disposition**:
   - **SUPERSEDED**. The released per-sample RepoMap results (**MRR 0.2293, Recall@20 0.6599**) are authoritative. RepoMap significantly outperforms all tested RepoNeedle configurations on ARB v2.

---

### 2.7 Latency and Memory Measurement Divergence

1. **Discrepancy Breakdown**:
   - Latency: Stage 3.5 reported **9.85 ms** (or **6.36 ms** on `pallets/click`), while Stage 3.6/3.7 reported mean latency **132.30 ms**, median ($p50$) **31.50 ms**, and 95th percentile ($p95$) **561.46 ms**.
   - Memory: Stage 3.5 reported **+12.4 MB**, while Stage 3.6/3.7 reported peak Resident Set Size (RSS) **238.4 MB**.
2. **Demonstrated Cause**:
   - **Latency**: Subword n-gram scoring (`SubwordSemanticIndex`) is $O(N_{\text{docs}} \times L_{\text{query}} \times K_{\text{ngrams}})$. On `pallets/click` ($133$ files), scoring takes $6.36\text{ ms}$. On `spring-projects/spring-boot` ($11,172$ files), scoring takes $560+\text{ ms}$. Reporting Click's micro-latency as full-benchmark latency was misleading.
   - **Memory**: Stage 3.5 measured incremental Python heap object allocations (`tracemalloc`). Stage 3.6 measured actual Windows OS Resident Set Size (RSS via PSAPI `K32GetProcessMemoryInfo`), which captures interpreter and shared C-library memory.
3. **Authoritative Disposition**:
   - **RECONCILED & STANDARDIZED**. Full-corpus latency distribution: Median ($p50$) **31.50 ms**, Mean **132.30 ms**, $p95$ **561.46 ms**. Peak operational RSS is **238.4 MB**.

