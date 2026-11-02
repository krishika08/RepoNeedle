# REPONEEDLE MISSION 0.80+ — PHASE R3
# DELIVERABLE 12: EXECUTIVE FINAL DECISION REPORT

**Author**: Principal Information Retrieval Engineer, Search Systems Architect  
**Date**: November 2, 2026  
**Status**: APPROVED & FROZEN  
**Target Milestone**: Phase R3 (AST Symbol Intelligence + BM25L Ranking)  

---

## 1. EXECUTIVE SUMMARY & DECISION

Phase R3 of the **Mission 0.80+ Ranking Intelligence Programme** investigated AST Symbol Intelligence and BM25 length-normalization variants (BM25Okapi, BM25L, BM25+, and Field-Weighted BM25).

```
========================================================================================
                               PHASE R3 DECISION GATE
========================================================================================
Aspirational Target:             MRR >= 0.80
Frozen Reference Baseline (R2):  Treatment E (Validation MRR = 0.2971, Held-Out = 0.2965)
Phase R3 Champion:               Treatment I (Validation MRR = 0.3124, Train = 0.5278)
Repository-Clustered 95% CI:     [-0.0326, +0.0330] (Spans zero; P*(Delta <= 0) = 0.2906)
Held-Out Confirmation:           MRR = 0.2835 (Regression of -0.0129 vs Baseline)
Full-Pool Candidate Recall:      100.0% (514/514 Gold Candidates Preserved)

FINAL DECISION:                  CONDITIONAL RETENTION & EXPERIMENTAL ARCHIVE
PRODUCTION PROMOTION:            REJECTED (Retain Treatment E as Authoritative Production Baseline)
R4 AUTHORIZATION:                AUTHORIZED (Dense Neural Embeddings & Hybrid Fusion)
========================================================================================
```

---

## 2. SCIENTIFIC & ENGINEERING EVALUATION

### 2.1 What Succeeded in R3
1. **Traceback Execution Demotion (`trace2code`)**:
   - In `trace2code` queries, developers provide terminal logs or failure excerpts.
   - Demoting test files ($\times 0.05$) and boosting matching implementation symbols caused `trace2code` MRR to surge from **0.4724 to 0.7138 (+51.1% relative)**.
2. **BM25L Length Normalization**:
   - Quantitatively proved that standard Okapi BM25 suffers a **68.6% score collapse** on long files (ratio 20.0x avgdl).
   - BM25L maintained 55.0% higher score fidelity on massive modules, stabilizing large driver files in repositories like `transformers` and `vite`.
3. **Training & Validation Point Improvements**:
   - Train MRR advanced from **0.4544 to 0.5278** (+0.0734, paired permutation $p = 0.0001$).
   - Validation MRR advanced from **0.2971 to 0.3124** (+0.0153, +5.15% relative).
   - Hit@1 advanced from **16.67% to 18.33%**.

### 2.2 Why Production Promotion Is Rejected
1. **Repository-Clustered Uncertainty**:
   - The 95% repository-clustered bootstrap confidence interval spans zero: **`[-0.0326, +0.0330]`**.
   - With $P^*(\Delta \le 0) = 0.2906$, the observed validation gain cannot be guaranteed across unseen repositories.
2. **Held-Out Regression on Meta-Testing Repositories**:
   - On the Confirmation partition (75 queries), Treatment I scored **0.2835** vs **0.2965** for Treatment E (-0.0129).
   - In meta-testing repositories like `pytest-dev/pytest`, framework source code resides inside testing subdirectories (`_pytest/pytester.py`). General traceback heuristics falsely penalized internal framework code.
3. **The Lexical / AST Saturation Barrier**:
   - Neither AST symbol extraction nor BM25 variants could bridge the semantic gap to reach 0.80+ MRR.
   - In `comment2context` and `edit2ripple`, queries frequently lack exact symbol overlap with their target files, hitting the theoretical ceiling of sparse lexical/syntactic retrieval.

---

## 3. ARCHIVAL & LINEAGE PROTOCOL

1. **Production Codebase**:
   - The production codebase in `reponeedle/core/ranker.py` and `reponeedle/core/lexical.py` remains frozen at the validated Treatment E baseline.
   - No experimental R3 code is merged into production release artifacts.
2. **Research Archive**:
   - All R3 code, models, and scripts are permanently preserved under:
     - `research/v1_accuracy/ranking_0_80/r3/src/ast_symbol.py`
     - `research/v1_accuracy/ranking_0_80/r3/src/bm25_variants.py`
     - `research/v1_accuracy/ranking_0_80/r3/src/ranker_r3.py`
     - `research/v1_accuracy/ranking_0_80/r3/src/evaluate_r3.py`
     - `research/v1_accuracy/ranking_0_80/r3/PER_QUERY_COMPARISON.jsonl`
     - `research/v1_accuracy/ranking_0_80/r3/master_metrics.json`
     - `research/v1_accuracy/ranking_0_80/r3/statistical_summary.json`

---

## 4. PHASE R4 STRATEGIC ROADMAP (PATH TO 0.80+ MRR)

The empirical findings of R1, R2, and R3 establish that sparse lexical matching, AST symbol extraction, and heuristic length normalization have reached an upper bound of $\approx 0.31 - 0.44$ MRR.

To breach the 0.80 MRR milestone in Phase R4, RepoNeedle must deploy:
1. **Dense Code Representation**: Fine-tuned bidirectional code bi-encoders (e.g. UniXcoder / StarCoder) capable of mapping natural language developer queries to implementation semantics without exact keyword overlap.
2. **Hybrid Reciprocal Rank Fusion (RRF)**: Combining dense vector similarity with SFS-filtered lexical scores.
3. **Multi-Hop Dynamic Call Graphs**: Resolving indirect ripple effects across transitive caller-callee chains.

---

## 5. SIGN-OFF

The Principal Information Retrieval Engineer and Search Systems Architect certify that Phase R3 has been executed with complete scientific integrity, verified reproducibility, and rigorous data governance.

