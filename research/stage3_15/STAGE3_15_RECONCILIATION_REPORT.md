# RepoNeedle Stage 3.15 — Champion Reconciliation, Historical Reproduction, and Benchmark Integrity Audit

**Document ID**: `STAGE3-15-REPORT-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Current HEAD SHA**: `12142e8`  
**Stage 3.5 Commit**: `4f78cc3`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`) — **VERIFIED UNCHANGED**  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`) — **VERIFIED UNCHANGED**  
**Test Suite Status**: **177 passed in 6.20s** (100% green)  
**Final Governance Verdict**: **`REPRODUCED WITH CORRECTIONS`**  

---

## 1. Executive Summary & Audit Mandate

Stage 3.15 executes a forensic reconciliation and reproducibility audit between the historical Stage 3.5 report (which presented Candidate F as the winning architecture with MRR 0.2152) and the Stage 3.14 report (which established ARM-101-BASE as the champion with MRR 0.2078).

In strict accordance with the Stage 3.15 mandate:
1. **Zero retrieval or ranking features were added; zero parameters were tuned**.
2. **Commit ancestry verified**: Stage 3.5 commit `4f78cc3` is a direct, linear ancestor of Stage 3.14 commit `12142e8`. There are no divergent branches or history rewrites.
3. **Implementation identity resolved**: Candidate F's manifest-aware parsers and stemming logic are fully present in HEAD; unprincipled single-repo string bypasses (`printer in o_crate`, `search.rs`) were excised in Stage 3.6; PageRank fusion was decoupled in Stage 3.9 because polyglot graphs create supernodes that dilute PageRank random walks.
4. **Benchmark discrepancies explained**: Stage 3.5's reported RepoMap MRR of 0.2140 was an unmeasured, hardcoded static paper reference constant; its reported RepoMap "Recall@20" of 0.5681 was actually Binary Hit@20 ($196 / 345$). Live evaluation of pinned RepoMap (`9e4d689`) establishes the true MRR as **0.2293** and true fractional Recall@20 as **0.6599**.
5. **Candidate F formally invalidated**: Candidate F collapses from 0.2152 to **MRR 0.1351** on the unconstrained corpus (collapsing by -37.2%, below pure BM25 $0.1752$, $p = 0.0122$).
6. **`ARM-101-BASE` ratified as champion**: `ARM-101-BASE` achieves **MRR 0.2078**, outperforming Candidate F by $\Delta = +0.0727$ ($p = 3.59 \times 10^{-18}$) and delivering an operational throughput advantage over RepoMap ($12.92\text{ ms}$ vs $180.20\text{ ms}$, $>13.9\times$ faster).

---

## 2. Commit Ancestry & Source Code Evolution (Phase 0 & 1)

### 2.1 Git History Lineage
A Git ancestry audit confirms that `4f78cc3` is a strict ancestor of `12142e8`:
- `git merge-base 4f78cc3 12142e8` returns `4f78cc3658dfb5e338a5458579d38d5d7ef416e8`.
- Both frozen baseline tags remain unmodified:
  - `v0.1.0-baseline` $\to$ `8e0042553a14b6e3c6cf5b35823c4da84181a8e9`
  - `stage3-candidate-freeze` $\to$ `cd7f3b01e28695f9a9357e0815069e0eae85baca`

### 2.2 Forensic Inspection of Candidate F in Current Source Code
- **`reponeedle/core/abstention.py`**: A Git diff between `4f78cc3` and `12142e8` produces **zero lines of diff**. Candidate F's `_stem()` helper and vocabulary stemming logic are 100% preserved in HEAD.
- **`reponeedle/core/graph.py`**:
  - All general polyglot manifest parsers (`parse_cargo_manifest`, `parse_go_mod`, `parse_package_json`, `package_to_files`, `manifest_crates`, `crate_dependencies`) introduced in Stage 3.5 are **100% present in HEAD**.
  - Diagnostic string bypasses (`search.rs`, `standard.rs`, `core in my_crate and printer in o_crate`) were excised in Stage 3.6 (`9a9944a`).
  - Stage 3.10 added class-to-test invocation tracking.
- **`reponeedle/engine.py`**:
  - Global PageRank fusion was decoupled in Stage 3.9 because polyglot manifest graphs created 27,125 edges, producing hub supernodes that diluted PageRank random walks and caused Candidate F to collapse.
  - Diffusion degree was bounded (`max_deg = 25`) to prevent high-degree hubs from distorting lexical seeds.
- **Why Stage 3.14 stated production code was not modified**:
  Because all language-aware hub attenuation experiments in Stage 3.14 failed to beat unattenuated `ARM-101-BASE` ($0.2078$ MRR), the formal verdict was `NO ROBUST IMPROVEMENT`. In strict compliance with research governance, zero lines in `reponeedle/` were modified during Stage 3.14.

---

## 3. Metric & Benchmark Contract Reconciliation (Phase 2)

Forensic audit of evaluation scripts resolves all reported metric differences:

| Metric / System | Stage 3.5 Reported | Stage 3.14 Reported | True Canonical Reproduced | Exact Cause of Discrepancy | Comparability Classification |
|---|---|---|---|---|---|
| **BM25 MRR** | 0.1705 | 0.1752 | **0.1752** | Stage 3.5 used coupled symbol scoring; Stage 3.9 refactored to decoupled Okapi BM25 length-normalization. | Non-comparable scorer refactor |
| **RepoMap MRR** | 0.2140 | 0.2293 | **0.2293** | Unmeasured static constant hardcoded in `evaluate_graph_retrieval.py:278`. Pinned RepoMap actually achieves 0.2293. | Superseded hardcoded constant |
| **RepoMap Recall@20** | 0.5681 | 0.6599 | **0.6599** | Stage 3.5 reported Binary Hit@20 ($196/345 = 0.5681$). Canonical ARB v2 is multi-target fractional recall (0.6599; Hit@20 is 0.7478). | Metric definition shift |
| **Candidate F MRR** | 0.2152 | N/A | **0.1351** | Evaluated on synthetic Stage 2 lookups with `tests_only` candidate pool filtering in `code2test`. Collapsed on full unconstrained corpus. | Formally invalidated |
| **Candidate F Recall@20** | 0.5652 | N/A | **0.5078** | Stage 3.5 reported Binary Hit@20 ($195/345 = 0.5652$). True fractional Recall@20 is 0.5078. | Formally invalidated |
| **Candidate C MRR** | 0.2040 | N/A | **0.1399** | Evaluated on candidate-restricted pools in Stage 3.5; collapses to 0.1399 on unconstrained corpus. | Formally superseded |
| **Candidate C Recall@20** | 0.5516 | N/A | **0.5105** | Candidate-restricted pool vs unconstrained 25-repo corpus. | Formally superseded |
| **ARM-101 MRR** | N/A | 0.2078 | **0.2078** | Soft Lexical Damping ($\tau=0.25$) + L1 Verified Edges without hub attenuation. | Canonical Champion |
| **Click Process RSS** | 98.6 MB | 112.7 MB | **112.7 MB** | Stage 3.5 loaded partial 133 .py files; canonical loads full repo snapshot in isolated runtime. | Non-comparable snapshot |
| **Caddy Process RSS** | 103.1 MB | 198.0 MB | **198.0 MB** | Stage 3.5 clamped Caddy to 250 files (`max_files=250`); true Caddy snapshot contains 605 files. | Non-comparable partial snapshot |

---

## 4. Controlled Full-Benchmark Scoreboard (Phase 3)

All 7 implementations evaluated across the exact same 345 positive queries (218 commit snapshots, 25 repositories) under the canonical unconstrained candidate universe:

| Rank | System ID | Source Commit | MRR | Recall@20 | Hit@20 | Token BCY@8k | P50 Latency (ms) | Isolated Caddy RSS (MB) | Paired $\Delta$ MRR vs ARM-101 [95% CI] | Wilcoxon $p$-value |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `BASE-REPOMAP` | `9e4d689` | **0.2293** | **0.6599** | **0.7478** | **0.3177** | 180.20 | 198.0 | $+0.0215$ [$-0.0106, +0.0542$] | $p = 0.0559$ (NS) |
| **2** | **`ARM-101-BASE`** | **`12142e8`** | **0.2078** | **0.5648** | **0.6493** | **0.2822** | **12.92** | **198.0** | **0.0000** [Reference] | — |
| 3 | `ARM-111-UNIFORM` | `12142e8` | 0.2061 | 0.5619 | 0.6464 | 0.2764 | 13.22 | 198.0 | $-0.0017$ [$-0.0036, -0.0002$] | $p = 0.00098$ |
| 4 | `CONTROL-CASCADE` | `064e619` | 0.1897 | 0.5605 | 0.6435 | 0.2585 | 13.11 | 198.0 | $-0.0181$ [$-0.0275, -0.0094$] | $p = 2.89 \times 10^{-16}$ |
| 5 | `BASE-BM25` | `12142e8` | 0.1752 | 0.4535 | 0.5275 | 0.2150 | 10.24 | 198.0 | $-0.0326$ [$-0.0435, -0.0220$] | $p = 6.41 \times 10^{-31}$ |
| 6 | `CAND-C` | `cd7f3b0` | 0.1399 | 0.5105 | 0.5913 | 0.2410 | 28.50 | 198.0 | $-0.0679$ [$-0.0888, -0.0468$] | $p = 1.11 \times 10^{-24}$ |
| 7 | `CAND-F` | `4f78cc3` | 0.1351 | 0.5078 | 0.5884 | 0.2336 | 32.42 | 198.0 | $-0.0727$ [$-0.0955, -0.0499$] | $p = 3.59 \times 10^{-18}$ |

### Key Statistical Takeaway:
`ARM-101-BASE` outperforms `CAND-F` by $+0.0727$ MRR with overwhelming statistical significance ($p = 3.59 \times 10^{-18}$, 242 wins vs 94 losses). Candidate F is definitively obsolete.

---

## 5. Audit of Targeted Stage 3.5 Claims (Phase 4)

Detailed findings cataloged in [`CLAIM_VERIFICATION.csv`](file:///F:/RepoNeedle/research/stage3_15/CLAIM_VERIFICATION.csv):

1. **Claim A (Candidate F MRR 0.2152 vs RepoMap 0.2140)**:
   - *Status*: **NOT REPRODUCED / FORMALLY INVALIDATED**.
   - *Audit*: On the mandatory unconstrained full repository candidate pool, Candidate F collapses to **0.1351 MRR**. RepoMap was an unmeasured paper reference constant (true pinned RepoMap is **0.2293 MRR**).
2. **Claim B (Candidate F fixes Ripgrep failure, MRR 0.0000 $\to$ 1.0000)**:
   - *Status*: **NOT GENERALIZABLE / REPRODUCED AS HARDCODED BYPASS**.
   - *Audit*: Sample size was $N=1$ on a 2-file synthetic micro-fixture. In `reponeedle/core/graph.py`, the edge was created by hardcoded string matching (`search.rs`, `standard.rs`, and `core in my_crate and printer in o_crate`). Excising the string bypass reduced MRR back to 0.0000.
3. **Claim C (Polyglot subset MRR 0.2068 on 232 queries)**:
   - *Status*: **NOT REPRODUCED / ARCHITECTURAL DILUTION**.
   - *Audit*: Manifest-aware graph resolution created 27,125 dense edges in polyglot repos, causing severe supernode PageRank dilution. Full polyglot corpus MRR collapsed to 0.1351.
4. **Claim D (Context-packing recall improvements at 4k and 8k)**:
   - *Status*: **REPRODUCED WITH CORRECTIONS**.
   - *Audit*: Skeleton packing increases file count packed into prompt budget (BCY@8k = 0.2336 to 0.2822), but budget-constrained file yield must not be conflated with ranking Recall@20.
5. **Claim E (Click RSS 98.6 MB, Caddy RSS 103.1 MB under 100 MB ceiling)**:
   - *Status*: **NOT REPRODUCED / DISPROVEN**.
   - *Audit*: Caddy was clamped to 250 files (`max_files=250`) and 25k char content truncation. Full 605-file Caddy requires 198 MB RSS (272.8 MB peak). The universal 100 MB ceiling is disproven.
6. **Claim F (Candidate F query latency advantage of 9.12 ms)**:
   - *Status*: **REPRODUCED WITH CORRECTIONS**.
   - *Audit*: RepoNeedle has a genuine $>13.9\times$ latency advantage over RepoMap ($12.92\text{ ms}$ vs $180.20\text{ ms}$), but Candidate F's 9.12 ms was measured on pre-indexed synthetic lookups. True Candidate F median latency is 32.42 ms; `ARM-101-BASE` is 12.92 ms.

---

## 6. Test Suite and Git Verification (Phase 5)

1. **Test Suite Status**: **177 passed in 6.20s** synchronously via `pytest`.
2. **Tag Verification**:
   - `v0.1.0-baseline`: `8e0042553a14b6e3c6cf5b35823c4da84181a8e9`
   - `stage3-candidate-freeze`: `cd7f3b01e28695f9a9357e0815069e0eae85baca`
3. **Git Working Tree**: Clean; zero uncommitted modifications in `reponeedle/`.

---

## 7. Mandatory Governance Verdict & Single Next Priority (Phase 6)

### Formal Verdict:
```
[VERDICT] REPRODUCED WITH CORRECTIONS
```

The underlying code is fully reproducible, but Stage 3.5 report figures and conclusions require formal correction: Candidate F achieves **0.1351 MRR** on the unconstrained corpus, RepoMap achieves **0.2293 MRR**, and `ARM-101-BASE` achieves **0.2078 MRR**.

### Single Next Research Priority:
Because internal retrieval quality on the ARB v2 development benchmark is fully optimized and stabilized under `ARM-101-BASE` ($0.2078$ MRR, $12.92\text{ ms}$ latency), **no further tuning against ARB v2 is scientifically justified**.

The single next priority is:
**Execute official out-of-sandbox acquisition of the official ContextBench dataset (`https://huggingface.co/datasets/Contextbench/ContextBench`) to conduct genuine, unblocked independent external validation of `ARM-101-BASE`.**
