# Statistical Significance & Uncertainty Audit

Evaluation performed on **345 positive samples** across **25 repositories** using 10,000 bootstrap resamples.

### Matched Paired Statistical Tests against Baselines

| Comparison | Mean Difference (Δ) | Standard Error | Sample-Level 95% CI | Repo-Clustered 95% CI | Paired Student's t | Wilcoxon W (p-value) | Wins / Ties / Losses |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RepoNeedle vs BM25** | **+0.0767** | 0.0161 | [+0.0458, +0.1085] | **[+0.0202, +0.1129]** | t = 4.776 (p = 2.65e-06) | W = 22384.0 (p = 9.62e-03) | 148 / 18 / 179 |
| **RepoNeedle vs RepoMap** | **+0.0148** | 0.0179 | [-0.0198, +0.0497] | **[-0.0466, +0.0619]** | t = 0.827 (p = 4.09e-01) | W = 23821.5 (p = 3.03e-01) | 122 / 26 / 197 |
| **RepoNeedle vs Lexical** | **+0.0713** | 0.0157 | [+0.0409, +0.1031] | **[+0.0307, +0.1029]** | t = 4.529 (p = 8.17e-06) | W = 22521.5 (p = 1.21e-01) | 133 / 29 / 183 |

### Repository Clustering Analysis
Because benchmark queries are clustered within repositories (e.g. Gin contributes 88 samples), a repository-clustered bootstrap resamples repositories with replacement.
Even under repository clustering, the lower bound of the 95% Confidence Interval for RepoNeedle versus BM25 remains strictly positive (+0.0202), confirming that improvements generalize across repositories rather than being driven by a single large repo.
