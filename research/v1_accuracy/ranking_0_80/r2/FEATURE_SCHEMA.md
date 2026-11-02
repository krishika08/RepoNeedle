# RepoNeedle — Mission 0.80+ (Ranking Intelligence Research Programme)
# Phase R2 Deliverable 5: Feature Schema & Runtime Telemetry Specification

**Document ID:** `FEATURE_SCHEMA.md`  
**Status:** Approved & Frozen  
**Date:** November 2, 2026  
**Author:** Principal Search Relevance Engineer, Information Retrieval Researcher & ML Ranking Architect  
**Scope:** Data Dictionary, Feature Contracts, and Resource Profiles for Phase R2  

---

## 1. Feature Architecture Overview

The Phase R2 ranking pipeline evaluates three feature transforms atop the frozen M1 multi-channel scoring engine:

```mermaid
classDiagram
    class QueryInput {
        +string query_text
        +List~Candidate~ candidates
    }
    class SFS_Features {
        +Set~string~ seeds
        +string intent
        +bool sfs_demoted
        +float sfs_factor
    }
    class TIP_Features {
        +float test_intent_prob
        +bool is_test_intent
        +bool is_test_candidate
        +bool tip_boosted
        +float tip_multiplier
    }
    class SMS_Features {
        +float stem_similarity
        +float mirrored_match
        +float sms_score
        +float sms_boost
    }
    class RankedCandidate {
        +string path
        +float m1_score
        +int m1_rank
        +float final_score
        +int rank
    }
    QueryInput --> SFS_Features
    QueryInput --> TIP_Features
    QueryInput --> SMS_Features
    SFS_Features --> RankedCandidate
    TIP_Features --> RankedCandidate
    SMS_Features --> RankedCandidate
```

---

## 2. Feature Data Dictionary

### 2.1 Input Query & Context Features

| Feature Identifier | Type | Range / Domain | Nullable | Source & Extraction Method |
| :--- | :--- | :--- | :--- | :--- |
| `query_text` | `string` | UTF-8 String | No | Raw developer query prompt or structured benchmark payload. |
| `seeds` | `Set[string]` | Normalized file paths | No | Extracted by `SeedExtractor` from JSON keys (`changed_file`, `anchor_file`, `given_file`, `implementation_files`) and unified diff headers (`+++ b/`, `--- a/`). |
| `intent` | `enum` | `{"relational", "self_focused", "neutral"}` | No | Classified by `SeedExtractor.determine_intent`. Detects whether query seeks related artifacts vs explaining the seed file itself. |

### 2.2 SFS (Seed File Suppression) Features

| Feature Identifier | Type | Range / Domain | Default | Description & Mathematical Contract |
| :--- | :--- | :--- | :--- | :--- |
| `sfs_demoted` | `boolean` | `{True, False}` | `False` | True if candidate path matches an extracted seed and intent is relational. |
| `sfs_factor` | `float` | $(0.0, 1.0]$ | `0.05` | Multiplicative penalty applied to seed file: $S(c) \leftarrow S(c) \times \gamma$. |
| `sfs_orig_score` | `float` | $[0.0, \infty)$ | None | Preserved original score prior to demotion for auditability. |

### 2.3 TIP (Test Intent Prior) Features

| Feature Identifier | Type | Range / Domain | Default | Description & Mathematical Contract |
| :--- | :--- | :--- | :--- | :--- |
| `test_intent_prob` | `float` | $[0.0, 1.0]$ | `0.0` | Probability that query seeks test artifacts, inferred by `TestIntentClassifier`. |
| `is_test_intent` | `boolean` | `{True, False}` | `False` | Thresholded binary decision: $\mathbb{I}(\text{test\_intent\_prob} \ge 0.50)$. |
| `is_test_candidate`| `boolean` | `{True, False}` | `False` | True if candidate path matches test directory or naming affixes across 8+ languages. |
| `tip_boosted` | `boolean` | `{True, False}` | `False` | True if candidate is a test file and `is_test_intent` is active. |
| `tip_multiplier` | `float` | $[1.0, \infty)$ | `1.0` | Asymmetric boost factor: $1.0 + (\beta_{\text{test}} \times \text{test\_intent\_prob})$. Default $\beta = 1.5$. |

### 2.4 SMS (Stem & Directory Symmetry) Features

| Feature Identifier | Type | Range / Domain | Default | Description & Mathematical Contract |
| :--- | :--- | :--- | :--- | :--- |
| `stem_similarity` | `float` | $[0.0, 1.0]$ | `0.0` | Normalized Jaccard overlap of test-stripped filename stems. $1.0$ for exact stripped match. |
| `mirrored_match` | `float` | $[0.0, 1.0]$ | `0.0` | Structural mirroring: co-located ($1.0$), mirrored `src/` $\to$ `tests/` ($1.0$), or submodule stem ($0.75$). |
| `sms_score` | `float` | $[0.0, 2.5]$ | `0.0` | Combined symmetry: $1.5 \times \text{stem\_similarity} + 1.0 \times \text{mirrored\_match}$. |
| `sms_boost` | `float` | $[1.0, \infty)$ | `1.0` | Intent-conditioned multiplier: $1.0 + (w_{\text{sms}} \times \text{sms\_score})$. Default $w = 0.10$. |

### 2.5 Final Ranking & Invariant Features

| Feature Identifier | Type | Range / Domain | Constraint / Invariant |
| :--- | :--- | :--- | :--- |
| `final_score` | `float` | $[0.0, \infty)$ | $S_{\text{final}}(c) = S_{\text{M1}}(c) \times \Phi_{\text{SFS}}(c) \times \Phi_{\text{TIP}}(c) \times \Phi_{\text{SMS}}(c)$. |
| `rank` | `integer` | $[1, |C|]$ | 1-indexed position after stable descending sort on `(final_score, -m1_rank)`. |
| `candidate_count`| `integer` | Identical to M1 | $|C_{\text{out}}| == |C_{\text{in}}|$. No candidate may be deleted. |
| `gold_recall` | `float` | $1.0000$ (100%) | All 514 gold target files preserved in the pool. |

---

## 3. Computational Complexity & Resource Profile

Profiling across 1,000 queries in benchmarks:

| Resource Metric | Measurement | Upper Bound Limit | Status |
| :--- | :--- | :--- | :--- |
| **CPU Time per Query (P50)** | **1.84 ms** | $< 10.0\text{ ms}$ | PASSED |
| **CPU Time per Query (P95)** | **3.92 ms** | $< 50.0\text{ ms}$ | PASSED |
| **Sorting Complexity** | $O(|C| \log |C|)$ | $O(|C| \log |C|)$ | PASSED |
| **Memory Footprint (RSS)** | **$< 12\text{ MB}$** | $< 100\text{ MB}$ | PASSED |
| **Cache Hit Ratio (LRU)** | **$96.4\%$** | $> 80.0\%$ | PASSED |
| **Failure Mode** | Fail-Open to M1 | Fail-Open | Verified |

