# Stage 4 benchmark summary (generated from `stage4_benchmark.json`)

Baseline `60fbfc072dcb35209aaea113ecd4162a9092a432` (clean: True); candidate `c5d9d22d27240c438a8ede22c67395dffaf03d69` (clean: False).
Windows-11-10.0.26200-SP0, Python 3.12.10, numpy 2.5.2, SciPy 1.18.1, 18 logical CPUs, 15.5 GB RAM (6.9 GB available at start).

## reduced 10000 files

Dataset `stage1-generator/reduced/10000/seed-7`, manifest SHA-256 `4d7140fe8cdafc47â€¦`, 10000 files, 14.7 MB; rounds: 3; verification: [True, True, True]; conditions: {'started_utc': '2026-11-20T19:29:21.339815Z', 'ended_utc': '2026-11-20T19:53:16.556755Z', 'keep_awake_requested': True, 'sleep_or_standby_events_during_workload': []}

| Phase | Metric | Baseline median (minâ€“max, sd, n) | Candidate median (minâ€“max, sd, n) |
| :--- | :--- | ---: | ---: |
| uncached | ready_engine_s | 35.575 (35.255â€“35.801, sd 0.2743, n 3) | 39.36 (38.722â€“40.838, sd 1.0854, n 3) |
| uncached | semantic_fit_s | 16.681 (16.659â€“16.776, sd 0.0622, n 3) | 20.596 (20.113â€“21.611, sd 0.7646, n 3) |
| uncached | peak_working_set_gb | 2.0479 (2.0477â€“2.0481, sd 0.0002, n 3) | 1.3811 (1.3803â€“1.3818, sd 0.0007, n 3) |
| uncached | peak_committed_gb | 3.1032 (3.1031â€“3.1036, sd 0.0002, n 3) | 2.4352 (2.4348â€“2.4361, sd 0.0007, n 3) |
| uncached | peak_wal_mb | 0.0 (0.0â€“0.0, sd 0.0, n 3) | 0.0 (0.0â€“0.0, sd 0.0, n 3) |
| cold_cached | ready_engine_s | 50.973 (49.93â€“51.331, sd 0.7279, n 3) | 56.728 (56.48â€“56.736, sd 0.1455, n 3) |
| cold_cached | semantic_fit_s | 16.857 (16.27â€“16.921, sd 0.3588, n 3) | 20.592 (20.441â€“20.633, sd 0.1011, n 3) |
| cold_cached | peak_working_set_gb | 2.0789 (2.0777â€“2.081, sd 0.0017, n 3) | 1.4093 (1.4092â€“1.4096, sd 0.0002, n 3) |
| cold_cached | peak_committed_gb | 3.1402 (3.139â€“3.1424, sd 0.0017, n 3) | 2.4684 (2.4683â€“2.4685, sd 0.0001, n 3) |
| cold_cached | peak_wal_mb | 17.1154 (17.1154â€“17.1154, sd 0.0, n 3) | 17.1154 (17.1154â€“17.1154, sd 0.0, n 3) |
| cold_cached | scan_ms | 4979.243 (4955.515â€“5032.653, sd 39.5093, n 3) | 5128.796 (5034.387â€“5165.112, sd 67.4795, n 3) |
| cold_cached | load_ms | 3.881 (3.039â€“8.589, sd 2.991, n 3) | 2.961 (2.69â€“6.602, sd 2.1846, n 3) |
| cold_cached | fit_ms | 31131.976 (30328.181â€“31675.084, sd 677.643, n 3) | 35322.04 (35155.25â€“35408.019, sd 128.5194, n 3) |
| cold_cached | persist_ms | 14661.211 (14556.324â€“14857.374, sd 152.8138, n 3) | 16226.962 (16182.379â€“16270.946, sd 44.2838, n 3) |
| warm_restart | ready_engine_s | 21.506 (21.435â€“21.817, sd 0.2032, n 3) | 26.18 (25.911â€“26.429, sd 0.2591, n 3) |
| warm_restart | semantic_fit_s | 3.303 (3.253â€“3.333, sd 0.0404, n 3) | 2.92 (2.89â€“2.944, sd 0.0271, n 3) |
| warm_restart | peak_working_set_gb | 2.3691 (2.3663â€“2.3697, sd 0.0018, n 3) | 1.7132 (1.7113â€“1.7147, sd 0.0017, n 3) |
| warm_restart | peak_committed_gb | 3.4278 (3.4243â€“3.4279, sd 0.0021, n 3) | 2.7689 (2.768â€“2.7716, sd 0.0019, n 3) |
| warm_restart | peak_wal_mb | 17.1311 (17.1311â€“17.1311, sd 0.0, n 3) | 17.1311 (17.1311â€“17.1311, sd 0.0, n 3) |
| warm_restart | scan_ms | 2994.978 (2898.159â€“3027.685, sd 67.3556, n 3) | 3025.521 (2965.521â€“3044.247, sd 41.1267, n 3) |
| warm_restart | load_ms | 8689.515 (8652.24â€“8863.757, sd 112.9079, n 3) | 13253.225 (13140.02â€“13411.273, sd 136.2429, n 3) |
| warm_restart | fit_ms | 5974.347 (5892.306â€“6432.114, sd 290.882, n 3) | 6107.81 (5601.787â€“6138.141, sd 301.2902, n 3) |
| warm_restart | persist_ms | 3440.948 (2927.792â€“3546.497, sd 330.9747, n 3) | 3412.683 (3187.743â€“3806.599, sd 313.2493, n 3) |
| warm_restart | query_latency_median_ms | 37.351 (36.858â€“39.663, sd 1.4976, n 3) | 40.896 (40.081â€“41.336, sd 0.6368, n 3) |

