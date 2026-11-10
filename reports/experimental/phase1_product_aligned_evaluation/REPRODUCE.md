# Reproducing the Supplemental Product-Aligned Evaluation

Requirements: this repository, the Agent Retrieval Bench checkout at `external/agent-retrieval-bench` (with `data/corpus/v2_selective_mixed` and the `v2_*` benchmark splits), Python 3.10+, and the package dependencies. About 7 GB of free RAM is recommended for 4 shards.

```bash
# 1. Evaluate (4 resumable shards; each skips queries already written)
python benchmarks/run_arb_product_aligned_eval.py --shard 0 --num-shards 4
python benchmarks/run_arb_product_aligned_eval.py --shard 1 --num-shards 4
python benchmarks/run_arb_product_aligned_eval.py --shard 2 --num-shards 4
python benchmarks/run_arb_product_aligned_eval.py --shard 3 --num-shards 4

# 2. Merge: writes aggregate.json, confidence_intervals.json, fidelity.json, run_metadata.json
python benchmarks/run_arb_product_aligned_eval.py --merge

# 3. Determinism: re-runs the first N snapshots in a temporary directory and compares
python benchmarks/run_arb_product_aligned_eval.py --check-determinism 6

# 4. Tables used by REPORT.md
python benchmarks/render_product_aligned_tables.py

# 5. Unit tests for the evaluator's protocol helpers
python -m pytest tests/test_product_aligned_eval.py -q
```

Notes:
- The protocol (retrieval unit, representations, tie rule, chunk-to-file rule, bootstrap settings) is fixed in the script's `CONFIG` and written to `config.json` on first run.
- The merge step cross-checks against `reports/arb_v2_current_engine/` (official sequence), `reports/full_arb_validation/` (historical BM25), and `reports/experimental/phase0_evaluator_audit/` (Phase 0), all read-only.
- The bootstrap is deterministic (seed 20261109); re-running `--merge` reproduces the confidence intervals exactly.
- Run 2026-11-09 with 4 concurrent shards. Wall time was about 55 minutes on a 16 GB, 18-thread Windows machine.
