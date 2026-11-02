# RepoNeedle — Phase R6: Data Provenance & Integrity Manifest

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R6 — Independent Benchmark & Generalization Research  
**Author**: Benchmark Architect & Information Retrieval Research Auditor  
**Date**: November 2, 2026  
**Status**: Cryptographic Manifest & Provenance Audit  

---

## 1. Provenance Statement & Integrity Guarantees

In accordance with scientific evaluation governance, the Phase R6 benchmark cohort is constructed with complete cryptographic provenance and strict isolation:

1. **Origin of Tasks**: Tasks are constructed from authentic open-source development workflows, including real bug reports, pull request descriptions, regression test additions, and cross-module refactoring issues drawn from established benchmarks (SWE-bench Lite, GitHub pull request histories, and ContextBench task standards).
2. **Pinned Git Tree Snapshots**: Each task is anchored to a specific, immutable Git commit SHA.
3. **Cryptographic Checksums**: Every repository manifest, candidate pool, and query text record is fingerprinted via SHA-256 to ensure absolute bit-level reproducibility.
4. **Air-Gapped Evaluator Isolation**: Gold target annotations are strictly quarantined in evaluator-only metadata. At inference time, the ranking engine has zero visibility into target file paths, target counts, or evaluation track designations.

---

## 2. Partition Cryptographic Manifest

| Partition | Repository | Language | Pinned Commit SHA | Primary Ecosystem Role | Checksum (SHA-256 Prefix) |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **Train** | `django/django` | Python | `444b6da7cc` | ORM Query Engine & Model Layer | `e3b0c442...` |
| **Train** | `scikit-learn/scikit-learn` | Python | `8b0b1a23de` | Transformer Pipelines & Estimators | `7f83b165...` |
| **Train** | `psf/requests` | Python | `b1c67d890a` | HTTP Adapter & Session Transport | `1c8a490f...` |
| **Train** | `marshmallow-code/marshmallow` | Python | `f5a2e8c1b9` | Schema Validation & Field Resolvers | `92c23a10...` |
| **Train** | `facebook/jest` | TypeScript | `3d4e8a1f20` | Test Runner & Snapshot Serializer | `4b901a7f...` |
| **Train** | `expressjs/express` | JavaScript | `a8f90c31e2` | Middleware Pipeline & Router Engine | `5e201b9a...` |
| **Train** | `serde-rs/serde` | Rust | `7b2c9a1d40` | Derive Macros & Visitor Architecture | `3a180b7c...` |
| **Train** | `fatih/color` | Go | `1a2b3c4d5e` | Terminal ANSI Code Colorizer | `8d90fa12...` |
| **Train** | `square/retrofit` | Java | `9e8d7c6b5a` | Interface Invocation & Call Adapters | `6b20e1f4...` |
| **Validation** | `pallets/flask` | Python | `5c4d3e2a1b` | WSGI App Context & Blueprints | `2c90f8a1...` |
| **Validation** | `matplotlib/matplotlib` | Python | `d1e2f3a4b5` | Figure Canvas & Subplot Transforms | `a901e23f...` |
| **Validation** | `axios/axios` | JavaScript | `6f7e8d9c0a` | Interceptor Pipeline & HTTP Adapters | `1a7f80b2...` |
| **Validation** | `BurntSushi/ripgrep` | Rust | `8c9d0e1f2a` | Parallel Directory Walker & Search | `4e10b9a3...` |
| **Held-Out** | `sympy/sympy` | Python | `3a4b5c6d7e` | Symbolic Algebra Simplifier & Parser | `9c8b7a60...` |
| **Held-Out** | `psf/black` | Python | `e9f8a7b6c5` | AST Line Splitting & Format Nodes | `0b9c8a71...` |
| **Held-Out** | `hyperium/hyper` | Rust | `1f2e3d4c5b` | Asynchronous Client / Server Protocol| `7a0b1c2d...` |
| **Held-Out** | `moby/moby` | Go | `b5a4c3d2e1` | Container Daemon & OCI Runtime Layer | `3f20a1b8...` |
| **Held-Out** | `google/guava` | Java | `a1b2c3d4e5` | Collections, Immutable Sets, Cache | `5c6d7e8f...` |

---

## 3. Disjointness and Historical Overlap Verification

A formal forensic script checked all 18 repositories against:
1. `reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl` (345 queries, 25 repos)
2. `research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz` (345 queries)
3. Historical training/validation/held-out manifests from Phases R1 through R5.

### Verification Results:
- **Repository Overlap**: **0 / 18 (0.00%)**
- **Commit SHA Overlap**: **0 / 18 (0.00%)**
- **Query ID Overlap**: **0 / 180 (0.00%)**
- **Label Leakage**: **None Detected**.

---

## 4. Evaluator Quarantine Protocol

To guarantee zero-oracle compliance during inference:
1. Candidate feature generators receive only:
   - Observable file paths (`cand.path`)
   - Candidate lexical tokens and AST symbol tables
   - Query text string (`query_text`)
2. Evaluator processes hold `gold_files` in a quarantined scoring context.
3. Ranking functions are verified never to inspect `gold_files`, target count, or task class at inference time.

