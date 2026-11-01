# RepoNeedle V1.0.0 — Milestone 2 Failure Forensics Report

**Scope**: Forensic analysis of all gold targets ranked beyond position 50 in Milestone 1.  
**Total Missed Targets (M1 Rank > 50)**: 121 targets across 99 unique queries.  
**Objective**: Characterize root causes of lexical outranking and verify structural resolution in M2.

---

## 1. Failure Taxonomy & Root Cause Distribution

| Failure Category | Missed Target Count | Fraction of Misses | Primary Mechanism |
| :--- | :---: | :---: | :--- |
| **A. Test-file distractors** | 25 | 20.7% | Test suites share identifiers with implementation and outrank targets. |
| **B. Sibling implementation distractors** | 19 | 15.7% | Files in same package/module share common vocabulary and type signatures. |
| **C. Traceback caller-frame distractors** | 1 | 0.8% | Outer test harness frames outrank the innermost faulty function frame. |
| **D. Generic utility and hub distractors** | 18 | 14.9% | Highly imported central files (`utils`, `types`, `mod.rs`) accumulate BM25 scores. |
| **E. Documentation distractors** | 0 | 0.0% | Readmes and doc files match multi-term natural language queries. |
| **F. Build-manifest distractors** | 0 | 0.0% | Build files (`Cargo.toml`, `package.json`) match dependency names. |
| **G. Missing structural evidence** | 5 | 4.1% | Target is an indirect ripple dependent with zero lexical overlap with query. |
| **H. Incorrect query-intent interpretation** | 17 | 14.0% | Natural language intent terms ("test", "bug") misdirected ranking. |
| **I. Unexplained failures** | 36 | 29.8% | Wide lexical dispersion without dominant pattern. |
| **Total** | **121** | **100.0%** | |

---

## 2. Recovery and Movement in Milestone 2

Across the 121 previously missed targets:
- Targets successfully elevated into **Top-20** by M2: **3** (2.5%)
- Targets successfully elevated into **Top-50** by M2: **12** (9.9%)
- Average rank improvement (Delta rank): **-53.7 positions**

---

## 3. Sample Case Forensics (Representative Failures)

### Query `33c92549` (clap-rs/clap @ `v2_edit2ripple`)
- **Gold Target**: `clap_builder/src/util/mod.rs`
- **Movement**: Rank 326 -> **Rank 440** (Delta = -114)
- **Classification**: **D. Generic utility and hub distractors**
- **Forensic Diagnosis**: Central hub file 'clap_builder/src/error/mod.rs' with generic symbol overlap outranked target.
- **Top Distractor (M1)**: `clap_builder/src/error/format.rs`

### Query `269e3e34` (clap-rs/clap @ `v2_edit2ripple`)
- **Gold Target**: `clap_builder/src/util/mod.rs`
- **Movement**: Rank 304 -> **Rank 442** (Delta = -138)
- **Classification**: **G. Missing structural evidence**
- **Forensic Diagnosis**: Indirect dependency relationship lacked explicit lexical overlap in query.
- **Top Distractor (M1)**: `clap_builder/src/output/help_template.rs`

### Query `6b1c1cff` (clap-rs/clap @ `v2_code2test`)
- **Gold Target**: `tests/builder/ignore_errors.rs`
- **Movement**: Rank 69 -> **Rank 70** (Delta = -1)
- **Classification**: **I. Unexplained failures**
- **Forensic Diagnosis**: Diffused lexical and structural scoring.
- **Top Distractor (M1)**: `clap_builder/src/parser/parser.rs`

### Query `30fded9a` (clap-rs/clap @ `v2_edit2ripple`)
- **Gold Target**: `clap_mangen/Cargo.toml`
- **Movement**: Rank 224 -> **Rank 173** (Delta = +51)
- **Classification**: **A. Test-file distractors**
- **Forensic Diagnosis**: Top distractors ['clap_mangen/src/render.rs', 'clap_builder/src/builder/arg.rs'] are test files outranking implementation target.
- **Top Distractor (M1)**: `clap_mangen/src/render.rs`

### Query `30fded9a` (clap-rs/clap @ `v2_edit2ripple`)
- **Gold Target**: `clap_mangen/tests/testsuite/common.rs`
- **Movement**: Rank 54 -> **Rank 123** (Delta = -69)
- **Classification**: **H. Incorrect query-intent interpretation**
- **Forensic Diagnosis**: Query intent markers collided with code identifiers.
- **Top Distractor (M1)**: `clap_mangen/src/render.rs`

