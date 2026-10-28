# Forensic Evaluation Reconciliation & Research Audit

**Document ID**: `STAGE3-7-RECON-001`  
**Stage**: Stage 3.7 — Forensic Evaluation Reconciliation and Research Integrity Audit  
**Date**: October 28, 2026  
**Status**: Authoritative Forensic Resolution  
**Baseline & Freeze References**:  
- `v0.1.0-baseline`: `8e00425` (Immutable Git Tag)  
- `stage3-candidate-freeze`: `cd7f3b0` (Immutable Git Tag)  
- Stage 3.5 Commit: `4f78cc3`  
- Stage 3.6 Clean HEAD: `cbe6c49`  

---

## 1. Executive Summary & Root Cause Overview

Stage 3.6 exposed significant numerical discrepancies when compared against Stage 3.5 reports across all headline metrics (MRR, Recall@k, BCY@8k, Latency, and Memory). This audit conducted a forensic code inspection, historical Git trajectory analysis, and isolated counter-factual experiments across the 345 positive ARB v2 benchmark samples.

The discrepancies do **NOT** stem from random evaluation nondeterminism. They stem from five distinct, verifiable root causes:
1. **Transcribed Historical Baselines vs. Live End-to-End Evaluation**: In Stage 3.5, the reported Candidate C numbers (MRR $0.2040$) were copied verbatim from an isolated Stage 2 micro-ablation (`STAGE2_FAILURE_ANALYSIS.md`), rather than re-computed dynamically alongside Candidate F.
2. **Structural Edge Dilution & Length Penalty Inflation**: Introducing regex-based polyglot symbol extraction in Stage 3.5/3.6 exploded graph edges from 1,802 to 36,508 in large repositories like `etcd-io/etcd`. PageRank diffused away from true targets onto generic hub files (`backend.go`, `types.go`), and BM25 document length penalties were artificially inflated by hundreds of regex symbols, driving true end-to-end Candidate C MRR down to **$0.1399$** and Candidate F to **$0.1351$**.
3. **Apples-to-Oranges Metric Conflation (Token BCY vs. Character Coverage)**: Stage 3.5 reported Token-Budgeted Context Yield (`pack_files` @ 8,000 BPE tokens = $0.3015$), whereas Stage 3.6 recorded Character-Budgeted Chunk Coverage (`sample_metrics["gold_coverage@8k"]` @ 8,000 characters $\approx$ 1,800 tokens = $0.0188$).
4. **RepoMap Reference Update**: Stage 3.5 used the legacy frozen paper constant ($0.2140$), whereas Stage 3.6 evaluated the released authoritative per-sample RepoMap predictions ($0.2293$).
5. **Statistical Aggregation Shift**: The Wilcoxon query-level test ($p=0.0023$) was driven by large localized wins in 3 repositories (`click`, `tokio`), whereas repository-clustered bootstrap resampling ($95\%$ CI $[-0.0091, +0.1689]$) accurately captured between-repository variance across the 25 clusters.

---

## 2. Comprehensive Metric Reconciliation Table

The following master reconciliation table maps every reported metric across Stage 3.5 and Stage 3.6, detailing the mathematical and computational root cause:

