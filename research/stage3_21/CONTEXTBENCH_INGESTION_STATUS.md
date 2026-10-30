# Official ContextBench Ingestion Status & Validation Gate Assessment

**Date:** 2026-10-30  
**Stage:** 3.21  
**Experiment ID:** `EXP-321-06`  
**Independent Validation Gate Status:** **`BLOCKED — OFFICIAL DATA ACQUISITION`**  

---

## 1. Executive Summary

RepoNeedle's independent external validation gate requires evaluation against the official ContextBench dataset (`EuniAI/ContextBench`, revision `c285579`).
In Phase 6, network reachability was tested to assess whether automated acquisition could proceed. The local sandbox environment maintains strict egress network policies that prevent direct socket connections to Hugging Face Hub (`https://huggingface.co`).

In accordance with Stage 3.21 Governing Rules:
- **Rule 3:** Do not tune ARM-101 against the external validation set.
- **Rule 4:** ARB v2 is a development/regression benchmark, not independent evidence of generalization.
- **Rule 8:** Never bypass network restrictions or fabricate an official benchmark dataset.

The independent validation gate remains explicitly and truthfully marked **`BLOCKED — OFFICIAL DATA ACQUISITION`**.

---

## 2. Ingestion Specification for Out-of-Band Transfer

An authoritative, cryptographically verified ingestion utility has been deployed at [research/stage3_21/ingest_contextbench.py](file:///F:/RepoNeedle/research/stage3_21/ingest_contextbench.py). When a human operator or authorized transfer pipeline delivers the artifacts, the script validates them against published cryptographic checksums:

### Required Upstream Artifacts (Pinned Revision `c285579`)

1. **Full Dataset (`full.parquet`):**
   - **Source:** `https://huggingface.co/datasets/Contextbench/ContextBench/resolve/c285579/data/full.parquet`
   - **Target Destination:** `research/external_data/contextbench/full.parquet`
   - **Expected Byte Size:** `26,102,607` bytes
   - **Expected SHA-256 Checksum:** `2f56535bdc73eb8a68bf4ebb49789d8e9cd4f219ea60df6290b85278aee61ca8`
   - **Expected Row Count:** 1,136 rows across 66 repositories and 8 programming languages.
   - **Purpose:** Full uncurated corpus context benchmarking.

2. **Verified Benchmark Subset (`contextbench_verified.parquet`):**
   - **Source:** `https://huggingface.co/datasets/Contextbench/ContextBench/resolve/c285579/data/contextbench_verified.parquet`
   - **Target Destination:** `research/external_data/contextbench/contextbench_verified.parquet`
   - **Expected Byte Size:** `9,558,250` bytes
   - **Expected SHA-256 Checksum:** `e9dcfd504cbfb849ac815a79040c793d0d92f94eecc9b5a4ee3e1445a2f8a791`
   - **Expected Row Count:** 500 human-verified benchmark instances across 35 repositories.
   - **Purpose:** Primary evaluation gate for independent cross-corpus generalization.

---

## 3. Strict Scientific Safeguards

1. **Separation of Full Corpus and Verified Subset:**
   The full dataset and verified subset serve distinct scientific purposes. The verified subset must never be used for exploratory parameter tuning or heuristic calibration.
2. **Prohibition of Unofficial Mirrors:**
   Third-party mirrors (such as `schwerli/contextbench`) have different row counts, modified task definitions, and altered ground truth, and are strictly prohibited.
3. **No Synthetic Proxies:**
   No mock data, synthetic benchmarks, or modified ARB queries may be substituted for official ContextBench data.
