# RepoNeedle — Phase R5: Change-Impact Feature & Leakage Audit

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R5 — Function-Level, Change-Aware Code Retrieval  
**Date**: November 2, 2026  
**Status**: Formal Code-Level Forensic Verification  

---

## 1. Executive Summary & Audit Mandate

In information retrieval research, feature engineering can easily cross into accidental label leakage (e.g., using test annotations, benchmark ground-truth paths, or hardcoded repository heuristics).

This audit conducted a strict, line-by-line inspection of [`ChangeImpactEngine`](file:///F:/RepoNeedle/research/v1_accuracy/ranking_0_80/r5/src/change_impact.py#L32) and [`R5Ranker`](file:///F:/RepoNeedle/research/v1_accuracy/ranking_0_80/r5/src/ranker_r5.py#L48) to certify zero-oracle compliance.

---

## 2. Leakage Checklist Verification

| Audit Check | Verified State | Audit Status |
| :--- | :--- | :---: |
| **Gold Path Access** | Ground truth `gold_files` is NEVER passed to rankers or indexers | **PASSED (CLEAN)** |
| **Benchmark Track Labels** | Track tags (`code2test`, `trace2code`) stripped before inference | **PASSED (CLEAN)** |
| **Repository Name Hardcoding** | No rules matching repository names (`gin`, `clap`, `tokio`, etc.) | **PASSED (CLEAN)** |
| **Target Count Hardcoding** | Ranking algorithms do not assume or enforce fixed target counts | **PASSED (CLEAN)** |
| **Runtime Data Sources** | Operates strictly on `query_text` and candidate file paths | **PASSED (CLEAN)** |

---

## 3. How Input Change Information Becomes Graph Evidence

The `ChangeImpactEngine` converts raw input text and candidate file paths into typed graph relationships via five zero-oracle static inference rules:

### 3.1 Seed File Extraction
- Inputs: `query_text` string alone.
- Method: `SeedExtractor.extract_seeds(query_text)` uses regular expressions to find file paths mentioned in the query text (e.g. `{"changed_file": "src/parser.rs"}` or backticked paths `` `src/parser.rs` ``).
- Ground truth target files are never referenced.

---

### 3.2 Concrete Examples of Typed Edge Construction

#### Example 1: `TESTS_BEHAVIOR` (Implementation $\to$ Test Suite)
- **Input Seed**: `clap_builder/src/output/help_template.rs`
- **Extracted Seed Tokens**: `{"output", "help", "template"}`
- **Candidate File**: `tests/builder/help.rs`
- **Candidate Properties**: Path contains `"test"` and basename is `"help.rs"`.
- **Inferred Relationship**:
  $$\text{Overlap} = |\{\text{"help"}\} \cap \{\text{"output", "help", "template"}\}| = 1$$
  $$\text{Score} = (0.7 + 0.3 \times 1) \times 1.6 \text{ (test intent boost)} = 1.60 \to \text{clipped to } 1.0$$
- **Outcome**: Companion test file is prioritized without prior knowledge that it was the gold label.

#### Example 2: `CHANGED_CALLER` (Changed Function $\to$ Downstream Caller)
- **Input Seed**: `src/auth/session_manager.py`
- **Candidate File**: `src/auth/session_storage.py`
- **Candidate Properties**: Same directory sibling (`src/auth/`) and shared stem `"session"`.
- **Inferred Relationship**:
  $$\text{Same Dir Bonus} = 0.5 + 0.25 \times 1 = 0.75 \times 1.5 \text{ (reference intent boost)} = 1.0$$
- **Outcome**: Sibling caller module is promoted based purely on directory locality and token stems.

#### Example 3: `MODULE_BUILD_CONFIG` (Source Module $\to$ Build Manifest)
- **Input Seed**: `clap_builder/src/output/help_template.rs`
- **Candidate File**: `Cargo.toml`
- **Candidate Properties**: File basename is `Cargo.toml` located in the ancestor directory of the seed.
- **Inferred Relationship**:
  $$\text{Score} = 0.40 \times \text{config\_mult}$$
- **Outcome**: Build manifest is linked to its constituent source modules.

#### Example 4: `PUBLIC_SYMBOL_DOCS` (Public Interface $\to$ Documentation)
- **Input Seed**: `src/parser.py`
- **Candidate File**: `docs/parser.md`
- **Candidate Properties**: Extension is `.md` and matches token `"parser"`.
- **Inferred Relationship**:
  $$\text{Score} = 0.35$$
- **Outcome**: Documentation files referencing modified modules are recognized.

---

## 4. Auditor Conclusion on Feature Integrity

All typed change-impact features are derived from **observable static repository topologies and query text tokens**. No evaluation annotations, benchmark answer sheets, or test labels leak into the ranking pipeline.

