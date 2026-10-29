# RepoNeedle Stage 3.12A: Git and Artifact Provenance Audit

**Stage**: Stage 3.12A — Canonical Evaluation Reconciliation and Graph Research Gate  
**Workspace**: `F:\RepoNeedle`  
**Branch**: `research-program`  
**HEAD Commit**: `3f4822d` (Stage 3.11 Function-Level Graph Retrieval Research)  
**Historical Anchor Commit**: `4f78cc3` (Stage 3.5 Polyglot Graph Resolution)  
**Date**: October 29, 2026  

---

## 1. Repository Provenance and Git Ancestry

### 1.1 Lineage Verification
A complete Git ancestry audit was performed between Stage 3.5 (`4f78cc3`) and Stage 3.11 (`3f4822d`):
```bash
git merge-base 4f78cc3 3f4822d
# Output: 4f78cc3658dfb5e338a5458579d38d5d7ef416e8

git merge-base --is-ancestor 4f78cc3 3f4822d
# Output: True
```

`4f78cc3` is confirmed to be a direct linear ancestor of `3f4822d`. Exactly 21 commits separate them in the `research-program` history:
- `3f4822d`: Stage 3.11 function-level call graph retrieval research
- `768f69d`: Stage 3.10.2 canonical evaluation integrity gate and independent verification
- `7679b40`: Stage 3.10.1 reproducibility reconciliation gate and metric validation
- `21d2586`: Stage 3.10 class-to-test invocation graph research (4-arm canonical evaluation)
- `110ff88`: Stage 3.9.2 cross-stage metric reconciliation and context-budget validity audit
- `b7cf35b`: Stage 3.9.1 metric integrity gate and 2,415-row independent recomputation
- `064e619`: Stage 3.9 cascaded lexical-first architecture and Gate B ablation
- `174c260`: Stage 3.8 independent metric verification and graph damage audit
- `fd45220`: Stage 3.7 canonical evaluation reconciliation and fail-closed audit
- `9a9944a`: Stage 3.6 forensic reproducibility audit and Candidate F validation gate
- `29bb3b9`: Stage 3.15 ContextBench acquisition audit and locked evaluation protocol
- `3e889fc`: Stage 3.14 historical errata and runtime/memory reconciliation
- `bf7f4c8`: Stage 3.13 canonical evidence reconciliation and independent validation readiness
- `e350b14`: Stage 3.12 performance hardening and fair benchmarking
- `59e77e6`: Stage 3.11 cross-stage reconciliation and statistical audit
- `6ada204`: Stage 3.10 canonical ranking recovery verification and evaluator audit
- `91c6df8`: Stage 3.9 ranking recovery, component isolation, and runtime optimization
- `fcab83b`: Stage 3.8 reproducibility lock and metric contract
- `60fb4c9`: Stage 3.7 forensic evaluation reconciliation
- `cbe6c49`: Stage 3.6 authoritative 4-system ARB v2 evaluation
- `0fdc257`: Stage 3.5 trailing newline normalization

### 1.2 Frozen Tags Audit
Both immutable baseline and candidate tags were checked and confirmed identical to their established targets:
- `v0.1.0-baseline`: `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` (Exact match)
- `stage3-candidate-freeze`: `cd7f3b01e28695f9a9357e0815069e0eae85baca` (Exact match)

---

## 2. Cross-Stage Artifact and Evaluation Script Audit

| Stage | Script Path | Output Artifact | Candidate Universe | Evaluator Nature |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 3.5** | `research/stage3_5/evaluate_graph_retrieval.py` | `GRAPH_RETRIEVAL_RESULTS.csv` (aggregate only) | Pre-filtered (`code2test` restricted to test files; synthetic 2-file ripgrep fixture) | ARB v1.1 chunk-level `sample_metrics`; hardcoded RepoMap reference |
| **Stage 3.6** | `research/stage3_6/run_authoritative_evaluation.py` | `PER_QUERY_RESULTS.csv` | 100% unconstrained candidate pool | Corrected file-level ranking; live RepoMap run |
| **Stage 3.10.2** | `research/stage3_10_2/run_canonical_audit.py` | `INDEPENDENT_METRIC_RECOMPUTATION.csv` | 100% unconstrained candidate pool | Clean-room `independent_metrics.py` (hand-checkable) |
| **Stage 3.11** | `research/stage3_11/run_stage3_11_evaluation.py` | `RETRIEVAL_RESULTS.csv` | 100% unconstrained candidate pool | Clean-room `independent_metrics.py`; live function graph |

---

## 3. Implementation and Configuration Comparison

### 3.1 Candidate F (Stage 3.5)
- **Code Path**: `reponeedle/core/graph.py` (lines 400–450) and `research/stage3_5/evaluate_graph_retrieval.py`.
- **Ranking Formula**:
  $$\text{Score} = \text{Score}_{\text{CandC}} + 0.15 \times \text{DiffusedBoost}$$
  where $\text{DiffusedBoost}$ used top-5 lexical/semantic seeds, propagating $+0.25$ along successors and $+0.20$ along predecessors.
- **Flaws Identified**:
  1. No degree normalization (supernode utility files absorbed all graph score).
  2. No package boundary fencing (spurious cross-subsystem linkages).
  3. No lexical safeguard (corrupted top-3 BM25 ranks).
  4. Candidate pool in `code2test` was filtered to test files only, pruning distractor code files.

### 3.2 Cascaded Rankers (Stage 3.10 – Stage 3.11)
- **`CONTROL-CASCADE`**: Rank 1–3 BM25 lexical freeze, symmetric degree normalization $\frac{1}{\sqrt{\text{deg}_{\text{out}} \cdot \text{deg}_{\text{in}}}}$, package/crate boundary fencing, doc penalty ($0.5\times$).
- **`TEST-GRAPH`**: `CONTROL-CASCADE` + evidence-backed class-to-test invocation edges.
- **`FUNCTION-GRAPH`**: `TEST-GRAPH` + fine-grained AST function/method call edges (Level 1 verified + Level 2 structural) with Rank 1–3 freeze.
- **`FUNCTION-GRAPH-NO-FREEZE`**: Full function graph with the Rank 1–3 freeze relaxed, allowing dynamic score fusion across all ranks.

### 3.3 RepoMap Baseline Configuration
- **Stage 3.5**: Hardcoded dictionary constant `{"mrr": 0.2140, "r5": 0.3185, "r10": 0.4786, "r20": 0.6306, "bcy8k": 0.3788, "lat": 180.20}`.
- **Stage 3.6 through Stage 3.11**: Live empirical evaluation of version-pinned official RepoMap on commit `9e4d689`.
  - True MRR: **$0.2293$**
  - True Fractional Recall@20: **$0.6599$**
  - True Binary Hit@20: **$0.7101$**
  - True Token BCY@8k: **$0.3177$**
  - Median Warm Query Latency: **$180.20\text{ ms}$**
