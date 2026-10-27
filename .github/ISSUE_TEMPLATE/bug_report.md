---
name: Bug Report
about: Create a report to help us improve RepoNeedle.
title: "[BUG]: "
labels: ["bug"]
assignees: []
---

### Describe the Bug
A clear and concise description of what the bug is.

### Reproduction Steps
Steps to reproduce the behavior:
```python
from reponeedle.engine import RepoNeedleEngine
engine = RepoNeedleEngine.from_directory("/path/to/repo")
result = engine.retrieve("my query", budget_tokens=4000)
```

### Expected Behavior
A clear description of what you expected to happen.

### Screenshots / Logs
If applicable, add screenshots or terminal logs.

### Environment
- OS: [e.g. Windows / Linux / macOS]
- RepoNeedle Version: [e.g. 0.1.0]
- Python Version: [e.g. 3.12]

