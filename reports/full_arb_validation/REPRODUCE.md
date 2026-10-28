# Reproduction Guide

```bash
# 1. Download official ARB v2 releases
python scripts/download_and_extract_arb_v2.py

# 2. Run full 427-sample evaluation
python benchmarks/run_complete_arb_evaluation.py

# 3. Run regression tests
pytest -v
```
