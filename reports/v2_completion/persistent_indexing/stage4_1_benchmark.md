# Stage 4 benchmark summary (generated from `stage4_1_benchmark.json`)

Revisions: baseline `60fbfc072dcb35209aaea113ecd4162a9092a432` (clean: True); intern `643fa228a9ca01cf0088aa078f20856d77a4790e` (clean: True); candidate `41991e870c32009a5625c534d2100ff534097b79` (clean: True).
Windows-11-10.0.26200-SP0, Python 3.12.10, numpy 2.5.2, SciPy 1.18.1, 18 logical CPUs, 15.5 GB RAM (4.6 GB available at start; 0 = unknown).

## reduced 10000 files

Dataset `stage1-generator/reduced/10000/seed-7`, manifest SHA-256 `4d7140fe8cdafc47…`, 10000 files, 14.7 MB; rounds: 3; verification: [True, True, True]; conditions: {'started_utc': '2026-11-21T07:17:52.510001Z', 'ended_utc': '2026-11-21T12:12:29.106321Z', 'keep_awake_requested': True, 'sleep_or_standby_events_during_workload': ['2026-11-21T13:04:32.5820000Z', '2026-11-21T16:45:19.2170000Z']}

| Phase | Metric | Baseline median (min–max, sd, n) | Intern median (min–max, sd, n) | Candidate median (min–max, sd, n) |
| :--- | :--- | ---: | ---: | ---: |
| uncached | ready_engine_s | 34.895 (34.738–63.655, sd 16.6501, n 3) | 39.932 (38.376–85.794, sd 26.9389, n 3) | 35.509 (34.812–36.132, sd 0.6603, n 3) |
| uncached | semantic_fit_s | 16.649 (16.563–28.581, sd 6.9139, n 3) | 21.015 (20.255–50.253, sd 17.1042, n 3) | 16.916 (16.656–17.119, sd 0.2321, n 3) |
| uncached | peak_working_set_gb | 2.0483 (2.0479–2.0488, sd 0.0005, n 3) | 1.3809 (1.3803–1.3815, sd 0.0006, n 3) | 1.0862 (1.0858–1.0869, sd 0.0006, n 3) |
| uncached | peak_committed_gb | 3.1034 (3.1033–3.105, sd 0.0009, n 3) | 2.4352 (2.4349–2.436, sd 0.0005, n 3) | 2.1399 (2.1396–2.1408, sd 0.0006, n 3) |
| uncached | peak_wal_mb | 0.0 (0.0–0.0, sd 0.0, n 3) | 0.0 (0.0–0.0, sd 0.0, n 3) | 0.0 (0.0–0.0, sd 0.0, n 3) |
| cold_cached | ready_engine_s | 50.886 (50.208–120.347, sd 40.3005, n 3) | 57.017 (55.572–57.748, sd 1.1074, n 3) | 47.452 (47.315–49.028, sd 0.9519, n 3) |
| cold_cached | semantic_fit_s | 16.88 (16.718–41.8, sd 14.4346, n 3) | 20.904 (20.397–21.019, sd 0.3309, n 3) | 16.803 (16.615–17.027, sd 0.2063, n 3) |
| cold_cached | peak_working_set_gb | 2.0811 (2.0779–2.083, sd 0.0026, n 3) | 1.4099 (1.4096–1.4117, sd 0.0011, n 3) | 1.1444 (1.1439–1.1467, sd 0.0015, n 3) |
| cold_cached | peak_committed_gb | 3.1432 (3.1393–3.1439, sd 0.0025, n 3) | 2.4686 (2.4685–2.4706, sd 0.0012, n 3) | 2.2043 (2.2037–2.206, sd 0.0012, n 3) |
| cold_cached | peak_wal_mb | 17.1154 (17.1154–17.1154, sd 0.0, n 3) | 17.1154 (17.1154–17.1154, sd 0.0, n 3) | 17.1154 (17.1154–17.1154, sd 0.0, n 3) |
| cold_cached | scan_ms | 4941.118 (4935.035–8811.657, sd 2236.4148, n 3) | 5251.124 (4899.473–5491.488, sd 297.7457, n 3) | 5159.886 (5018.92–5254.624, sd 118.6051, n 3) |
| cold_cached | load_ms | 3.559 (2.851–11.637, sd 4.8811, n 3) | 5.147 (4.133–8.388, sd 2.2225, n 3) | 2.581 (2.429–3.347, sd 0.492, n 3) |
| cold_cached | fit_ms | 31041.113 (30882.613–75442.409, sd 25680.9775, n 3) | 35627.14 (34426.214–35635.791, sd 695.8657, n 3) | 30697.124 (30487.134–32131.978, sd 895.2107, n 3) |
| cold_cached | persist_ms | 14889.913 (14376.514–36062.392, sd 12374.8047, n 3) | 16232.022 (16114.673–16601.542, sd 254.0857, n 3) | 11714.259 (11486.374–11795.168, sd 160.1206, n 3) |
| warm_restart | ready_engine_s | 21.757 (21.587–23.269, sd 0.9259, n 3) | 26.846 (26.402–27.361, sd 0.4799, n 3) | 21.939 (21.924–22.58, sd 0.3745, n 3) |
| warm_restart | semantic_fit_s | 3.463 (3.353–3.695, sd 0.1746, n 3) | 3.117 (2.949–3.15, sd 0.1078, n 3) | 1.472 (1.471–1.534, sd 0.0361, n 3) |
| warm_restart | peak_working_set_gb | 2.3668 (2.3645–2.367, sd 0.0014, n 3) | 1.7126 (1.7108–1.7133, sd 0.0013, n 3) | 1.4295 (1.4285–1.4302, sd 0.0009, n 3) |
| warm_restart | peak_committed_gb | 3.4248 (3.4224–3.4265, sd 0.0021, n 3) | 2.7685 (2.7671–2.769, sd 0.001, n 3) | 2.4855 (2.4841–2.4858, sd 0.0009, n 3) |
| warm_restart | peak_wal_mb | 17.1311 (17.1311–17.1311, sd 0.0, n 3) | 17.1311 (17.1311–17.1311, sd 0.0, n 3) | 17.1311 (17.1311–17.1311, sd 0.0, n 3) |
| warm_restart | scan_ms | 2957.499 (2926.263–3265.923, sd 187.7365, n 3) | 3256.925 (3100.759–3303.75, sd 106.2903, n 3) | 2962.992 (2894.248–3198.189, sd 159.3861, n 3) |
| warm_restart | load_ms | 8715.229 (8714.575–9348.583, sd 365.856, n 3) | 13437.347 (13300.141–13779.911, sd 247.1015, n 3) | 10975.583 (10963.153–11178.437, sd 120.8659, n 3) |
| warm_restart | fit_ms | 6685.143 (6489.504–7084.17, sd 303.0745, n 3) | 6192.265 (5976.696–6405.143, sd 214.2249, n 3) | 4651.947 (4108.18–4759.274, sd 349.0762, n 3) |
| warm_restart | persist_ms | 2980.284 (2923.369–3050.574, sd 63.7196, n 3) | 3306.953 (3263.099–3805.553, sd 301.3253, n 3) | 2961.625 (2926.229–3433.685, sd 283.3152, n 3) |
| warm_restart | query_latency_median_ms | 37.031 (36.905–37.418, sd 0.2673, n 3) | 40.899 (40.313–42.294, sd 1.0177, n 3) | 36.629 (36.051–37.462, sd 0.7093, n 3) |

| Component (retained, uncached build) | Baseline MB | Intern MB | Candidate MB |
| :--- | ---: | ---: | ---: |
| documents_raw_text | 15.2 | 15.2 | 15.2 |
| documents_metadata | 16.6 | 16.6 | 16.6 |
| semantic_feature_cache | 1064.9 | 421.8 | 172.3 |
| semantic_vocabulary_idf_matrix | 0.9 | 0.9 | 0.9 |
| lexical_term_cache | 98.6 | 98.6 | 98.6 |
| lexical_index_rest | 106.1 | 106.1 | 106.1 |
| abstainer | 109.6 | 109.6 | 109.6 |
| function_graph | 76.9 | 75.2 | 76.9 |
| repo_graph | 16.5 | 16.5 | 16.5 |
| engine_rest | 0.3 | 0.3 | 0.3 |

Excluded, failed or aborted phases: none
