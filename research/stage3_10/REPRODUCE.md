# REPONEEDLE STAGE 3.10: EXACT REPRODUCTION GUIDE

This guide provides instructions to reproduce all Stage 3.10 canonical results, evaluator audits, statistical tests, and performance benchmarks.

---

## 1. PRE-FLIGHT ENVIRONMENT & WORKSPACE CHECK

Verify the repository state and frozen baseline tags:
```bash
git checkout research-program
git rev-parse HEAD
# Ensure tags are intact:
git tag -l -n1
# Expected tags:
#   v0.1.0-baseline
#   stage3-candidate-freeze
```

---

## 2. REPRODUCING THE OFFICIAL ARB EVALUATOR AUDIT

To inspect the upstream ARB repository revision and verify the deterministic RepoMap PR #3 commit:
```bash
cd external/agent-retrieval-bench
git rev-parse HEAD
# Expected: 9e4d68937f29d5967afd62f4f6a24c1478298133
git log -1 f0cc9be --oneline
# Expected: f0cc9be Prevent hash-seed drift in RepoMap evaluation (#3)
```

Run the official evaluation audit report generator:
```bash
python research/stage3_10/ARB_EVALUATOR_AUDIT.md
```

---

## 3. REPRODUCING THE CANONICAL COMPARISON & STATISTICAL TESTS

Run the unified Stage 3.10 canonical benchmark generator:
```bash
python research/stage3_10/generate_canonical_results.py
```
Outputs produced:
- `research/stage3_10/CANONICAL_RESULTS.csv` (7 systems $	imes$ full metric suite)
- `research/stage3_10/PER_QUERY_RESULTS.csv` (345 queries $	imes$ 7 systems)
- `research/stage3_10/PER_TASK_RESULTS.csv` (4-track breakdown)
- `research/stage3_10/PER_REPOSITORY_RESULTS.csv` (25-repository breakdown)
- `research/stage3_10/PAIRED_STATISTICAL_TESTS.csv` (Holm's step-down multiplicity correction and bootstrap CIs)

---

## 4. REPRODUCING CODE LEAKAGE AUDIT

To scan the codebase for hardcoded benchmark strings or synthetic shortcuts:
```bash
python research/stage3_10/run_leakage_audit.py
```
Output:
- `research/stage3_10/LEAKAGE_AND_SPECIAL_CASE_AUDIT.md` (0 hits verified)

---

## 5. REPRODUCING RUNTIME & MEMORY PROFILING

To profile process RSS via Windows PSAPI and query latency percentiles across small, medium, and large repositories:
```bash
python research/stage3_9/audit_runtime_and_memory.py
```
Output produced:
- `research/stage3_10/RUNTIME_MEMORY_RESULTS.csv`

---

## 6. RUNNING UNIT & REGRESSION TESTS

Execute the full pytest suite:
```bash
python -m pytest tests/ -v
```
All 71 tests must pass.
