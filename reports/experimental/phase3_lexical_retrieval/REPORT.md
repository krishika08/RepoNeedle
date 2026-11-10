# Milestone 2C: Lexical Retrieval Forensics and Development Ablations

> [!IMPORTANT]
> **EXPERIMENTAL. Development evidence only. No confirmatory result.** All experiments used the 15 Milestone 2B **development** repositories (previously used development data). The 10 Milestone 2B held-out repositories were never loaded (asserted in code). **No fresh confirmatory data exists locally**: every ARB split on disk (v0.1, v2 positives, v2 selective, abstention) draws on the same 25 repositories. No production code was changed. Official ARB v2 results and Phases 0–2 are unchanged.

**Scripts**: `benchmarks/run_lexical_forensics.py` · **Tests**: `tests/test_lexical_forensics.py` · **Protocol SHA-256**: `dd0860bac5f0ca016a44156b84441696f547417ba0a465f80468dafa83aa0f11` (registered before any variant result) · **Framework**: Phase 1 product-aligned evaluation (whole-file input, file unit, full ranking)

---

## 1. Conclusion

**NOT VALIDATED.** No lexical change met the pre-registered development-support criterion, so nothing was implemented and nothing was eligible for confirmation. Independently of that, **fresh confirmatory data is unavailable**, so no confirmatory claim would have been possible in any case.

The forensic analysis did identify the **root cause** of the lexical deficit (§3): RepoNeedle's `BM25Index` **ignores query term frequency**. That single factor closes about 79% of the comment2context lexical gap to BM25 on development data, but it also harms trace2code. The pre-registered guardrail excluded it from the hybrid stage. It is the recommended subject of the next pre-registered study (§9).

## 2. Lexical pipeline (traced from code)

| Component | RepoNeedle (`reponeedle/core/lexical.py`, `tokenizer.py`) | ARB BM25 (Phase 1 comparator) |
| :--- | :--- | :--- |
| Unit / input | File; whole-file text (benchmark reconstruction) | File; same whole-file text |
| Document fields | Path tokens × 2.5 (deduplicated per path), symbol tokens × 2.0, body tokens × 1.0, summed into one weighted tf per term | Path + text concatenated once |
| Symbol field in the benchmark | **Empty**: harness documents carry no symbols, and polyglot extraction is off by default (real `from_directory` fills Python symbols via AST) | n/a |
| Tokenizer | `[A-Za-z0-9_]+` words; for each word the raw lowercase form **and** its identifier pieces (camel/snake split). A plain word yields its own token **twice**. Stopwords incl. `self`, `return`, `none`, `true`, `false` | camelCase split, `[A-Za-z0-9]+`, lowercase; one token per piece; no stopwords |
| Query handling | Whole JSON string tokenized; **query term counts are computed but not used** (each distinct term contributes once) | Each term's contribution × its query count |
| BM25 | k1 = 1.5, b = 0.75, global average length over body + path tokens, RSJ idf `ln((N−df+0.5)/(df+0.5)+1)`, scores max-normalised to [0, 1] for fusion | k1 = 1.5, b = 0.75, same idf |
| Use in ranking | Lexical score fused with semantic (+ structural, workflow) scores by task-specific router weights | n/a |

## 3. Development forensics (lexical-only ranking, 166 queries / 15 repositories)

Baseline reproduction: lexical-only L0 equals the Phase 0 whole-file lexical-only results on **91 / 91** overlapping development queries. The hybrid baseline equals Phase 1 whole-file results on **166 / 166**.

### 3.1 One-factor ablations (comment2context Recall@20; repository-clustered 95% CI)

| Factor | Variant | comment2context R@20 (L0 = 0.3732; BM25 = 0.5652) | Δ vs L0 [CI] | Worst task MRR/R@20 change |
| :--- | :--- | :---: | :---: | :---: |
| **Query term frequency** | L4: multiply by query count | **0.5254** | **+0.1522 [+0.051, +0.201]** | **−0.0555** (trace2code MRR) |
| Token duplication | L5: each token once per word | 0.4312 | +0.0580 [+0.000, +0.144] | −0.0025 |
| JSON key tokens | L6: score JSON leaf values only | 0.3949 | +0.0217 [−0.022, +0.089] | −0.0046 |
| Length normalisation | L2: b = 0.4 | 0.4058 | +0.0326 [−0.024, +0.153] | −0.0301 |
| Length normalisation | L3: b = 0.9 | 0.3659 | −0.0072 [−0.020, +0.000] | −0.0121 |
| Field weighting | L1: path weight 2.5 → 1.0 | 0.3732 | 0.0000 | −0.0139 |

### 3.2 Field contribution

| Diagnostic | comment2context MRR / R@20 | Overall MRR / R@20 |
| :--- | :---: | :---: |
| Production (all fields) | 0.1731 / 0.3732 | 0.1551 / 0.3961 |
| Path field only | 0.0656 / 0.1377 | 0.0586 / 0.1807 |
| Body field only | 0.1832 / 0.4022 | 0.1561 / 0.3951 |