| Metric / Dimension | Stage 3.5 Reported | Stage 3.6 Reproduced | Evaluation Contract | Script / Version | Forensic Root Cause & Mathematical Explanation | Final Disposition |
| :--- | :---: | :---: | :--- | :--- | :--- | :--- |
| **CAND-C MRR** | **0.2040** | **0.1399** | Full ARB v2 ($N=345$) | S3.5: `evaluate_graph_retrieval.py`<br>S3.6: `evaluate_systems.py` | S3.5 transcribed Stage 2 isolated doc-penalty result (`STAGE2_FAILURE_ANALYSIS.md` line 23). In S3.6, adding polyglot symbol parsing created edge bloat in `FileDoc` and inflated BM25 length denominators. | **0.1399 is authoritative** for current codebase; $0.2040$ reflected clean Python-only Stage 2 baseline. |
| **CAND-F MRR** | **0.2078** / **0.2152** | **0.1351** | Full ARB v2 ($N=345$) | S3.5: `evaluate_graph_retrieval.py`<br>S3.6: `evaluate_systems.py` | S3.5 reported MRR $0.2078$ in CSV and $0.2152$ in Decision Report by applying graph diffusion on top of the uncorrupted Stage 2 scores. Under unified end-to-end parsing, noisy graph edges cause PageRank dilution, reducing MRR to $0.1351$. | **0.1351 is authoritative** for Candidate F. No general retrieval advantage over BM25 ($0.1735$). |
| **BASE-BM25 MRR** | **0.1705** | **0.1735** | Full ARB v2 ($N=345$) | S3.5: Stage 2 lookup (`EXP-016`)<br>S3.6: Live evaluation | S3.5 took historical lookup from `PER_SAMPLE_ABLATIONS.jsonl` ($0.1705$). S3.6 evaluated pure Okapi BM25 dynamically ($0.1735$, $\Delta = +0.0030$). | **Reconciled / Parity**. Difference is negligible ($< 0.003$) due to tie-breaking order. |
| **BASE-REPOMAP MRR** | **0.2140** | **0.2293** | Full ARB v2 ($N=345$) | S3.5: Paper constant<br>S3.6: Authoritative JSONL details | S3.5 used frozen paper constant from ARB v1.1 table ($0.2140$). S3.6 loaded per-sample records from `repomap_code_only_details.jsonl` ($0.2293$). | **0.2293 is authoritative**. RepoMap strongly outperforms all RepoNeedle variants on ARB v2. |
| **CAND-C Recall@5** | **0.2514** | **0.2111** | Full ARB v2 ($N=345$) | Pinned `sample_metrics` | Transcribed Stage 2 value vs. live end-to-end evaluation under polyglot document length normalization. | **0.2111 is authoritative**. |
| **CAND-C Recall@10** | **0.3802** | **0.3196** | Full ARB v2 ($N=345$) | Pinned `sample_metrics` | Same as above. | **0.3196 is authoritative**. |
| **CAND-C Recall@20** | **0.5516** | **0.5105** | Full ARB v2 ($N=345$) | Pinned `sample_metrics` | Same as above. | **0.5105 is authoritative**. |
| **CAND-F Recall@20** | **0.5562** | **0.5078** | Full ARB v2 ($N=345$) | Pinned `sample_metrics` | Graph diffusion adds low-confidence structural neighbors that displace borderline lexical matches outside rank 20. | **0.5078 is authoritative**. |
| **BCY@8k (Cand C)** | **0.3015** | **0.0188** | 8k Context Limit | S3.5: `pack_files` (tokens)<br>S3.6: `gold_coverage@8k` (chars) | **Apples-to-oranges metric collision**: S3.5 measured Token-Budgeted Context Yield (8,000 BPE tokens). S3.6 recorded Character-Budgeted Chunk Coverage (8,000 characters $\approx$ 1,800 tokens). | **Both values are mathematically valid within their respective contracts**. See Section 3 for strict separation. |
| **Token BCY@8k (Cand C)**| **0.3015** | **0.3805** | Token budget (8k tokens) | `audit_context_packing.py` | S3.5 used Stage 2 full-file packing. S3.6 audited packing with skeleton compression, yielding higher token efficiency ($0.3805$). | **0.3805 is authoritative** for Candidate C Token BCY. |
| **Query Latency (Mean)** | **9.85 ms** | **132.30 ms** | ARB v2 Benchmark | Click subset vs Full corpus | S3.5 reported latency on small repositories (Click = 6.36 ms). Full ARB includes Spring-Boot (11,172 files) where subword n-grams take 500+ ms. | **Median ($p50$) 31.50 ms / Mean 132.30 ms / $p95$ 561.46 ms** is authoritative. |
| **Runtime Memory** | **+12.4 MB** | **238.4 MB** | Memory Footprint | Python Heap vs OS Process RSS | S3.5 measured incremental Python heap objects (`tracemalloc`). S3.6 measured actual Windows OS Resident Set Size (`WorkingSetSize`). | **Both valid**: +12.4 MB heap delta; ~240 MB total process RSS. |

---

## 3. Deep-Dive Forensic Discrepancy Analysis

### 3.1 Forensic Analysis of MRR Degradation: 0.2040 to 0.1399

To isolate why Candidate C produced MRR $0.2040$ in Stage 2 / Stage 3.4 and $0.1399$ in Stage 3.6, we executed counter-factual ablation runs across matched query subsets:

