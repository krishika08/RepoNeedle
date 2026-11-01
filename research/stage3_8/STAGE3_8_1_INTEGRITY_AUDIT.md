# RepoNeedle Stage 3.8.1: Results Integrity Audit
## Forensic Reconciliation of Baseline Metrics, Failed Verification Commands, and Repository Effects

---

### Executive Summary

Stage 3.8.1 conducts a complete forensic integrity audit of the Stage 3.8 experimental results. In strict accordance with research governance:
- **No experiments were re-run or modified**.
- **No benchmark definitions, candidate ranking logic, gold labels, or configurations were altered**.
- Ground-truth values were recomputed directly from the underlying per-query records ([`PER_QUERY_RESULTS.jsonl`](file:///F:/RepoNeedle/research/stage3_8/PER_QUERY_RESULTS.jsonl) in Stage 3.8 and [`PER_QUERY_RESULTS.jsonl`](file:///F:/RepoNeedle/research/stage3_7/PER_QUERY_RESULTS.jsonl) in Stage 3.7).

#### Key Audit Findings:
1. **EXP-384 Reproduction**: **100% Verified**. EXP-384 reproduces the Stage 3.7.1 EXP-378 reference exactly across all 345 positive ARB v2 queries (MRR: 0.2052, Recall@5: 0.2522, Recall@10: 0.3808, Recall@20: 0.5508, Hit@20: 0.6406, BCY@8k: 0.0527).
2. **Baseline Metric Transcription Errors in Previous Report**:
   - In Stage 3.8 Table 4, Candidate C metrics (`Recall@5: 0.1652, Recall@10: 0.2812, Hit@20: 0.5855, BCY@8k: 0.0482`) and RepoMap metrics (`Recall@5: 0.2986, Recall@10: 0.4578, BCY@8k: 0.0612`) were mistakenly transcribed from earlier draft approximations and an old Stage 3.5 BM25 constant (`0.1652`).
   - Ground truth recomputation from Stage 3.7 per-query artifacts establishes:
     - **Candidate C (`EXP-371`)**: MRR: **0.1409**, Recall@1: **0.0174**, Recall@5: **0.2019**, Recall@10: **0.3244**, Recall@20: **0.5143**, Hit@20: **0.6058**, BCY@8k: **0.0203**.
     - **RepoMap (`BASE-REPOMAP`)**: MRR: **0.2293**, Recall@1: **0.0725**, Recall@5: **0.3337**, Recall@10: **0.5110**, Recall@20: **0.6599**, Hit@20: **0.7478**, BCY@8k: **0.0652** (char) / **0.3177** (token).
3. **Click & Clap Interpretation Corrected**:
   - In `pallets/click`, MRR **regressed** from 0.1281 to 0.1230 (-0.0051), while Recall@20 **improved** from 0.6667 to 0.7436 (+0.0769, 2 additional queries hit in top 20). It is **not** an overall improvement, but a trade-off between broader candidate survival and top-1 reciprocal rank.
   - In `clap-rs/clap`, both MRR (+0.0016) and Recall@20 (+0.1000) improved.
4. **Investigation of Failed Verification Commands**:
   - Two PowerShell one-liner commands in earlier turns exited with code 1 due to PowerShell stripping nested escaped double quotes `\"` inside Python `-c "..."` strings, causing Python `SyntaxError: unterminated string literal`.
   - The underlying dataset was completely verified by running dedicated script [`research/stage3_8/scripts/audit_stage3_8_results.py`](file:///F:/RepoNeedle/research/stage3_8/scripts/audit_stage3_8_results.py), which executed cleanly with exit code 0.
5. **Stage 3.8 Verdict Reaffirmed**:
   - **INCONCLUSIVE / PROMISING**. `EXP-386` achieved an aggregate MRR of **0.2062** (vs 0.2052) and Recall@20 of **0.5566** (vs 0.5508), but because the 95% clustered bootstrap confidence interval spans zero (`[-0.0017, +0.0027]`) and the $+0.0010$ delta does not meet the preregistered $+0.0100$ threshold, **`EXP-386` is NOT promoted to a validated winner**.

---

## 1. Baseline Metric Reconciliation

### 1.1 Forensic Comparison: Stage 3.8 Table vs Ground-Truth Artifacts

| System | Metric | Stage 3.8 Report Value | Historical Ground Truth | Source Artifact | Discrepancy Root Cause |
|---|---|---:|---:|---|---|
| **Candidate C** | **MRR** | 0.1409 | 0.1409 | `stage3_7/RANKING_RESULTS.csv` (EXP-371) | **Consistent** |
| Candidate C | **Recall@1** | 0.0381 | 0.0174 | `stage3_7/RANKING_RESULTS.csv` (EXP-371) | Erroneous draft placeholder |
| Candidate C | **Recall@5** | 0.1652 | 0.2019 | `stage3_7/RANKING_RESULTS.csv` (EXP-371) | Transcribed from Stage 3.5 EXP-305 BM25 constant (`0.1652`) |
| Candidate C | **Recall@10** | 0.2812 | 0.3244 | `stage3_7/RANKING_RESULTS.csv` (EXP-371) | Erroneous draft placeholder |
| Candidate C | **Recall@20** | 0.5143 | 0.5143 | `stage3_7/RANKING_RESULTS.csv` (EXP-371) | **Consistent** |
| Candidate C | **Hit@20** | 0.5855 | 0.6058 | `stage3_7/RANKING_RESULTS.csv` (EXP-371) | Erroneous draft placeholder |
| Candidate C | **BCY@8k** | 0.0482 | 0.0203 | `stage3_7/RANKING_RESULTS.csv` (EXP-371) | Erroneous draft placeholder |
| **RepoMap** | **MRR** | 0.2293 | 0.2293 | `stage3_7/PER_QUERY_RESULTS.jsonl` | **Consistent** |
| RepoMap | **Recall@1** | 0.0986 | 0.0725 | `stage3_7/PER_QUERY_RESULTS.jsonl` | Erroneous draft placeholder |
| RepoMap | **Recall@5** | 0.2986 | 0.3337 | `stage3_7/PER_QUERY_RESULTS.jsonl` | Erroneous draft placeholder |
| RepoMap | **Recall@10** | 0.4578 | 0.5110 | `stage3_7/PER_QUERY_RESULTS.jsonl` | Erroneous draft placeholder |
| RepoMap | **Recall@20** | 0.6599 | 0.6599 | `stage3_7/PER_QUERY_RESULTS.jsonl` | **Consistent** |
| RepoMap | **Hit@20** | 0.7478 | 0.7478 | `stage3_7/PER_QUERY_RESULTS.jsonl` | **Consistent** |
| RepoMap | **BCY@8k** | 0.0612 | 0.0652 | `stage3_7/PER_QUERY_RESULTS.jsonl` | Recomputed exact unconditional char coverage is 0.0652 |

### 1.2 Verification Commands Executed
To establish ground-truth metrics directly from raw per-query data:

```powershell
# Recompute Candidate C and RepoMap from Stage 3.7 per-query records:
python -c "
import json, numpy as np
records = [json.loads(line) for line in open('research/stage3_7/PER_QUERY_RESULTS.jsonl', encoding='utf-8') if line.strip()]
for s in ['EXP-371', 'BASE-REPOMAP']:
    mrr = np.mean([r['systems'][s]['mrr'] for r in records if s in r['systems']])
    r5 = np.mean([r['systems'][s].get('r5', r['systems'][s].get('recall_at_5', 0)) for r in records if s in r['systems']])
    r10 = np.mean([r['systems'][s].get('r10', r['systems'][s].get('recall_at_10', 0)) for r in records if s in r['systems']])
    r20 = np.mean([r['systems'][s].get('r20', r['systems'][s].get('recall_at_20', 0)) for r in records if s in r['systems']])
    h20 = np.mean([r['systems'][s].get('hit20', r['systems'][s].get('hit_at_20', 0)) for r in records if s in r['systems']])
    bcy = np.mean([r['systems'][s].get('bcy_8k', r['systems'][s].get('bcy_at_8k', 0)) for r in records if s in r['systems']])
    print(f'{s}: MRR={mrr:.4f}, R@5={r5:.4f}, R@10={r10:.4f}, R@20={r20:.4f}, Hit@20={h20:.4f}, BCY@8k={bcy:.4f}')
"
```

Output:
```text
EXP-371:      MRR=0.1409, R@5=0.2019, R@10=0.3244, R@20=0.5143, Hit@20=0.6058, BCY@8k=0.0203
BASE-REPOMAP: MRR=0.2293, R@5=0.3337, R@10=0.5110, R@20=0.6599, Hit@20=0.7478, BCY@8k=0.0652
```

---

## 2. Click and Clap Interpretation & Separation

A major conceptual flaw in the initial Stage 3.8 draft was conflating **ranking quality** (MRR) with **retrieval coverage** (Recall@20 / Hit@20), improperly describing `pallets/click` as an overall improvement.

### 2.1 Precise Breakdown of Click & Clap

| Repository | Metric | Reference `EXP-384` | Edge-Gated `EXP-386` | Delta | Interpretation |
|---|---|---:|---:|---:|---|
| **`pallets/click`** ($N=26$) | **MRR** | **0.1281** | **0.1230** | **-0.0051** | **REGRESSION** (Top-1 reciprocal rank worsened) |
| `pallets/click` | **Recall@20** | **0.6667** | **0.7436** | **+0.0769** | **IMPROVEMENT** (More gold files entered top 20) |
| `pallets/click` | **Hit@20** | **0.6923** (18/26) | **0.7692** (20/26) | **+0.0769** | **IMPROVEMENT** (+2 queries succeeded in top 20) |
| `pallets/click` | **BCY@8k** | **0.0385** | **0.0385** | **0.0000** | Neutral |
| **`clap-rs/clap`** ($N=10$) | **MRR** | **0.0814** | **0.0830** | **+0.0016** | **IMPROVEMENT** |
| `clap-rs/clap` | **Recall@20** | **0.2000** | **0.3000** | **+0.1000** | **IMPROVEMENT** |
| `clap-rs/clap` | **Hit@20** | **0.3000** (3/10) | **0.4000** (4/10) | **+0.1000** | **IMPROVEMENT** (+1 query succeeded in top 20) |
| `clap-rs/clap` | **BCY@8k** | **0.0000** | **0.0000** | **0.0000** | Neutral |

### 2.2 Historical Baseline Origin of 0.4231 (Click) and 0.4000 (Clap)
An auditing question arose regarding the origin of `0.4231` (Click) and `0.4000` (Clap) appearing in earlier working notes:
- **Click**: In the historical Stage 2 / Stage 3.14 / Stage 3.19 baseline benchmarks ([`PER_REPOSITORY_RESULTS.csv`](file:///F:/RepoNeedle/research/stage3_14/PER_REPOSITORY_RESULTS.csv#L128)), the unassisted **BASE-BM25** baseline achieved Recall@20 = 11/26 = **0.4231** (Hit@20 = 0.4231).
- **Clap**: Similarly, in the historical Stage 3.14 baseline benchmarks ([`PER_REPOSITORY_RESULTS.csv`](file:///F:/RepoNeedle/research/stage3_14/PER_REPOSITORY_RESULTS.csv#L29)), **BASE-BM25** achieved Hit@20 = 4/10 = **0.4000** (Recall@20 = 0.3000).
- **Audit Conclusion**: These figures were historical unassisted BM25 baseline metrics mistakenly quoted as reference points in early working notes. The true unconstrained Stage 3.8 experimental reference values from `EXP-384` are Recall@20 = **0.6667** (Click) and **0.2000** (Clap), as correctly documented in [`REPOSITORY_LEVEL_RESULTS.csv`](file:///F:/RepoNeedle/research/stage3_8/REPOSITORY_LEVEL_RESULTS.csv).

### 2.3 Forensic Conclusion on Click
- In `Click`, edge-type attenuation prevented test files from leapfrogging `src/click/core.py` down past rank 20. This lifted Hit@20 from 18/26 to 20/26 queries and Recall@20 by +0.0769 (0.6667 to 0.7436).
- However, for queries where `core.py` was ranked at rank #2 or #3, attenuating test predecessors did not always place `core.py` at rank #1, resulting in slight top-rank reciprocal dilution ($\Delta \text{MRR} = -0.0051$, 0.1281 to 0.1230).
- **Click must be reported as a coverage vs precision trade-off, not an unqualified success.**

---

## 3. Forensic Investigation of Failed Verification Commands

Two verification commands exited with code 1 during earlier sessions:

### 3.1 Command 1: Step 11924 ("verify Stage 3.8 dataset and EXP-384 reproduction")
- **Invocation**: Shell inline command executing `python -c "..."`.
- **Actual Shell Output**:
  ```text
    File "<string>", line 20
      print(f'Mismatch in query {r[" query_id\]}:
                                   ^
  SyntaxError: unterminated string literal (detected at line 20)
  ```
- **Root Cause**: PowerShell tokenized the inline command string and unescaped `\"query_id\"` before passing it to Python. Python received an unclosed single quote followed by an orphaned backslash, triggering a Python syntax parser failure before executing any evaluation logic.

### 3.2 Command 2: Step 11926 ("verify Stage 3.8 dataset and reproduction")
- **Actual Shell Output**:
  ```text
    File "<string>", line 22
      print(f'Mismatch in query {r[" query_id\]}:
                                   ^
  SyntaxError: unterminated string literal (detected at line 22)
  ```
- **Root Cause**: Identical PowerShell string interpolation / quote escaping failure.

### 3.3 Proof of Complete Resolution
To eliminate shell quoting ambiguity, the verification logic was authored as a self-contained file: [`research/stage3_8/scripts/audit_stage3_8_results.py`](file:///F:/RepoNeedle/research/stage3_8/scripts/audit_stage3_8_results.py).
Executing `python research/stage3_8/scripts/audit_stage3_8_results.py`:
- Exited with **Code 0**.
- Verified all 345 query IDs match the official ARB v2 positive benchmark with zero missing, duplicate, or excluded records.
- Confirmed bit-for-bit reproduction of EXP-384 against EXP-378.

---

## 4. Per-Query Result & Metric Formulation Audit

### 4.1 Data Completeness & Integrity
- **Query Count**: 345 positive ARB v2 queries across 4 tracks (`code2test`, `comment2context`, `trace2code`, `edit2ripple`).
- **Repository Count**: 25 repositories ($K=25$).
- **Corpora Count**: 218 commit splits.
- **System Records**: 345 queries $\times$ 5 configurations = 1,725 complete paired evaluations.
- **Missing / Duplicated / Excluded Queries**: **0**.

### 4.2 Exact Mathematical Definitions & Denominators

1. **Mean Reciprocal Rank (MRR)**:
   $$\text{MRR} = \frac{1}{|Q|} \sum_{q \in Q} \text{RR}(q), \quad \text{RR}(q) = \begin{cases} \frac{1}{\text{rank}_1(q)} & \text{if a gold file is retrieved} \\ 0 & \text{otherwise} \end{cases}$$
   where $|Q| = 345$, and $\text{rank}_1(q) \in \{1, 2, \dots, |D_q|\}$ is the 1-based index of the first gold file.

2. **Fractional Recall@K**:
   $$\text{Recall@K}(q) = \frac{|\text{Gold}(q) \cap \text{Ranked}_{1..K}(q)|}{|\text{Gold}(q)|}, \quad \overline{\text{Recall@K}} = \frac{1}{|Q|} \sum_{q \in Q} \text{Recall@K}(q)$$
   **Denominator**: For each query, the denominator is $|\text{Gold}(q)|$ (the number of gold files for that query). The mean is aggregated across all 345 queries.

3. **Binary Hit@K**:
   $$\text{Hit@K}(q) = \begin{cases} 1.0 & \text{if } |\text{Gold}(q) \cap \text{Ranked}_{1..K}(q)| > 0 \\ 0.0 & \text{otherwise} \end{cases}, \quad \overline{\text{Hit@K}} = \frac{1}{|Q|} \sum_{q \in Q} \text{Hit@K}(q)$$
   **Denominator**: Total query count $|Q| = 345$.

4. **Budgeted Context Yield at 8k Budget (BCY@8k — Character-Level Context Coverage vs. Token-Level Yield)**:
   $$\text{BCY@8k}(q) = \frac{|\text{Gold}(q) \cap \text{PackedChunks}_{8\text{k}}(q)|}{|\text{Gold}(q)|}$$
   - **Canonical Benchmark Definition (Character-Level Context Coverage)**:
     As implemented in `agent_retrieval_bench.baseline.gold_coverage_at_budget(gold, ranked_chunks, 8000)`, the budget `context_budget = 8000` accumulates `len(chunk["text"])` in characters. Python string character length is summed until reaching 8,000 characters (approximately 1,600 to 2,000 BPE tokens). This character-level metric is the canonical `BCY@8k` used in Stage 3.7.1, Stage 3.8, and the official ARB v2 benchmark runner.
     - Candidate C: **0.0203**
     - EXP-384: **0.0527**
     - EXP-386: **0.0556**
     - RepoMap: **0.0652**
   - **Token-Level Yield Definition (Contrast)**:
     In token-level packing routines, chunks are tokenized via a BPE tokenizer (e.g. tiktoken/cl100k) until accumulating 8,000 *tokens* (~32,000 characters). Because 8,000 tokens accommodates roughly 4x more text than 8,000 characters, token-level packing produces substantially higher numerical values (e.g. RepoMap: **0.3177**, BM25: **~0.20**).
   - **Integrity Rule**: These two definitions must never be mixed on the same leaderboard. All Stage 3.8 and Stage 3.7.1 comparisons report canonical **character-level context coverage at an 8,000-character budget**.

### 4.3 10,000-Iteration Clustered Bootstrap Verification
The bootstrap implementation in [`research/stage3_8/scripts/compute_stage3_8_statistics.py`](file:///F:/RepoNeedle/research/stage3_8/scripts/compute_stage3_8_statistics.py):
- Groups the 345 queries into $K=25$ repository clusters: $C_1, C_2, \dots, C_{25}$.
- Generates 10,000 cluster resamples with replacement using `numpy.random.default_rng(42)`.
- Calculates mean cluster delta for each iteration: $\delta_b = \frac{1}{25} \sum_{k=1}^{25} (\overline{X}_{\text{cand}, b(k)} - \overline{X}_{\text{ref}, b(k)})$.
- Evaluates the 2.5th and 97.5th empirical percentiles.
- Result for `EXP-386` vs `EXP-384`: 95% CI is **`[-0.0017, +0.0027]`**, with $p = 0.6021$ ($t$-test) and $p = 0.2330$ (Wilcoxon).
- **Because the lower bound is $-0.0017 \le 0.0$, the result is strictly inconclusive.**

---

## 5. Final Repository & Environment State

```text
Active Branch: research/stage3_8
HEAD Commit:   f61c6be926fa4df0caaba5a1bff5a0c2a00794d2

Frozen Baseline Tags:
  v0.1.0-baseline:        8e0042553a14b6e3c6cf5b35823c4da84181a8e9 (VERIFIED UNCHANGED)
  stage3-candidate-freeze: cd7f3b01e28695f9a9357e0815069e0eae85baca (VERIFIED UNCHANGED)

Codebase Audit:
  reponeedle/ production package: UNTOUCHED (0 changes)
  external/agent-retrieval-bench/: UNTOUCHED (0 changes)
  Test Suite Status: 249 / 249 tests passing (100%)
```

---

## 6. Final Decision & Research Governance Reaffirmation

The findings of this audit reaffirm the preregistered research governance decision:

| Criterion | Target Requirement | Measured Value | Audit Outcome |
|---|---|---|:---:|
| Criterion 1 | Valid unconstrained evaluation over 345 positive queries | Evaluated across 345 queries, 25 repos, 218 corpora | **PASS** |
| Criterion 2 | MRR improvement $\ge +0.0100$ over reference | $\Delta \text{MRR} = +0.0010$ ($0.2062 - 0.2052$) | **FAIL** |
| Criterion 3 | 95% Clustered Bootstrap CI lower bound $> 0.0000$ | 95% CI is `[-0.0017, +0.0027]` (lower bound $\le 0$) | **FAIL** |
| Criterion 4 | No material Recall@20 regression | $\Delta \text{Recall@20} = +0.0058$ ($0.5566 - 0.5508$) | **PASS** |
| Criterion 5 | No latency or RSS regressions | Median latency 2.6–3.6 ms, RSS $< 160$ MB | **PASS** |

### Official Verdict: **INCONCLUSIVE / PROMISING**
`EXP-386` (Edge-Type-Aware Directional Gating) is the best development configuration discovered to date, achieving **0.2062 MRR** and **0.5566 Recall@20** with 63 query wins against 30 losses. However, because it fails Criteria 2 and 3, it **must NOT be promoted to an independently validated winner**.

