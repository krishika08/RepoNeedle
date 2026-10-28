# DATASET AND SPLIT MANIFESTS: BENCHMARK SUITES & AUDIT RECORDS

**Document ID**: `DSM-2026-001`  
**Version**: 1.0.0  
**Date**: 2026-10-28  
**Author**: Principal Retrieval Researcher & Lead Systems Engineer  

---

## 1. Overview of Benchmark Split Manifests

To ensure total transparency, reproducibility, and prevent data leakage, all datasets used across the research program are cataloged below with exact sample counts, repository associations, and license classifications.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                Benchmark Split Ecosystem                                │
├────────────────────────────┬─────────────────────────────┬──────────────────────────────┤
│ Development / Regression   │ Process Evaluation Harness  │ Independent Evaluation Gates │
├────────────────────────────┼─────────────────────────────┼──────────────────────────────┤
│ ARB v2 ($N=427$)           │ ContextBench ($N=1,136$)    │ Independent Holdout ($N=200$)│
│ • Positive: 345 samples    │ • 66 repositories           │ • 50+ fresh repositories     │
│ • Selective: 82 samples    │ • 8 languages               │ • Zero-leakage splits        │
│ • 25 repos, 271 snapshots  │ • File/block/line gold      │ • Fresh No-Gold ($N=180$)    │
└────────────────────────────┴─────────────────────────────┴──────────────────────────────┘
```

---

## 2. Manifest 1: ARB v2 Development & Regression Benchmark ($N=427$)

- **Upstream Repository**: `eyuansu62/agent-retrieval-bench`
- **Evaluator Commit**: `9e4d68937f29d5967afd62f4f6a24c1478298133`
- **Total Samples**: $427$ ($345$ Positive Retrieval, $82$ Selective Abstention)
- **Unique Repositories**: $25$
- **Total Unique Snapshots**: $271$ ($218$ positive snapshots, $71$ selective snapshots, $18$ common snapshots)

### Task-Type Distribution ($N=345$ Positive Samples):
| Task Type | Samples ($N$) | Percentage | Mean Gold Files | Target Description |
| :--- | :---: | :---: | :---: | :--- |
| `code2test` | 106 | 30.7% | 1.83 | Implementation feature $\to$ regression test suite |
| `comment2context` | 80 | 23.2% | 1.95 | High-level issue comment $\to$ target code module |
| `trace2code` | 101 | 29.3% | 1.42 | Error stack trace $\to$ root-cause source file |
| `edit2ripple` | 58 | 16.8% | 1.98 | Modified interface $\to$ downstream dependents/callers |

### Repository Distribution ($N=345$ Positive Samples):
| Repository | Positive Samples ($N$) | Percentage of Suite | Primary Language |
| :--- | :---: | :---: | :--- |
| `gin-gonic/gin` | 88 | 25.5% | Go |
| `etcd-io/etcd` | 41 | 11.9% | Go |
| `tokio-rs/tokio` | 38 | 11.0% | Rust |
| `huggingface/transformers` | 36 | 10.4% | Python |
| `pallets/click` | 26 | 7.5% | Python |
| `vitejs/vite` | 25 | 7.2% | TypeScript |
| `huggingface/diffusers` | 16 | 4.6% | Python |
| `caddyserver/caddy` | 13 | 3.8% | Go |
| `clap-rs/clap` | 10 | 2.9% | Rust |
| `spring-projects/spring-boot` | 8 | 2.3% | Java |
| `pytest-dev/pytest` | 7 | 2.0% | Python |
| `vuejs/core` | 6 | 1.7% | TypeScript |
| `astral-sh/ruff` | 6 | 1.7% | Rust |
| `pypa/pip` | 5 | 1.4% | Python |
| `microsoft/playwright` | 4 | 1.2% | TypeScript |
| `fastapi/fastapi` | 3 | 0.9% | Python |
| `scrapy/scrapy` | 3 | 0.9% | Python |
| `ipython/ipython` | 2 | 0.6% | Python |
| `tox-dev/tox` | 2 | 0.6% | Python |
| `mockito/mockito` | 1 | 0.3% | Java |
| `HypothesisWorks/hypothesis` | 1 | 0.3% | Python |
| `eslint/eslint` | 1 | 0.3% | JavaScript |
| `numpy/numpy` | 1 | 0.3% | Python / C |
| `pydantic/pydantic` | 1 | 0.3% | Python |
| `python/mypy` | 1 | 0.3% | Python |

### Selective Abstention Distribution ($N=82$ Samples):
| Stratum | Category / Reason | Samples ($N$) | Description |
| :--- | :--- | :---: | :--- |
| **Natural No-Gold** | `upstream_dependency` | 41 | Issue caused by third-party library |
| | `external_service` | 7 | Issue caused by remote API or network outage |
| | `user_error` | 2 | User configuration or misusage |
| **Counterfactual** | `counterfactual_wrong_repo` | 32 | Task taken from completely different repository |
| **Total** | **All Abstentions** | **82** | Across 71 repository snapshots |

---

## 3. Manifest 2: ContextBench Integration Specification ($N=1,136$)

- **Source**: `Contextbench/ContextBench` (Hugging Face) / `EuniAI/ContextBench`
- **License**: Apache License 2.0
- **Total Scale**: 1,136 real-world issue-resolution tasks across 66 repositories.
- **Language Coverage**: Python, Java, Go, Rust, C++, C, C#, TypeScript.
- **Gold Annotation**:
  - File-level gold targets ($F_{\text{gold}}$)
  - Block/Function-level gold targets ($B_{\text{gold}}$)
  - Line-level gold ranges ($L_{\text{gold}}$)

### Adapter Architecture for RepoNeedle:
The ContextBench evaluation adapter runs RepoNeedle as an upstream context provider:
```python
class RepoNeedleContextBenchAdapter:
    def __init__(self, repo_dir: str, budget_tokens: int = 8000):
        self.engine = RepoNeedleEngine.from_directory(repo_dir)
        self.budget_tokens = budget_tokens

    def get_initial_context(self, task_description: str) -> Dict[str, Any]:
        result = self.engine.retrieve(task_description, budget_tokens=self.budget_tokens)
        return {
            "retrieved_files": [f.path for f in result.selected_files],
            "packed_context": result.to_context_prompt(),
            "total_tokens": result.total_tokens,
            "abstained": result.abstained,
        }