| Component (retained, uncached build) | Baseline MB | Candidate MB |
| :--- | ---: | ---: |
| documents_raw_text | 15.2 | 15.2 |
| documents_metadata | 9.6 | 9.6 |
| semantic_feature_cache | 1064.9 | 421.8 |
| semantic_vocabulary_idf_matrix | 0.9 | 0.9 |
| lexical_term_cache | 98.6 | 98.6 |
| lexical_index_rest | 106.1 | 106.1 |
| abstainer | 109.6 | 109.6 |
| function_graph | 76.9 | 75.2 |
| repo_graph | 16.5 | 16.5 |
| engine_rest | 0.3 | 0.3 |

Excluded, failed or aborted phases: none

## realistic 10000 files

Dataset `stage1-generator/realistic/10000/seed-7`, manifest SHA-256 `32b892595492e42câ€¦`, 10000 files, 85.3 MB; rounds: 1; verification: [None]; conditions: {'started_utc': '2026-11-20T19:53:22.053306Z', 'ended_utc': '2026-11-20T20:14:14.517710Z', 'keep_awake_requested': True, 'sleep_or_standby_events_during_workload': []}

| Phase | Metric | Baseline median (minâ€“max, sd, n) | Candidate median (minâ€“max, sd, n) |
| :--- | :--- | ---: | ---: |
| uncached | ready_engine_s | 137.256 (137.256â€“137.256, sd 0.0, n 1) | 143.91 (143.91â€“143.91, sd 0.0, n 1) |
| uncached | semantic_fit_s | 64.545 (64.545â€“64.545, sd 0.0, n 1) | 74.979 (74.979â€“74.979, sd 0.0, n 1) |
| uncached | peak_working_set_gb | 5.4762 (5.4762â€“5.4762, sd 0.0, n 1) | 3.671 (3.671â€“3.671, sd 0.0, n 1) |
| uncached | peak_committed_gb | 6.5402 (6.5402â€“6.5402, sd 0.0, n 1) | 4.7319 (4.7319â€“4.7319, sd 0.0, n 1) |
| uncached | peak_wal_mb | 0.0 (0.0â€“0.0, sd 0.0, n 1) | 0.0 (0.0â€“0.0, sd 0.0, n 1) |
| cold_cached | ready_engine_s | 159.297 (159.297â€“159.297, sd 0.0, n 1) | 174.757 (174.757â€“174.757, sd 0.0, n 1) |
| cold_cached | semantic_fit_s | 64.163 (64.163â€“64.163, sd 0.0, n 1) | 76.217 (76.217â€“76.217, sd 0.0, n 1) |
| cold_cached | peak_working_set_gb | 5.6249 (5.6249â€“5.6249, sd 0.0, n 1) | 3.6617 (3.6617â€“3.6617, sd 0.0, n 1) |
| cold_cached | peak_committed_gb | 6.6928 (6.6928â€“6.6928, sd 0.0, n 1) | 4.8939 (4.8939â€“4.8939, sd 0.0, n 1) |
| cold_cached | peak_wal_mb | 19.355 (19.355â€“19.355, sd 0.0, n 1) | 19.355 (19.355â€“19.355, sd 0.0, n 1) |
| cold_cached | scan_ms | 12002.554 (12002.554â€“12002.554, sd 0.0, n 1) | 11901.033 (11901.033â€“11901.033, sd 0.0, n 1) |
| cold_cached | load_ms | 7.544 (7.544â€“7.544, sd 0.0, n 1) | 7.196 (7.196â€“7.196, sd 0.0, n 1) |
| cold_cached | fit_ms | 123968.355 (123968.355â€“123968.355, sd 0.0, n 1) | 138275.575 (138275.575â€“138275.575, sd 0.0, n 1) |
| cold_cached | persist_ms | 23297.877 (23297.877â€“23297.877, sd 0.0, n 1) | 24553.71 (24553.71â€“24553.71, sd 0.0, n 1) |
| warm_restart | ready_engine_s | â€“ | 57.354 (57.354â€“57.354, sd 0.0, n 1) |
| warm_restart | semantic_fit_s | â€“ | 8.168 (8.168â€“8.168, sd 0.0, n 1) |
| warm_restart | peak_working_set_gb | â€“ | 4.7279 (4.7279â€“4.7279, sd 0.0, n 1) |
| warm_restart | peak_committed_gb | â€“ | 5.7922 (5.7922â€“5.7922, sd 0.0, n 1) |
| warm_restart | peak_wal_mb | â€“ | 19.3707 (19.3707â€“19.3707, sd 0.0, n 1) |
| warm_restart | scan_ms | â€“ | 3351.95 (3351.95â€“3351.95, sd 0.0, n 1) |
| warm_restart | load_ms | â€“ | 32332.418 (32332.418â€“32332.418, sd 0.0, n 1) |
| warm_restart | fit_ms | â€“ | 17569.292 (17569.292â€“17569.292, sd 0.0, n 1) |
| warm_restart | persist_ms | â€“ | 3215.552 (3215.552â€“3215.552, sd 0.0, n 1) |
| warm_restart | query_latency_median_ms | â€“ | 59.989 (59.989â€“59.989, sd 0.0, n 1) |

