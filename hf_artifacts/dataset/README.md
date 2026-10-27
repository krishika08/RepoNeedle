---
annotations_creators:
- machine-generated
- expert-generated
language:
- en
- code
license: mit
multilinguality:
- monolingual
size_categories:
- n<1K
source_datasets:
- original
tags:
- code-search
- repository-retrieval
- context-budgeting
- agentic-coding
- evaluation-benchmark
task_categories:
- text-retrieval
- feature-extraction
task_ids:
- document-retrieval
pretty_name: RepoNeedle-Bench
dataset_info:
  features:
  - name: id
    dtype: string
  - name: repo_name
    dtype: string
  - name: task_type
    dtype: string
  - name: query
    dtype: string
  - name: gold_files
    sequence: string
  - name: anchor_files
    sequence: string
  - name: budget_tokens
    dtype: int32
  - name: description
    dtype: string
  - name: is_held_out_repo
    dtype: bool
  splits:
  - name: train
    num_bytes: 8400
    num_examples: 10
  - name: test
    num_bytes: 4200
    num_examples: 5
  download_size: 12600
  dataset_size: 12600
---

# RepoNeedle-Bench: Repository Context Retrieval Benchmark for AI Coding Agents

## Dataset Description
**RepoNeedle-Bench** is a specialized, open-source benchmark designed to evaluate **upstream repository context retrieval** and **token-budget-aware context selection** for autonomous AI coding agents.

Rather than measuring end-to-end patch generation (where retrieval failures are masked by LLM synthesis capabilities), RepoNeedle-Bench isolates the critical upstream context acquisition phase across five distinct software engineering workflow categories:

1. **`trace2code`**: Tracing execution error stack traces and exceptions down to root-cause implementation files.
2. **`code2test`**: Retrieving regression and unit test suites implied by an implementation change or feature request.
3. **`edit2ripple`**: Identifying downstream dependencies, callers, and interface implementers affected by an anchor file change.
4. **`comment2context`**: Connecting high-level natural language issue comments and feature requests to core implementation files.
5. **`selective`**: Recognizing out-of-repository, non-internal, or counterfactual queries where the retriever should abstain from returning hallucinated files.

## Dataset Structure

Each sample in `train.jsonl` (development split) and `test.jsonl` (held-out split) follows the schema:

```json
{
  "id": "flask_trace2code_01",
  "repo_name": "pallets/flask",
  "task_type": "trace2code",
  "query": "Traceback (most recent call last):\n  File \"src/flask/app.py\", line 28, in wsgi_app...",
  "gold_files": [
    "src/flask/wrappers.py",
    "src/flask/app.py"
  ],
  "anchor_files": [],
  "budget_tokens": 4000,
  "description": "Traceback in get_json and dispatch_request.",
  "is_held_out_repo": false
}
```

## Data Provenance & Permissive Licensing
RepoNeedle-Bench is built exclusively from permissively licensed open-source repositories to ensure completely unrestricted downstream academic, personal, and commercial reuse:
- `pallets/flask` (BSD-3-Clause)
- `psf/requests` (Apache-2.0)
- `tiangolo/fastapi` (MIT License)

**No non-commercial or copyleft share-alike data (such as CC BY-NC-SA materials) is included.**

## Benchmark Evaluation Metrics
Evaluations should measure both ranking quality and token budget efficiency:
- **Recall@k** (k=1, 3, 5)
- **Mean Reciprocal Rank (MRR)**
- **nDCG@k**
- **Budgeted Context Coverage (BCC@2k, BCC@4k, BCC@8k)**: The percentage of gold files present within a hard context token constraint.
- **Irrelevant Token Waste**: The number of non-gold tokens included in context.
- **Selective Abstention Accuracy**: Precision, recall, and F1 score on no-gold queries.

## Citation
```bibtex
@misc{reponeedle2026,
  author = {RepoNeedle Contributors},
  title = {RepoNeedle-Bench: Repository Context Retrieval Benchmark for AI Coding Agents},
  year = {2026},
  publisher = {Hugging Face},
  howpublished = {\url{https://huggingface.co/datasets/RepoNeedle/RepoNeedle-Bench}}
}
```