```

---

## 4. Manifest 3: Independent Held-Out Benchmark Design ($N=200$)

### Construction Criteria:
1. **Repository Exclusivity**: Zero repositories overlap with the 25 ARB v2 codebases.
2. **Temporal Quarantine**: Frozen commits sampled from post-2024 releases.
3. **Target Scope**: 200 tasks across 50 independent repositories (4 tasks per repo).
4. **Target Repositories**:
   - *Python*: `django/django`, `psf/black`, `encode/httpx`, `tiangolo/sqlmodel`, `marshmallow-code/marshmallow`.
   - *Go*: `gohugoio/hugo`, `gofiber/fiber`, `spf13/cobra`, `charmbracelet/bubbletea`, `stretchr/testify`.
   - *Rust*: `serde-rs/serde`, `dtolnay/syn`, `BurntSushi/ripgrep`, `hyperium/hyper`, `actix/actix-web`.
   - *TypeScript*: `vercel/next.js`, `facebook/jest`, `expressjs/express`, `prettier/prettier`, `trpc/trpc`.
   - *Java*: `spring-projects/spring-framework`, `micronaut-projects/micronaut-core`, `google/guava`.
   - *C / C++*: `redis/redis`, `sqlite/sqlite`, `protocolbuffers/protobuf`.

---

## 5. Manifest 4: Fresh No-Gold Abstention Benchmark Design ($N=180$)

### 4-Tier Typology:
1. **Tier 1: Upstream Dependency & External Service Negatives ($N=60$)**:
   - 60 real GitHub issues where the resolution was closed as "not a bug in this repo" (e.g. bug in OS kernel, upstream libc, or external cloud API).
2. **Tier 2: Sibling-Repo Plausible Counterfactuals ($N=50$)**:
   - 50 tasks swapped between sibling projects (e.g. a `FastAPI` dependency injection query submitted to `Flask`).
3. **Tier 3: Hard Ambiguous Solvable Positives ($N=50$)**:
   - 50 legitimate solvable queries formulated with abstract or conversational descriptions to measure false abstention.
4. **Tier 4: Exotic Domain Negatives ($N=20$)**:
   - 20 queries from specialized compiler and hardware description repos to verify cross-domain calibration.