The body field carries almost all of the lexical signal; the ×2.5 path weight neither helps nor causes the deficit (L1: no change). The symbol field is empty in this benchmark, so its ×2.0 weight was not exercised.

### 3.3 Structured query tokenization (`forensics_query_and_length.json`)

| Task (dev) | Tokens, RepoNeedle vs ARB (median) | Unique / total | Max repeats of one term | JSON key share | Largest fields |
| :--- | :---: | :---: | :---: | :---: | :--- |
| comment2context | 139 vs 92 | 0.48 | 7 | 12.2% | review_comment 34%, diff_hunk_context 24%, pr_title 9%, given_file 8%, path 8% |
| code2test | 204 vs 135 | 0.41 | 10 | 6.0% | pr_body 67% |
| trace2code | 868 vs 540 | 0.21 | 58 | 1.3% | failure_excerpt 92% |
| edit2ripple | 1,540 vs 1,020 | 0.18 | 184 | 0.5% | anchor_diff 68%, intent 16% |

- All development queries are JSON objects; key names contribute 12% of comment2context query tokens (small, inconsistent benefit from dropping them: L6).
- Token duplication inflates RepoNeedle's query token counts by about 1.5× relative to ARB.
- **Why query term frequency is task-specific**: in comment2context, repetition is informative (an identifier repeated across the review comment, diff hunk and path is likely the subject). In CI failure excerpts and diffs, a few terms repeat 58–184 times, so weighting by raw query count amplifies log and diff noise, consistent with L4's trace2code MRR loss.

### 3.4 Length normalisation

Gold files are long (median length percentile 0.87–0.95 across tasks), and so are the top-10 non-gold files (6.5–10× the corpus median). Neither b = 0.4 nor b = 0.9 produced a consistent benefit. Length normalisation is **not** a cause of the deficit.

## 4. Root cause

The comment2context lexical deficit is caused mainly by **ignoring query term frequency** (L4 recovers +0.152 of the 0.192 Recall@20 gap on development data), with a smaller contribution from **duplicate token counting** (L5, +0.058). Path field weighting and length normalisation are not causes. JSON key tokens contribute marginally.

## 5. Stage 1 → stage 2 (pre-registered rules)

**Stage 1 rule** (lexical-only): candidate if comment2context Recall@20 gain > 0 and no task's MRR or Recall@20 mean change < −0.02. Candidates: **L5** and **L6**, plus their combination. **L4 was excluded** (trace2code MRR −0.0555, from 14 queries in 3 repositories); L2 was excluded (−0.0301).

**Stage 2** (full RepoNeedle hybrid, development data; Δ vs hybrid baseline):

| Arm | c2c R@20 Δ [CI] | c2c MRR Δ | code2test MRR Δ | trace2code MRR Δ | edit2ripple MRR Δ [CI] | Eligible |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| L5 no duplicate tokens | +0.0290 [+0.000, +0.068] | −0.0126 | −0.0054 | −0.0015 | −0.0040 | yes |
| L6 JSON values only | +0.0471 [+0.000, +0.098] | +0.0030 | **−0.0349** | +0.0033 | −0.0038 | **no** (guardrail) |
| **L5 + L6 combined** | **+0.0507 [+0.000, +0.107]** | +0.0099 | +0.0026 | +0.0005 | −0.0085 [−0.016, −0.001] | yes, **selected** |

**Stage 2 rule**: select the eligible arm with the largest comment2context Recall@20 gain (the combined arm); it is "dev-supported" only if that CI excludes zero. The combined arm's CI lower bound is **+0.000**, so it is **not dev-supported**. By the pre-registered rule, **no implementation and no default change** were made.

## 6. Implementation

None. `reponeedle/` is byte-identical to its pre-Milestone-2A fingerprint. All variants exist only as harness subclasses in `benchmarks/run_lexical_forensics.py`.

## 7. Confirmatory data

Not available. A valid confirmation requires fresh repositories disjoint from all 25 ARB v2 repositories, independently labelled for all four tasks (in particular comment2context), split at repository level with a recorded hash, and a protocol registered before treatment results are examined. The previous 10 held-out repositories were not used.

## 8. Limitations

- Development data was previously used (Milestone 2B), and development samples are small for some tasks (trace2code: 14 queries, 3 repositories).
- The L4 exclusion rests on that small trace2code sample.
- Only the pre-registered matrix was tested; no capped or saturated query term frequency variant was evaluated.
- Benchmark queries are structured JSON; task labels are passed explicitly; whole files are reconstructions from ARB chunks.

## 9. Recommendation

1. **Collect fresh confirmatory data first**: new repositories (disjoint from the 25 ARB v2 repositories) with independently established comment2context labels and coverage of the other three tasks. Without it, no lexical improvement can be confirmed.
2. **Pre-register a focused query-term-frequency study** on development data: saturated or capped query term frequency (for example `1 + log(count)` or `min(count, k)`), alone and combined with duplicate-token removal. Primary endpoint: comment2context Recall@20; guardrail emphasis on trace2code and edit2ripple, where queries are highly repetitive.
3. Keep all lexical behaviour unchanged by default until a confirmatory study supports a change.