| Component (retained, uncached build) | Baseline MB | Candidate MB |
| :--- | ---: | ---: |
| documents_raw_text | 85.7 | 85.7 |
| documents_metadata | 25.0 | 25.0 |
| semantic_feature_cache | 2801.0 | 1093.7 |
| semantic_vocabulary_idf_matrix | 0.9 | 0.9 |
| lexical_term_cache | 366.7 | 366.7 |
| lexical_index_rest | 413.7 | 413.7 |
| abstainer | 218.6 | 218.6 |
| function_graph | 388.6 | 382.8 |
| repo_graph | 47.7 | 47.7 |
| engine_rest | 0.3 | 0.3 |

Excluded, failed or aborted phases: [{'round': 1, 'variant': 'baseline', 'phase': 'warm_restart', 'paging_suspected': True, 'suspended_suspected': False, 'seconds_to_ready_engine': 48.6}]

## reduced 30000 files

Dataset `stage1-generator/reduced/30000/seed-7`, manifest SHA-256 `9498fea5849c70bdâ€¦`, 30000 files, 44.0 MB; rounds: 1; verification: [None]; conditions: {'started_utc': '2026-11-20T20:14:20.812021Z', 'ended_utc': '2026-11-20T20:40:20.328256Z', 'keep_awake_requested': True, 'sleep_or_standby_events_during_workload': []}

