# REPRODUCIBILITY INSTRUCTIONS: REPONEEDLE RESEARCH PIPELINE

**Document ID**: `RI-2026-001`  
**Version**: 1.0.0  
**Date**: 2026-10-28  
**Author**: Principal Retrieval Researcher & Lead Systems Engineer  

---

## 1. Environment Specification

- **Python Runtime**: Python `3.10` to `3.12` (audited on `3.12.10` 64-bit AMD64).
- **Core Dependencies**: `numpy>=1.24.0`, `scipy>=1.10.0`, `networkx>=3.0`, `pydantic>=2.0.0`, `pathspec>=0.11.0`, `rich>=13.0.0`.
- **Optional Accelerators**: `numba>=0.60.0`, `onnxruntime>=1.19.0`.
- **Operating Systems**: Tested on Windows 11, Ubuntu 22.04 LTS, macOS Sonoma.

---

## 2. Quick Setup & Installation

```bash
# Clone the repository
git clone https://github.com/RepoNeedle/RepoNeedle.git
cd RepoNeedle

# Switch to the research branch
git checkout research-program

# Install RepoNeedle in editable development mode
pip install -e ".[dev]"
```

---

## 3. Verifying the Baseline Benchmark ($N=427$)

To independently verify the audited baseline metrics without re-running the full multi-hour benchmark evaluation:

```bash
# Run the diagnostic baseline calculation directly from saved raw predictions
python -c "
import json

with open('reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl', 'r', encoding='utf-8') as f:
    pos = [json.loads(line) for line in f]

with open('reports/full_arb_validation/checkpoint_selective.jsonl', 'r', encoding='utf-8') as f:
    sel = [json.loads(line) for line in f]

mean = lambda xs: sum(xs) / len(xs)

print('Positive Samples Evaluated:', len(pos))
print('RepoNeedle MRR:          ', f'{mean([r[\"reponeedle\"][\"mrr\"] for r in pos]):.4f}')
print('RepoMap MRR:             ', f'{mean([r[\"repomap\"][\"mrr\"] for r in pos]):.4f}')
print('BM25 MRR:                ', f'{mean([r[\"bm25\"][\"mrr\"] for r in pos]):.4f}')
print('RepoNeedle Recall@20:    ', f'{mean([r[\"reponeedle\"][\"recall@20\"] for r in pos]):.4f}')
print('RepoMap Recall@20:       ', f'{mean([r[\"repomap\"][\"recall@20\"] for r in pos]):.4f}')
print('RepoNeedle BCY@4k:       ', f'{mean([r[\"reponeedle\"][\"bcy@4k\"] for r in pos]):.4f}')
print('RepoNeedle BCY@8k:       ', f'{mean([r[\"reponeedle\"][\"bcy@8k\"] for r in pos]):.4f}')
print('RepoMap BCY@8k:          ', f'{mean([r[\"repomap\"][\"bcy@8k\"] for r in pos]):.4f}')

c2t = [r for r in pos if r['task_type'] == 'code2test']
print('code2test RepoNeedle MRR:', f'{mean([r[\"reponeedle\"][\"mrr\"] for r in c2t]):.4f}')

c2c = [r for r in pos if r['task_type'] == 'comment2context']
print('comment2context RN MRR:  ', f'{mean([r[\"reponeedle\"][\"mrr\"] for r in c2c]):.4f}')
print('comment2context BM25 MRR:', f'{mean([r[\"bm25\"][\"mrr\"] for r in c2c]):.4f}')

abstained = sum(1 for r in sel if r.get('abstained') is True)
print(f'Selective Abstentions:    {abstained} / {len(sel)} (0.0%)')
"
```

---

## 4. Running Regression Tests

Execute the 34-test regression and robustness suite:

```bash
pytest -v
```

Expected output:
```
============================= 34 passed in ~2.8s =============================
```

---

## 5. Building Clean Distribution Packages

```bash
python -m build --no-isolation
twine check dist/*
```

---

## 6. Registering a New Experiment

When running an experiment in `research/`:
1. Assign an experiment ID (e.g. `EXP-001`, `EXP-002`).
2. Record Git commit SHA and parameter settings.
3. Save per-sample predictions to `research/experiments/<exp_id>/predictions.jsonl`.
4. Append aggregate results and statistical significance tests to [`research/EXPERIMENT_REGISTRY.jsonl`](file:///F:/RepoNeedle/research/EXPERIMENT_REGISTRY.jsonl).

