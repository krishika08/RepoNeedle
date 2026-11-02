# RepoNeedle — Phase R6: Treatment Reconciliation & Champion Provenance

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R6 — Controlled Production Integration  
**Author**: Principal Software Architect & Information Retrieval Systems Engineer  
**Date**: November 2, 2026  
**Status**: Authoritative Champion Specification & Lineage Resolution  

---

## 1. Resolution of the Treatment D / F / G / H Naming Inconsistency

Across research documentation in Phases R5 and R6, multiple treatment letters have been applied to the typed change-impact architecture. This section establishes the authoritative, bit-level lineage and eliminates all ambiguity.

### 1.1 Historical Lineage Matrix

| Milestone | Treatment Label | Canonical Architecture Name | Functional Description | Role in Milestone |
| :--- | :---: | :--- | :--- | :--- |
| **Phase R5** | **Treatment F** | Typed Change-Impact Retrieval | SFS + TIP + Typed Graph Propagation (Import, Call, Symbol, Build, Doc, Proximity) | **Authoritative Research Champion** |
| **Phase R6** | **Treatment D** | R5 Treatment F Evaluation | Exact replication of R5 Treatment F on the 18-repository independent benchmark | **Authoritative Benchmark Champion** |
| **Phase R6** | **Treatment E** | Change-Impact (No Heuristics) | Ablation removing directory proximity, test stem, and doc matches | Controlled Ablation Model |
| **Phase R6** | **Treatment F** | Change-Impact (Verified Only) | Restricted exclusively to verified AST imports, calls, symbols, and build manifests | Controlled Ablation Model |
| **Phase R6** | **Treatment G** | Confidence-Calibrated Impact | Bayesian continuous confidence combination ($1 - \prod (1 - c_i)$) | Calibration Investigation Model |
| **Phase R6** | **Treatment H** | Best Combined Model | Bayesian calibrated impact + exact symbol channel reinforcement | Hybrid Exploratory Model |

### 1.2 Formal Resolution
> **Definitive Finding**:  
> **Phase R5 Treatment F** and **Phase R6 Treatment D** refer to the **exact same winning ranking algorithm**.  
> In Phase R6 evaluation logs and `PER_QUERY_RESULTS.jsonl`, this model is recorded under treatment tag `"D"`.  
> In Phase R5 summary documents, it was recorded under treatment tag `"F"`.  
> For production integration into RepoNeedle V1.1, this verified algorithm is designated formally as:
> ```python
> ranking_engine = "change_impact"
> ```

---

## 2. Exact Specification of the Champion Algorithm

### 2.1 Formula & Feature Lineage
For candidate file $c$, query text $q$, and seed files $S = [s_1, \dots, s_k]$:

1. **First-Stage Lexical Score**:
   $$S_{\text{lex}}(c) = \text{cand}["\text{m1\_score}"]$$

2. **Seed File Suppression (SFS)**:
   $$\text{Mult}_{\text{SFS}}(c) = \begin{cases} 0.01 & \text{if } c \in S \\ 1.00 & \text{otherwise} \end{cases}$$

3. **Test Intent Prior (TIP)**:
   $$\text{Mult}_{\text{TIP}}(c) = \begin{cases} 1.45 & \text{if } \text{is\_test\_query}(q) \land \text{is\_test}(c) \\ 0.85 & \text{if } \neg \text{is\_test\_query}(q) \land \text{is\_test}(c) \\ 1.00 & \text{otherwise} \end{cases}$$

4. **Change-Impact Graph Boost**:
   $$S_{\text{R6}}(c) = \left( S_{\text{lex}}(c) \times \text{Mult}_{\text{SFS}}(c) \times \text{Mult}_{\text{TIP}}(c) \right) + 3.0 \times \text{Impact}(c, S, q)$$

   Where $\text{Impact}(c, S, q) = \max_{e \in \text{Edges}(c, S)} W(e, q)$, with edge weights:
   - `HEURISTIC_TEST_STEM`: $0.85$ (if test intent) / $0.55$ (general)
   - `CONFIRMED_IMPORT`: $0.75$
   - `HEURISTIC_DIR_PROXIMITY`: $0.75$
   - `CONFIRMED_SYMBOL`: $0.80$
   - `CONFIRMED_CALL`: $0.80$
   - `CONFIRMED_BUILD`: $0.40$
   - `HEURISTIC_DOC`: $0.35$
   - `HEURISTIC_ANCESTOR`: $0.30$

---

## 3. Cryptographic Checksum Manifest

All source and dataset artifacts are verified with SHA-256 digests:

| File Path | SHA-256 Checksum | Purpose / Contents |
| :--- | :--- | :--- |
| `research/.../r6/src/ranker_r6.py` | `dfd7bf6ae8350a4d73a55ee3440cdc05a9933e48df2ccc932ca05459e8392b5c` | Exact scoring implementation for Treatments A–H |
| `research/.../r6/src/graph_evidence.py` | `9879a4d2e2e284d4d0cf41840de363633ae35b46646bebc70907408a452c3979` | Provenance classification & edge auditing |
| `research/.../r6/src/evaluate_r6.py` | `36c9ece3d581fb3c1a856268bda78d192efbfcb682a33d3cbeaa8ee0c19856f0` | Resampling harness & per-query evaluator |
| `research/.../r6/src/task_definitions.py`| `dc595273a37a3c67363143c1d923cc6926764663fa2172807a03caadc6afe03a` | 180 authentic developer tasks |
| `research/.../r6/independent_benchmark.json.gz` | `e4b0dad8a7a98bc07c08410f17338671902dd5d048adda97b9acd7d56d5212bd` | 18-repository evaluation benchmark |
| `research/.../r6/master_metrics.json` | `5a1b8a3cf4c311ec32a65e93281c6adc243cbe639bc9fbd0cd91c865e8021ea2` | Authoritative partition metrics |

---

## 4. Metric Reproduction Table

Bit-for-bit reproduction of reported metrics across all three independent partitions:

| Partition | Queries | Baseline Treatment B (MRR) | Champion Treatment D (MRR) | Observed Lift ($\Delta \text{MRR}$) | Baseline Recall@20 | Champion Recall@20 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Train** | 90 | 0.6213 | **0.6546** | **+0.0333** | 0.9000 | **1.0000** |
| **Validation** | 40 | 0.6472 | **0.6708** | **+0.0236** | 0.9125 | **1.0000** |
| **Held-Out** | 50 | 0.5215 | **0.5467** | **+0.0252** | 0.9200 | **1.0000** |
| **Overall (Pooled)** | 180 | 0.5993 | **0.6282** | **+0.0289** | 0.9083 | **1.0000** |

