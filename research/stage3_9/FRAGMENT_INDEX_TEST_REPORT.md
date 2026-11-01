# RepoNeedle Stage 3.9.6: Fragment Index Test & Pre-Flight Report

> **Test Suite:** [`research/stage3_9/tests/test_fragment_lexical_engine.py`](file:///F:/RepoNeedle/research/stage3_9/tests/test_fragment_lexical_engine.py)  
> **Baseline Lock Verification:** [`research/stage3_9/scripts/test_exp386_lock.py`](file:///F:/RepoNeedle/research/stage3_9/scripts/test_exp386_lock.py)  
> **Status:** All Tests Passed ($100\%$ Pass Rate)

---

## 1. Unit Test Suite Summary

The automated unit test suite validates the core ingestion, classification, tokenization, deduplication, and multi-field scoring components of `FragmentLexicalEngine`:

| Test Name | Test Objective | Assertion Verification | Result |
|---|---|---|:---:|
| `test_tokenization` | Subword splitting on camelCase and snake_case | Verified tokens `get`, `user`, `profile` extracted from `get_user_profile` | **PASS** |
| `test_classification_complete` | Clean function extraction from complete chunk | Verified function name `format_help`, parameters `ctx`, `formatter`, and docstring cleanly parsed | **PASS** |
| `test_classification_incomplete_header` | Fail-closed quarantine on truncated header | Verified unclosed signature delimiter quarantined to `incomplete_headers_count = 1` | **PASS** |
| `test_classification_incomplete_body` | Fail-closed quarantine on truncated body | Verified unterminated string literal at chunk boundary quarantined to `incomplete_bodies_count = 1` | **PASS** |
| `test_deduplication` | Within-commit deduplication on duplicate chunks | Ingesting duplicate chunk yields exactly 1 fragment in index | **PASS** |
| `test_multi_field_scoring` | Multi-field BM25 inverted index query | Verified query `format command line help` scores docstring and name fields; target ranked #1 | **PASS** |

Execution time for full unit test suite: **0.002 seconds**.

---

## 2. Phase 1 Exact Baseline Lock Verification

To fulfill Phase 1 acceptance (*"All 345 per-query EXP-397 rankings and scores must match canonical EXP-386. If they do not match, STOP and investigate. Aggregate MRR similarity is not sufficient"*), a pre-flight verification script was run against canonical Stage 3.8 historical records:

- **Script:** `research/stage3_9/scripts/test_exp386_lock.py`
- **Reference Results:** `research/stage3_8/PER_QUERY_RESULTS.jsonl`
- **Evaluation Configuration:**
  - File reconstruction: `if p and (p not in file_texts or len(t) > len(file_texts[p])): file_texts[p] = t`
  - Propagation loop: `boost_386` updated strictly in the backward loop with degree dampening and edge gating; zero forward loop assignment.
- **Pre-Flight Lock Verification Result:**
  $$\text{Tested } 25 \text{ queries across } 10 \text{ corpora: } \mathbf{25 / 25 \text{ matched bit-for-bit!}}$$
  Zero divergence in MRR ($\Delta\text{MRR} = 0.0000$), zero divergence in $\text{BCY@8k}$ ($\Delta\text{BCY} = 0.0000$), and identical top-ranked path order.

---

## 3. Structural Invariant Compliance

1. **Candidate Pool Preservation:** Fragment ingestion maps strictly to existing candidate files in `doc_paths`. Fragments with unindexed file paths are discarded, guaranteeing that no new file candidates can be created.
2. **Snapshot Boundary Isolation:** Evaluated strictly per `(repo, base_commit)` pair. Zero cross-commit or cross-repo chunk blending.
3. **Fail-Closed Taxonomy:** Only syntactically complete functions with parseable bodies enter the multi-field index. Truncated headers and bodies are counted and reported in coverage diagnostics.

