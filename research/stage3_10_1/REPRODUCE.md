# RepoNeedle Stage 3.10.1: Reproduction Instructions

This guide provides exact commands to independently reproduce the Stage 3.10.1 reconciliation datasets, verify all statistical tests, and run the metric validation test suite.

## 1. Environment & Setup

Ensure the workspace is on branch `research-program` and required dependencies are installed:

```bash
git checkout research-program
pip install pytest scipy numpy
```

## 2. Verify Frozen Tags

Confirm that both immutable tags remain unchanged:

```bash
git rev-parse "v0.1.0-baseline^{commit}"
# Output must be: 8e0042553a14b6e3c6cf5b35823c4da84181a8e9

git rev-parse "stage3-candidate-freeze^{commit}"
# Output must be: cd7f3b01e28695f9a9357e0815069e0eae85baca
```

## 3. Run the Metric Validation Suite

Execute the hand-checkable metric validation unit tests:

```bash
pytest tests/test_stage3_10_1_metric_validation.py -v
```

All 6 tests must pass.

## 4. Run the Full Regression Suite

Execute the entire repository test suite (149 tests):

```bash
pytest
```

## 5. Re-generate Canonical Reconciliation Datasets

To re-generate all reconciliation CSVs and re-run the 10,000-replicate bootstrap statistical analyses:

```bash
python research/stage3_10_1/generate_reconciliation_artifacts.py
```

This updates:
- `research/stage3_10_1/CANONICAL_PER_QUERY_RESULTS.csv`
- `research/stage3_10_1/CANONICAL_PER_TASK_RESULTS.csv`
- `research/stage3_10_1/CANONICAL_PER_REPOSITORY_RESULTS.csv`
- `research/stage3_10_1/REPRODUCTION_MATRIX.csv`
- `research/stage3_10_1/statistical_tests.json`
