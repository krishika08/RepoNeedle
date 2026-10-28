# REPONEEDLE STAGE 3.11: EXACT REPRODUCTION GUIDE

This guide allows an independent auditor to reproduce all Stage 3.11 audit artifacts, cross-stage reconciliations, recomputed metrics, and statistical corrections.

---

## 1. PRE-FLIGHT VERIFICATION
```bash
git checkout research-program
git rev-parse HEAD
# Verify immutable frozen tags:
git rev-parse "v0.1.0-baseline^{commit}"
# Expected: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9
git rev-parse "stage3-candidate-freeze^{commit}"
# Expected: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

---

## 2. REPRODUCE FULL AUDIT & DATA RECOMPUTATION
```bash
python research/stage3_11/run_stage3_11_audit.py
```
This produces:
- `research/stage3_11/QUERY_ALIGNMENT_AUDIT.csv`
- `research/stage3_11/RECOMPUTED_CANONICAL_RESULTS.csv`
- `research/stage3_11/CROSS_STAGE_RECONCILIATION.csv`
- `research/stage3_11/STATISTICAL_RECOMPUTATION.csv`
- `research/stage3_11/LEAKAGE_CLAIM_AUDIT.md`
- `research/stage3_11/RUNTIME_CLAIM_AUDIT.md`
- `research/stage3_11/STAGE3_11_AUDIT_REPORT.md`

---

## 3. EXECUTE INTEGRITY TEST SUITE
```bash
python -m pytest tests/test_stage3_11_integrity.py -v
```
All tests must pass.