```
[Diagnostic Probe: etcd-io/etcd Snapshot c64f8fd]
Sample: 0265037c6c534b98289fe815
Gold targets: ['cache/cache.go', 'cache/demux.go', 'tests/integration/cache_test.go']

Condition 1: Clean Stage 2 Engine (Python AST only, No Polyglot Regex Extraction)
  - Graph edges: 1,802
  - Target cache/cache.go: lex=0.8630, sem=0.2383, struct=0.3021 -> Total=0.4678 (RANK 1)
  - Sample MRR: 1.0000

Condition 2: Stage 3.6 Unified Engine (Polyglot Regex Symbol & Import Extraction)
  - Graph edges: 36,508 (20.2x edge explosion!)
  - Target cache/cache.go: lex=0.7480, sem=0.2378, struct=0.0384 -> Total=0.3414 (RANK 3)
  - Top retrieved file: server/storage/backend/backend.go (central structural hub)
  - Sample MRR: 0.3333 (regressed by -66.7%)
```

#### The Mathematical Mechanism:
1. **Structural Score Mass Dilution**: In a sparse graph (1,802 edges), PageRank concentrates score mass on modular subsystem entry points. In an over-connected graph (36,508 edges), high-indegree utility hubs (`backend.go`, `types.go`, `mod.rs`) absorb virtually all PageRank mass. True targets drop from PageRank $0.3021 \to 0.0384$.
2. **BM25 Document Length Penalty Inflation**: Okapi BM25 length normalization is defined as:
   $$\text{norm}(d) = 1.0 - b + b \cdot \frac{\text{len}(d)}{\text{avg\_len}}$$
   In RepoNeedle, `doc_length = len(symbols) * 3 + len(content_tokens)`. Adding 500 noisy regex symbols to `FileDoc` doubled the effective document length of Go and Rust files, heavily penalizing lexical term matches on true targets ($0.8630 \to 0.7480$).

### 3.2 Forensic Analysis of BCY@8k: 0.3015 vs 0.0188

The apparent collapse from $30.15\%$ to $1.88\%$ was purely an artifact of unit and interface conflation:
- **`gold_coverage@8k` in `sample_metrics`**: Budget is defined in **characters** (`len(chunk_text)`). An 8,000 character budget accommodates only $\approx 1,800$ tokens. In multi-file repositories where chunks are 3,000–4,500 characters, the budget breaks after 2 chunks. Because chunks of gold files rarely appear within the first 2 chunks of a 1,400-file repository, character coverage is naturally bounded between $0.015$ and $0.065$.
- **`pack_files` in `bcy_curve`**: Budget is defined in **tokens** (8,000 BPE tokens). Full files are packed greedily until 8,000 tokens are exhausted. When skeleton compression is enabled, Candidate C packs $0.3805$ of all gold content tokens.
- **Resolution**: Both metrics are retained, but strictly renamed in the registry to `char_cov_at_8k` ($0.0188$) and `token_bcy_at_8k` ($0.3805$).

### 3.3 Forensic Analysis of RepoMap: 0.2140 vs 0.2293

In Stage 3.5, RepoMap was treated as a single scalar baseline ($0.2140$) copied from the initial ARB v1.1 release paper. In Stage 3.6, RepoMap was evaluated per-query from the authoritative released evaluation details (`repomap_code_only_details.jsonl` and `v2_edit2ripple/repomap_details.jsonl`):
- Across all 345 samples, actual mean RepoMap MRR is **$0.2293$**.
- RepoMap achieves Recall@5 = **$0.3337$**, Recall@10 = **$0.5110$**, Recall@20 = **$0.6599$**, and Token BCY@8k = **$0.4357$**.
- This proves that RepoMap outperforms all tested RepoNeedle configurations by $+64\%$ on MRR ($0.2293$ vs $0.1399$) and $+29\%$ on Recall@20 ($0.6599$ vs $0.5105$).
- Claims that RepoNeedle matched or beat RepoMap in Stage 3.5 were invalid artifacts of comparing against an outdated paper constant and evaluating an isolated subset.

---

## 4. Final Discrepancy Resolutions

1. **Candidate C Baseline**: Locked at **MRR $0.1399$**, **Recall@20 $0.5105$**, **Token BCY@8k $0.3805$**.
2. **Candidate F Intervention**: Locked at **MRR $0.1351$**, **Recall@20 $0.5078$**, **Token BCY@8k $0.4180$**.
3. **Pure BM25 Baseline**: Locked at **MRR $0.1735$**, **Recall@20 $0.4549$**, **Token BCY@8k $0.2688$**.
4. **Authoritative RepoMap Reference**: Locked at **MRR $0.2293$**, **Recall@20 $0.6599$**, **Token BCY@8k $0.4357$**.
5. **Stage 3.5 Claims**: Formally corrected. Candidate F does NOT beat RepoMap or BM25 on overall ARB v2 retrieval quality.
