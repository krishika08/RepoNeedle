# REPONEEDLE STAGE 3.11: AUDIT OF LEAKAGE & GENERALIZATION CLAIMS

**Date**: October 2026  
**Document ID**: `STAGE3.11-LEAKAGE-AUDIT`  
**Git Workspace**: `F:\RepoNeedle`  
**Auditor**: Independent Retrieval Systems & Benchmark Auditor  

---

## 1. EXECUTIVE STATEMENT & CORRECTION OF PRIOR CLAIMS

In Stage 3.10, `LEAKAGE_AND_SPECIAL_CASE_AUDIT.md` concluded:
> *"The RepoNeedle codebase contains zero leakage, zero hardcoded benchmark shortcuts, and zero repository-specific bypasses. The ranking-recovery improvements observed in Stage 3.9 represent genuine algorithmic corrections that generalize across codebases."*

This statement conflated **absence of literal static strings** with **absence of benchmark exposure and tuning leakage**. This audit formally delineates four distinct scientific boundaries:

---

## 2. THE FOUR SCIENTIFIC LEAKAGE & VALIDATION BOUNDARIES

| Dimension | Scope & Methodology | Actual RepoNeedle Status | Scientific Implication |
| :--- | :--- | :--- | :--- |
| **1. Static Code String Scan** | Grepping `reponeedle/` for benchmark repo names, query IDs, or synthetic bypass tokens (`search.rs`). | **VERIFIED CLEAN (0 hits)** | Proves only that developers did not hardcode lookup tables or test-case bypasses in python files. |
| **2. Development Exposure & Hyperparameter Tuning** | Repeatedly diagnosing failures, tuning component weights, and modifying scoring equations against the ARB benchmark. | **EXTENSIVE EXPOSURE** | The ARB v2 benchmark has been evaluated continuously from Stage 2 through Stage 3.10. Parameters ($k_1=1.5, b=0.75$, docfilter $0.5\times$, subword weight $0.4\times$, diffusion bound $25$) were shaped by ARB error analysis. |
| **3. Information Leakage Controls** | Preventing query metadata, gold commit hashes, or ground truth files from leaking into feature extractors. | **CONTROLLED** | Verified: AST parser and BM25 index do not inspect query provenance or gold targets during retrieval. |
| **4. Truly Independent Generalization** | Evaluating the frozen system on an external, unseen benchmark that was never part of development or tuning. | **UNVERIFIED (`BLOCKED / PRELIMINARY`)** | ContextBench acquisition failed under execution sandbox network restrictions (`HTTP 403 Forbidden`). Zero independent validation data has been evaluated. |

---

## 3. FORMAL STATUS OF BENCHMARKS

1. **Agent Retrieval Bench (ARB v2)**:
   - **Status**: **DEVELOPMENT & REGRESSION EVIDENCE ONLY**.
   - Because ARB v2 task instances, failure modes, and repositories (`etcd`, `click`, `tokio`, `gin`) were directly inspected to develop the Stage 3.9 ranking-recovery features, ARB v2 **CANNOT be cited as proof of independent generalization**.
   - Performance on ARB v2 demonstrates that the ranking failure was successfully corrected within the development distribution.

2. **ContextBench**:
   - **Status**: **`BLOCKED / PRELIMINARY`**.
   - The official dataset at `https://huggingface.co/datasets/Contextbench/ContextBench` is inaccessible due to execution sandbox network restrictions.
   - Per research integrity rules, no synthetic, mock, or fabricated dataset will be substituted under the official ContextBench name.
   - Any claims of independent generalization remain blocked until ContextBench or another held-out benchmark is downloaded through sanctioned channels.
