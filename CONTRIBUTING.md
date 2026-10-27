# Contributing to RepoNeedle

We welcome contributions from the retrieval, software engineering, and AI agent communities!

## Core Principles
1. **Scientific Rigor & Honest Metrics**: Never claim superiority without empirical, reproducible evidence.
2. **Strict License Compliance**: Only permissively licensed code (MIT, Apache-2.0, BSD) may be used. Never introduce CC BY-NC or copyleft restricted materials.
3. **Reproducibility**: All benchmark figures must correspond to deterministic, reproducible benchmark scripts.

## Development Setup

1. Clone repository:
   ```bash
   git clone https://github.com/RepoNeedle/RepoNeedle.git
   cd RepoNeedle
   ```

2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Run test suite:
   ```bash
   pytest -v
   ```

4. Execute benchmark suite:
   ```bash
   python scripts/run_benchmarks.py
   ```

## Code Quality Standards
- Write unit tests for any new router, graph algorithm, or tokenizer feature.
- Maintain typing annotations.
- Keep dependencies lightweight (pure standard ML stack: `numpy`, `scipy`, `networkx`, `pydantic`).
