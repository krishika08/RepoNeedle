# RepoNeedle Stage 3.20 — Baseline State & Starting Inventory

**Date:** 2026-10-30  
**Workspace:** `F:\RepoNeedle`  
**Branch:** `research-program`  
**Starting Commit:** `89a3ef4cd5c6854884bf8e4578f45577636bbbc7` (Stage 3.19)  
**Status:** PRISTINE & VERIFIED  

---

## 1. Protected Baseline References

| Reference | Target Commit SHA | Status |
| :--- | :--- | :--- |
| `HEAD` | `89a3ef4cd5c6854884bf8e4578f45577636bbbc7` | **VERIFIED MATCH** |
| `v0.1.0-baseline^{commit}` | `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` | **IMMUTABLE — VERIFIED** |
| `stage3-candidate-freeze^{commit}` | `cd7f3b01e28695f9a9357e0815069e0eae85baca` | **IMMUTABLE — VERIFIED** |

---

## 2. Test Suite Baseline

Prior to making any modifications, the entire existing test suite was executed:
- **Total Test Cases:** 220 tests across 28 test suites
- **Result:** **220 PASSED, 0 FAILED** in 8.03s
- **Working Tree:** Clean (`git status --porcelain` empty)

---

## 3. Cryptographic Hashes of Key Starting Artifacts

The SHA-256 hashes of critical source and research artifacts were recorded in [research/stage3_20/STARTING_SOURCE_HASHES.json](file:///F:/RepoNeedle/research/stage3_20/STARTING_SOURCE_HASHES.json):

| Artifact Path | Size (Bytes) | SHA-256 Checksum |
| :--- | :---: | :--- |
| `reponeedle/engine.py` | 17,998 | `4ebf15bc5c13e6cf1e4a1a0f8bfd925e01b3a32501a354bbba38b1f7f1857c5a` |
| `reponeedle/models.py` | 7,126 | `ce90f4e2402dd17ec9353915112fc751a086a9f46405788e0a37943564e9a4f4` |
| `reponeedle/cli.py` | 2,741 | `4359d997a38b1054238e8da6fb1b948f98a2eb24e4d564fa7e88fc8ee5fc6522` |
| `reponeedle/core/lexical.py` | 18,367 | `a85ea8dff91dc83a7491cf19597ffdd30f5ecb8be2ef7f766e4aee7848651c6c` |
| `reponeedle/core/cascade.py` | 11,811 | `1686df0fe9745e9ee20fe1bc00e1236113db1b6bc9321c7a82ec56e2c39e240c` |
| `reponeedle/core/graph.py` | 13,832 | `96aa19d4586d63d6f30e6a13d7a82204c3cf7b2d5f07df529c2ea2dd6e23635a` |
| `research/stage3_14/pilot_attenuation.py` | 14,022 | `b299e9dc019dcdd5287f7943d03cebfa4a3407e33555543c8d19d671fc06a146` |
| `research/stage3_11/function_graph_engine.py` | 22,238 | `e5a40bf597a7e8e6bb27f275a5939ca6c4ea21c7d3126ec86bebe33bbd1bf1e7` |
| `research/stage3_19/REPRODUCED_LEADERBOARD.csv` | 1,502 | `00a653c0e3a51f044bb4d2847a9643d92036496924b17bc6719b46ecfe53fb69` |
| `research/stage3_19/PER_QUERY_RESULTS.csv` | 71,307 | `4c8d5500e572e8111cf74e892c90c7490217ecfe093b12369fc6368d54d19330` |