### Query `41deac7d` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target**: `cache/demux_test.go`
- **Movement**: Rank 61 -> **Rank 63** (Delta = -2)
- **Classification**: **B. Sibling implementation distractors**
- **Forensic Diagnosis**: Sibling file 'cache/cache.go' in same directory absorbed lexical match.
- **Top Distractor (M1)**: `cache/cache.go`

### Query `7d5c2788` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target**: `cache/demux_test.go`
- **Movement**: Rank 69 -> **Rank 62** (Delta = +7)
- **Classification**: **B. Sibling implementation distractors**
- **Forensic Diagnosis**: Sibling file 'cache/cache.go' in same directory absorbed lexical match.
- **Top Distractor (M1)**: `cache/cache.go`

### Query `fa3c694a` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target**: `cache/demux_test.go`
- **Movement**: Rank 118 -> **Rank 260** (Delta = -142)
- **Classification**: **B. Sibling implementation distractors**
- **Forensic Diagnosis**: Sibling file 'cache/cache_test.go' in same directory absorbed lexical match.
- **Top Distractor (M1)**: `tests/integration/cache_test.go`

### Query `15959167` (etcd-io/etcd @ `v2_code2test`)
- **Gold Target**: `cache/demux_test.go`
- **Movement**: Rank 117 -> **Rank 119** (Delta = -2)
- **Classification**: **B. Sibling implementation distractors**
- **Forensic Diagnosis**: Sibling file 'cache/config.go' in same directory absorbed lexical match.
- **Top Distractor (M1)**: `cache/config.go`

### Query `1dd2bdfd` (etcd-io/etcd @ `v2_code2test`)
- **Gold Target**: `server/etcdserver/txn/txn_test.go`
- **Movement**: Rank 162 -> **Rank 227** (Delta = -65)
- **Classification**: **D. Generic utility and hub distractors**
- **Forensic Diagnosis**: Central hub file 'server/storage/mvcc/index.go' with generic symbol overlap outranked target.
- **Top Distractor (M1)**: `server/storage/mvcc/index.go`

### Query `d5f1198f` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target**: `server/etcdserver/txn/txn_test.go`
- **Movement**: Rank 147 -> **Rank 159** (Delta = -12)
- **Classification**: **D. Generic utility and hub distractors**
- **Forensic Diagnosis**: Central hub file 'tests/robustness/model/types.go' with generic symbol overlap outranked target.
- **Top Distractor (M1)**: `server/storage/mvcc/kv.go`

### Query `d5f1198f` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target**: `server/storage/mvcc/index_test.go`
- **Movement**: Rank 182 -> **Rank 206** (Delta = -24)
- **Classification**: **B. Sibling implementation distractors**
- **Forensic Diagnosis**: Sibling file 'server/storage/mvcc/kv.go' in same directory absorbed lexical match.
- **Top Distractor (M1)**: `server/storage/mvcc/kv.go`

### Query `e45d17f0` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target**: `cache/demux_test.go`
- **Movement**: Rank 53 -> **Rank 60** (Delta = -7)
- **Classification**: **B. Sibling implementation distractors**
- **Forensic Diagnosis**: Sibling file 'cache/cache.go' in same directory absorbed lexical match.
- **Top Distractor (M1)**: `cache/cache.go`

### Query `3a9ae9c1` (etcd-io/etcd @ `v2_code2test`)
- **Gold Target**: `clientv3/integration/kv_test.go`
- **Movement**: Rank 158 -> **Rank 147** (Delta = +11)
- **Classification**: **I. Unexplained failures**
- **Forensic Diagnosis**: Diffused lexical and structural scoring.
- **Top Distractor (M1)**: `proxy/grpcproxy/watch.go`

### Query `3a9ae9c1` (etcd-io/etcd @ `v2_code2test`)
- **Gold Target**: `clientv3/integration/lease_test.go`
- **Movement**: Rank 63 -> **Rank 64** (Delta = -1)
- **Classification**: **I. Unexplained failures**
- **Forensic Diagnosis**: Diffused lexical and structural scoring.
- **Top Distractor (M1)**: `proxy/grpcproxy/watch.go`

