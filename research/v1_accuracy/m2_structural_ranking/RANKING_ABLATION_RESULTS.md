# RepoNeedle V1.0.0 — Milestone 2 Full Ranking Ablation Results

## 1. Full Benchmark Comparative Performance (345 Queries, 514 Gold Files)

| Configuration | Description | MRR | Hit@1 | Recall@1 | Recall@5 | Recall@10 | Recall@20 | Coverage@20 | Recall@50 | Candidate Rec |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `m1_baseline` | Frozen M1 Multi-Channel Union Baseline | **0.2675** | 0.0899 | 0.0603 | 0.3599 | 0.4903 | **0.5953** | **0.5507** | 0.7646 | 1.0 |
| `m2a_test_linkage_only` | M1 + Test-to-Code Linkage Alone | **0.1663** | 0.0406 | 0.0272 | 0.2082 | 0.3502 | **0.4786** | **0.458** | 0.6693 | 1.0 |
| `m2b_traceback_only` | M1 + Traceback Reasoning Alone | **0.2658** | 0.087 | 0.0584 | 0.3599 | 0.4903 | **0.5953** | **0.5507** | 0.7646 | 1.0 |
| `m2c_hub_norm_only` | M1 + Hub-Degree Normalization Alone | **0.2657** | 0.087 | 0.0584 | 0.356 | 0.4903 | **0.5992** | **0.5536** | 0.7549 | 1.0 |
| `m2d_combined_structural` | M1 + Combined Structural Graph Features | **0.184** | 0.1072 | 0.072 | 0.1673 | 0.2451 | **0.4047** | **0.3913** | 0.5973 | 1.0 |
| `m2e_rrf` | Reciprocal Rank Fusion (M1 + Structural Ranks) | **0.1871** | 0.1101 | 0.0739 | 0.1595 | 0.249 | **0.3949** | **0.3623** | 0.6342 | 1.0 |
| `m2_full_auto` | **M2 Full Query-Conditioned Ranker (AUTO Mode)** | **0.196** | 0.0754 | 0.0506 | 0.216 | 0.3074 | **0.4728** | **0.4377** | 0.6654 | 1.0 |
| `m2_full_task_conditioned` | M2 Full Ranker (Task-Conditioned Diagnostic) | **0.1981** | 0.0986 | 0.0661 | 0.1965 | 0.2821 | **0.4591** | **0.4348** | 0.6518 | 1.0 |

---

## 2. Paired Repository-Clustered Bootstrap Significance Analysis

- **Bootstrap Iterations**: 1,000 resamples clustered at repository boundary (21 clusters).
- **Comparison**: `m1_baseline` vs `m2_full_auto`.

| Evaluated Metric | Baseline Value | Treatment (M2 Auto) | Delta | 95% Bootstrap CI | p-value | Significance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **MRR** | 0.2675 | 0.196 | **-0.0715** | (-0.1207, -0.0278) | p = 0.0 | **p < 0.001** |
| **Recall@20** | 0.5953 | 0.4728 | **-0.1225** | (-0.1986, -0.0508) | p = 0.0 | **p < 0.001** |
| **Coverage@20**| 0.5507 | 0.4377 | **-0.1130** | (-0.1851, -0.0514) | p = 0.0 | **p < 0.001** |

---

## 3. Query Movement Dynamics

- **Improved Queries**: **124** (35.9%)
- **Unchanged Queries**: **21** (6.1%)
- **Degraded Queries**: **200** (58.0%)
- **Net Query Win Rate**: **-22.0%**

---

## 4. AUTO Mode vs Task-Conditioned Diagnostic Mode

- **AUTO Mode** infers query intent dynamically using `QueryIntentDetector` from the query string alone.
- **Task-Conditioned Mode** supplies the ground-truth benchmark task label (`v2_code2test`, etc.) as an oracle diagnostic upper bound.
- The difference between AUTO Mode and Task-Conditioned Mode is marginal:
  - MRR: **0.196** (Auto) vs **0.1981** (Task-Conditioned)
  - Recall@20: **0.4728** vs **0.4591**
  - Complete Coverage@20: **0.4377** vs **0.4348**
- This confirms that query intent detection in production AUTO mode incurs negligible performance loss compared to oracle task conditioning.
