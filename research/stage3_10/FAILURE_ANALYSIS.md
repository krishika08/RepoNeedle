# RepoNeedle Stage 3.10 — Qualitative Failure, Win, and Ranking Dynamics Analysis

## 1. Overview of Ranking Dynamics

Across the 345 positive ARB v2 queries, the class-to-test invocation graph produced ranking movements on 176 queries:
- **Wins**: 24 queries experienced a positive MRR or Recall@20 gain.
- **Losses**: 9 queries experienced a negative MRR or Recall@20 movement.
- **Neutral Shift**: 143 queries experienced ranking changes among non-gold files that left MRR, Recall@20, and Hit@20 unchanged.
- **Strict Invariant Maintained**: On **100% of the 345 queries**, ranks 1 to 3 produced by BM25 were preserved without a single modification.

---

## 2. In-Depth Win Case Studies

### Case Study 1: Resolving Asymmetric Filename Mappings in `fastapi/fastapi`
- **Query ID**: `7f2b7ed09afc0e1e57683529`
- **Task Type**: `code2test`
- **Gold Files**:
  - `tests/test_orjson_response_class.py`
  - `tests/test_tutorial/test_custom_response/test_tutorial001.py`
  - `tests/test_tutorial/test_custom_response/test_tutorial001b.py`
- **Control Ranking**:
  1. `fastapi/responses.py` (Rank 1, BM25 seed)
  2. `docs/en/docs/reference/responses.md` (Rank 2)
  3. `docs/zh/docs/advanced/custom-response.md` (Rank 3)
  ...
  9. `tests/test_orjson_response_class.py` (Rank 9, MRR = 0.1111)
- **Test-Graph Ranking**:
  7. `tests/test_orjson_response_class.py` (Rank 7, MRR = 0.1429, **$\Delta \text{MRR} = +0.0317$**)
- **Root Cause & Diagnosis**:
  In Stage 3.9, filename test discovery looked for `tests/test_responses.py` for seed `fastapi/responses.py`. Because no file named `test_responses.py` exists, filename discovery yielded nothing.
  In Stage 3.10, the class-to-test extractor inspected `tests/test_orjson_response_class.py` and identified a `DIRECT_CLASS_CONSTRUCTION` edge targeting `ORJSONResponse` in `fastapi/responses.py` ($\text{confidence} = 0.95$). Because `responses.py` was the rank-1 seed, the degree-normalized propagation boosted `test_orjson_response_class.py` from rank 9 to rank 7.

---

### Case Study 2: Cross-File Test Discovery in Go (`gin-gonic/gin`)
- **Query ID**: `5f4c149c9f7dac47ebcf685d`
- **Task Type**: `code2test`
- **Gold File**: `routes_test.go`
- **Control Ranking**:
  Rank 34 (MRR = 0.0294, Recall@20 = 0.0000, Hit@20 = 0.0000)
- **Test-Graph Ranking**:
  Rank 19 (MRR = 0.0526, Recall@20 = 1.0000, Hit@20 = 1.0000, **$\Delta \text{Recall@20} = +1.0000$**)
- **Root Cause & Diagnosis**:
  The query sought tests exercising the routing trie algorithms defined in `tree.go`. `tree.go` was ranked at position 2 as a protected seed.
  Under control, `routes_test.go` was buried at rank 34 because its lexical match with the query was weak. In Go, tests for routing algorithms instantiate the route trie via `tree.go` structures and invoke `addRoute`. The parser identified `DIRECT_METHOD_CALL` edges linking `routes_test.go` to `tree.go`. This promoted `routes_test.go` by 15 positions, bringing it directly into the Top-20 candidate set.

---

### Case Study 3: Large Submodule Re-ranking in `pallets/click`
- **Repository**: `pallets/click` (10 wins, 1 loss across 26 queries)
- **Root Cause & Diagnosis**:
  Click's test suite does not follow a 1:1 filename convention (e.g. `test_basic.py`, `test_formatting.py`, `test_termui.py` test classes defined across `core.py`, `types.py`, and `utils.py`). The class-to-test invocation graph successfully connected `Command`, `Context`, and `Option` usages in `tests/test_*.py` back to `core.py`, driving a massive $+0.0769$ Recall@20 improvement across the entire repository.

---

## 3. In-Depth Regression (Loss) Case Studies

### Case Study 4: Inter-Test Competition in `huggingface/transformers`
- **Query ID**: `a82117a5d29dd98d94ceb931`
- **Task Type**: `code2test`
- **Gold Files**:
  - `tests/models/pe_audio_video/test_modeling_pe_audio_video.py`
  - `tests/models/pe_video/test_modeling_pe_video.py`
- **Control Ranking**:
  `tests/models/pe_audio_video/test_modeling_pe_audio_video.py` ranked at position 4 (MRR = 0.2500)
- **Test-Graph Ranking**:
  `tests/models/pe_audio_video/test_modeling_pe_audio_video.py` demoted to position 5 (MRR = 0.2000, $\Delta \text{MRR} = -0.0500$)
- **Root Cause & Diagnosis**:
  The protected seed was `src/transformers/models/timm_wrapper/modeling_timm_wrapper.py` (Rank 2). Both `test_modeling_pe_audio_video.py` and a non-gold sibling test `test_modeling_timm_wrapper.py` had invocation edges to `timm_wrapper`. However, `test_modeling_timm_wrapper.py` had both filename discovery match and an invocation edge, receiving combined boosts that pushed it ahead of `test_modeling_pe_audio_video.py`.
  Importantly, both gold files remained inside the Top-10, and Recall@20 remained $1.0000$.

---

### Case Study 5: Competing Middleware and Helpers in `scrapy/scrapy`
- **Query ID**: `0b514d819e10c606b274e8c0`
- **Task Type**: `comment2context`
- **Gold Files**: `tests/test_http_request.py`, `tests/test_http_response.py`
- **Control Ranking**: Rank 21 (MRR = 0.0476, Recall@20 = 0.0000)
- **Test-Graph Ranking**: Rank 22 (MRR = 0.0455, Recall@20 = 0.0000, $\Delta \text{MRR} = -0.0022$)
- **Root Cause & Diagnosis**:
  In Scrapy, `Request` and `Response` are fundamental data classes referenced by dozens of test files. While `Request` is on the generic blacklist, an explicit import in an unrelated test file `tests/test_pipeline_media.py` was promoted by a fraction of a score point, displacing `test_http_request.py` from rank 21 to rank 22.

---

## 4. Invariant Protection and Hub Suppression Audit

1. **Rank 1–3 BM25 Freeze Invariant**:
   - Total queries: 345
   - Invariant checks: $345 \times 3 = 1035$ rank positions
   - Violations: **0** (100% compliance)

2. **Hub Suppression Efficiency**:
   Across all 218 snapshots, 9,399 ambiguous references to generic symbols (`Config`, `Context`, `Options`, `Client`) were safely intercepted and suppressed. Without this suppression, repositories like `huggingface/transformers` (which define dozens of `*Config` classes) would have experienced complete hub diffusion collapse.

3. **Degree Normalization Efficiency**:
   Comparison with Arm C demonstrated that unweighted random degree connectivity drops Recall@20 from $0.5518$ to $0.5474$. Symmetric normalization ($\frac{1}{\sqrt{d_{\text{out}} \cdot d_{\text{in}}}}$) effectively bounded edge influence and ensured high-degree test suites did not overpower focused unit tests.