| Phase | Metric | Baseline median (minâ€“max, sd, n) | Candidate median (minâ€“max, sd, n) |
| :--- | :--- | ---: | ---: |
| uncached | ready_engine_s | 112.354 (112.354â€“112.354, sd 0.0, n 1) | 126.538 (126.538â€“126.538, sd 0.0, n 1) |
| uncached | semantic_fit_s | 55.694 (55.694â€“55.694, sd 0.0, n 1) | 71.059 (71.059â€“71.059, sd 0.0, n 1) |
| uncached | peak_working_set_gb | 5.8991 (5.8991â€“5.8991, sd 0.0, n 1) | 3.8702 (3.8702â€“3.8702, sd 0.0, n 1) |
| uncached | peak_committed_gb | 6.9642 (6.9642â€“6.9642, sd 0.0, n 1) | 4.9309 (4.9309â€“4.9309, sd 0.0, n 1) |
| uncached | peak_wal_mb | 0.0 (0.0â€“0.0, sd 0.0, n 1) | 0.0 (0.0â€“0.0, sd 0.0, n 1) |
| cold_cached | ready_engine_s | 265.993 (265.993â€“265.993, sd 0.0, n 1) | 340.116 (340.116â€“340.116, sd 0.0, n 1) |
| cold_cached | semantic_fit_s | 55.02 (55.02â€“55.02, sd 0.0, n 1) | 70.539 (70.539â€“70.539, sd 0.0, n 1) |
| cold_cached | peak_working_set_gb | 5.9192 (5.9192â€“5.9192, sd 0.0, n 1) | 3.9787 (3.9787â€“3.9787, sd 0.0, n 1) |
| cold_cached | peak_committed_gb | 7.0921 (7.0921â€“7.0921, sd 0.0, n 1) | 5.0552 (5.0552â€“5.0552, sd 0.0, n 1) |
| cold_cached | peak_wal_mb | 51.3342 (51.3342â€“51.3342, sd 0.0, n 1) | 51.3342 (51.3342â€“51.3342, sd 0.0, n 1) |
| cold_cached | scan_ms | 14148.141 (14148.141â€“14148.141, sd 0.0, n 1) | 14139.709 (14139.709â€“14139.709, sd 0.0, n 1) |
| cold_cached | load_ms | 7.394 (7.394â€“7.394, sd 0.0, n 1) | 7.505 (7.505â€“7.505, sd 0.0, n 1) |
| cold_cached | fit_ms | 99312.656 (99312.656â€“99312.656, sd 0.0, n 1) | 115065.762 (115065.762â€“115065.762, sd 0.0, n 1) |
| cold_cached | persist_ms | 152509.344 (152509.344â€“152509.344, sd 0.0, n 1) | 210885.811 (210885.811â€“210885.811, sd 0.0, n 1) |
| warm_restart | ready_engine_s | â€“ | 112.402 (112.402â€“112.402, sd 0.0, n 1) |
| warm_restart | semantic_fit_s | â€“ | 10.86 (10.86â€“10.86, sd 0.0, n 1) |
| warm_restart | peak_working_set_gb | â€“ | 4.8501 (4.8501â€“4.8501, sd 0.0, n 1) |
| warm_restart | peak_committed_gb | â€“ | 5.9168 (5.9168â€“5.9168, sd 0.0, n 1) |
| warm_restart | peak_wal_mb | â€“ | 51.3499 (51.3499â€“51.3499, sd 0.0, n 1) |
| warm_restart | scan_ms | â€“ | 8418.172 (8418.172â€“8418.172, sd 0.0, n 1) |
| warm_restart | load_ms | â€“ | 61342.209 (61342.209â€“61342.209, sd 0.0, n 1) |
| warm_restart | fit_ms | â€“ | 20712.521 (20712.521â€“20712.521, sd 0.0, n 1) |
| warm_restart | persist_ms | â€“ | 19413.296 (19413.296â€“19413.296, sd 0.0, n 1) |
| warm_restart | query_latency_median_ms | â€“ | 134.48 (134.48â€“134.48, sd 0.0, n 1) |

| Component (retained, uncached build) | Baseline MB | Candidate MB |
| :--- | ---: | ---: |
| documents_raw_text | 45.4 | 45.4 |
| documents_metadata | 28.8 | 28.8 |
| semantic_feature_cache | 3184.0 | 1240.9 |
| semantic_vocabulary_idf_matrix | 1.0 | 1.0 |
| lexical_term_cache | 294.4 | 294.4 |
| lexical_index_rest | 288.5 | 288.5 |
| abstainer | 319.8 | 319.8 |
| function_graph | 226.4 | 222.3 |
| repo_graph | 48.9 | 48.9 |
| engine_rest | 1.2 | 1.2 |

Excluded, failed or aborted phases: [{'round': 1, 'variant': 'baseline', 'phase': 'warm_restart', 'paging_suspected': True, 'suspended_suspected': False, 'seconds_to_ready_engine': 73.449}]
