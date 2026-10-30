# RepoNeedle Stage 3.17 — Frozen Official ContextBench Evaluation Report

**Document ID**: `STAGE3-17-REPORT-001`  
**Date**: October 2026  
**Git Branch**: `research-program`  
**Base Commit**: `548dab5eea6c71c3e9982676289098d9e0dca5f0`  
**Production Code Reference**: `12142e8`  
**Frozen Baseline Tag**: `v0.1.0-baseline` (`8e0042553a14b6e3c6cf5b35823c4da84181a8e9`) — **VERIFIED UNCHANGED**  
**Frozen Candidate Tag**: `stage3-candidate-freeze` (`cd7f3b01e28695f9a9357e0815069e0eae85baca`) — **VERIFIED UNCHANGED**  
**Final Governance Verdict**: **`BLOCKED — DATA ACQUISITION OR VALIDATION FAILED`**  

---

## 1. Executive Summary & Mission Charter

Stage 3.17 executes the evaluation integrity gate for independent external validation of RepoNeedle against the official ContextBench benchmark (`Contextbench/ContextBench`, official EuniAI benchmark at pinned revision `c285579`).

In accordance with the Stage 3.17 research charter:
1. **Zero Algorithm Tuning**: Production retrieval code under `reponeedle/` was completely frozen. Ranking weights, graph parameters, candidate configurations, thresholds, and retrieval algorithms were untouched.
2. **Strict Dataset Validation Contract**: The intake validator ([`research/external_data/contextbench/validate_contextbench.py`](file:///F:/RepoNeedle/research/external_data/contextbench/validate_contextbench.py)) was executed to verify the presence, row counts, cryptographic hashes, and byte sizes of `full.parquet` (1,136 tasks, SHA-256: `2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8`, 26,102,607 bytes) and `contextbench_verified.parquet` (500 tasks, SHA-256: `e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791`, 9,558,250 bytes).
3. **Fail-Closed Gate Enforcement**: Because both Parquet artifacts are missing from [`research/external_data/contextbench/`](file:///F:/RepoNeedle/research/external_data/contextbench) and network access to Hugging Face is blocked by standard container isolation (`HTTP Error 403: Forbidden`), the evaluation gate failed closed with exit code `2`.
4. **Rejection of Synthetic Substitutes**: Unofficial mirrors (`Schwerli/ContextBench`) and synthetic/mock Parquet files were strictly rejected. No fabricated numbers were generated.
5. **Frozen Candidate Alignment**: Candidate configurations (`ARM-101-BASE`, `BASE-BM25`, `BASE-REPOMAP`) remain locked. Historical Candidate F was confirmed permanently invalidated ($0.1351$ MRR on unconstrained corpus), establishing `ARM-101-BASE` as the sole legitimate candidate champion.

---

## 2. Research Safeguards & Tag Immutability

Prior to conducting any analysis, repository state and baseline tags were verified:

```
Branch: research-program
Starting HEAD: 548dab5eea6c71c3e9982676289098d9e0dca5f0
Tag v0.1.0-baseline: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9 (MATCH)
Tag stage3-candidate-freeze: cd7f3b01e28695f9a9357e0815069e0eae85baca (MATCH)
Working Tree: Clean
Production Code reponeedle/: Untouched (0 diffs against base commit)
```

No git tags were moved, retagged, or deleted.

---

## 3. Dataset Validation & Integrity Audit

### 3.1 Upstream Specification
The target benchmark dataset is the official ContextBench release:
- **Repository**: `https://huggingface.co/datasets/Contextbench/ContextBench`
- **Pinned Commit Revision**: `c285579`
- **Full Configuration (`full.parquet`)**:
  - Rows: 1,136
  - Repositories: 66
  - Languages: 8 (Python, TypeScript, JavaScript, Go, Java, Rust, C, C++)
  - Size: 26,102,607 bytes
  - SHA-256: `2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8`
- **Verified Configuration (`contextbench_verified.parquet`)**:
  - Rows: 500
  - Repositories: 35
  - Languages: 8
  - Size: 9,558,250 bytes
  - SHA-256: `e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791`

### 3.2 Audit Execution
The automated intake validator was run:
```powershell
python research/external_data/contextbench/validate_contextbench.py
```
Output:
```
================================================================================
REPONEEDLE: OFFICIAL CONTEXTBENCH VALIDATION GATE (STAGE 3.17)
Data Directory: F:\RepoNeedle\research\external_data\contextbench
Pinned Upstream Revision: c285579
================================================================================

[STATUS: BLOCKED - DATA ACCESS]
No ContextBench artifacts found in F:\RepoNeedle\research\external_data\contextbench.
Required artifacts:
  - full.parquet (expected SHA: 2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8, 26102607 bytes)
  - contextbench_verified.parquet (expected SHA: e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791, 9558250 bytes)
Network boundary prevents automated acquisition from Hugging Face.
See research/external_data/contextbench/ACQUISITION_BLOCKER.md for handoff instructions.
ExitCode: 2
```

In accordance with Section 2 of the Stage 3.17 prompt, the evaluation immediately stopped upon detecting missing files.

---

## 4. Frozen Evaluation Configurations

The following systems are preregistered and frozen for independent external evaluation once datasets are acquired:

| System ID | Architecture Configuration | ARB v2 MRR | ARB v2 Recall@20 | ARB v2 P50 Latency (ms) | Role in Independent Evaluation |
|---|---|---|---|---|---|
| **`ARM-101-BASE`** | Soft Lexical Damping ($\tau=0.25$) + Level 1 Verified Function Call Edges | **0.2078** | **0.5648** | **12.92** | **Preregistered Candidate Champion** |
| **`BASE-BM25`** | Decoupled Okapi BM25 length-normalized scoring | **0.1752** | **0.4535** | **10.24** | **Preregistered Lexical Baseline (Lower Bound)** |
| **`BASE-REPOMAP`** | Official Aider RepoMap reference (commit `9e4d689`) | **0.2293** | **0.6599** | **180.20** | **Preregistered External Leader Reference (Upper Bound)** |

See [`research/stage3_17/EVALUATION_CONFIGURATIONS.md`](file:///F:/RepoNeedle/research/stage3_17/EVALUATION_CONFIGURATIONS.md) for architectural details.

---

## 5. Candidate Naming Reconciliation

### Historical Candidate F Invalidation
In Stage 3.5, Candidate F was reported with an MRR of **0.2152**. However, subsequent audits (Stage 3.10 through Stage 3.15) discovered that Candidate F's evaluation relied upon:
1. Artificial test-only candidate filtering for `code2test` tasks.
2. A constrained 20-file evaluation corpus rather than full-repository candidate generation.

When Candidate F was evaluated under canonical, unconstrained conditions across all 345 positive ARB v2 queries, its MRR collapsed to **0.1351** ($p = 0.0122$ worse than standard BM25 at $0.1752$).

### Resolution
- Candidate F is formally retired and must not be used as a candidate champion or evaluation baseline.
- `ARM-101-BASE` is the true, robust candidate champion, maintaining an MRR of **0.2078** under strict unconstrained full-repository retrieval.

---

## 6. Preregistered Acceptance Criteria

When independent validation is unblocked, `ARM-101-BASE` will be evaluated against ContextBench using the following preregistered thresholds:

1. **Quality Criteria**:
   - $\text{MRR}(\text{ARM-101}) > \text{MRR}(\text{BASE-BM25})$ with repository-clustered bootstrap $p < 0.05$.
   - $\text{Recall@20}(\text{ARM-101}) > \text{Recall@20}(\text{BASE-BM25})$ with repository-clustered bootstrap $p < 0.05$.
   - Parity with `BASE-REPOMAP`: $\Delta \text{MRR} > -0.03$.
2. **Latency Criteria**: P50 query latency $< 20.0\text{ ms}$, P95 $< 100.0\text{ ms}$.
3. **Memory Criteria**: Process RSS $< 200.0\text{ MB}$ across all benchmark repositories.
4. **Integrity Criteria**: Zero target leakage via [`LeakageGuard`](file:///F:/RepoNeedle/research/contextbench_evaluation/leakage_guard.py), strict denominator preservation (checkout failures $\to$ 0.0 score).

---

## 7. Deliverables Catalog

All Stage 3.17 research artifacts have been generated and validated:

1. [`research/stage3_17/STAGE3_17_REPORT.md`](file:///F:/RepoNeedle/research/stage3_17/STAGE3_17_REPORT.md): Primary audit and evaluation gate report.
2. [`research/stage3_17/DATASET_VALIDATION_REPORT.md`](file:///F:/RepoNeedle/research/stage3_17/DATASET_VALIDATION_REPORT.md): Exhaustive forensics on expected dataset revision `c285579` and missing file verification.
3. [`research/stage3_17/EVALUATION_CONFIGURATIONS.md`](file:///F:/RepoNeedle/research/stage3_17/EVALUATION_CONFIGURATIONS.md): Frozen candidate specifications and Candidate F naming reconciliation.
4. [`research/stage3_17/DECISION_REPORT.md`](file:///F:/RepoNeedle/research/stage3_17/DECISION_REPORT.md): Executive decision ratifying `BLOCKED — DATA ACQUISITION OR VALIDATION FAILED`.
5. [`research/stage3_17/dataset_manifest.json`](file:///F:/RepoNeedle/research/stage3_17/dataset_manifest.json): Machine-readable dataset specification and blocker record.
6. [`research/stage3_17/evaluation_manifest.json`](file:///F:/RepoNeedle/research/stage3_17/evaluation_manifest.json): Machine-readable preregistration of candidate configurations and evaluation rules.
7. [`research/stage3_17/EXPERIMENT_REGISTRY.jsonl`](file:///F:/RepoNeedle/research/stage3_17/EXPERIMENT_REGISTRY.jsonl): Audit experiment registry entries (EXP-080 through EXP-085).
8. [`research/stage3_17/REPRODUCE.md`](file:///F:/RepoNeedle/research/stage3_17/REPRODUCE.md): Deterministic reproduction instructions.
9. [`research/external_data/contextbench/validate_contextbench.py`](file:///F:/RepoNeedle/research/external_data/contextbench/validate_contextbench.py): Updated validator checking revision `c285579`, exact byte sizes, SHA-256 hashes, and subset integrity.
10. [`tests/test_stage3_17_evaluation_gate.py`](file:///F:/RepoNeedle/tests/test_stage3_17_evaluation_gate.py): Automated pytest verification suite.

---

## 8. Final Governance Verdict

```
================================================================================
GOVERNANCE VERDICT: BLOCKED — DATA ACQUISITION OR VALIDATION FAILED
================================================================================
```

Stage 3.17 terminates with a clean, fail-closed gate stop. Evaluation will be executed immediately when `full.parquet` and `contextbench_verified.parquet` are provided by an operator outside the sandbox.
