# Tables (generated from aggregate.json and confidence_intervals.json)

## overall (queries = 345, repositories = 25)

| System | MRR | Recall@5 | Recall@10 | Recall@20 |
| :--- | :---: | :---: | :---: | :---: |
| RepoNeedle, fragment input | 0.2379 | 0.3061 | 0.4407 | 0.5803 |
| RepoNeedle, whole-file input | 0.2789 | 0.4270 | 0.5862 | 0.7042 |
| BM25, fragment input (file unit) | 0.1439 | 0.1650 | 0.2389 | 0.3604 |
| BM25, whole-file input (file unit) | 0.1717 | 0.2290 | 0.3498 | 0.5138 |
| BM25, all chunks → file by max (official baseline) | 0.1520 | 0.1899 | 0.3034 | 0.4452 |

| Packed context (CUD-Pack, 8,000 tokens) | Files packed | Utilisation | Gold coverage | Queries with ≥1 gold packed | Unselected files |
| :--- | :---: | :---: | :---: | :---: | :---: |
| fragment input | 8.9 | 99.6% | 38.3% | 45.8% | 1615 (no positions assigned) |
| wholefile input | 11.7 | 99.5% | 59.8% | 68.4% | 1612 (no positions assigned) |

| Comparison (paired, repo-clustered 95% CI) | Metric | Mean Δ | W / T / L | 95% CI | CI excludes 0 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Representation effect on RepoNeedle | mrr | +0.0410 | 165 / 73 / 107 | [+0.0007, +0.1042] | **yes** |
| Representation effect on RepoNeedle | recall@5 | +0.1209 | 66 / 261 / 18 | [+0.0503, +0.2422] | **yes** |
| Representation effect on RepoNeedle | recall@10 | +0.1455 | 76 / 257 / 12 | [+0.0725, +0.2684] | **yes** |
| Representation effect on RepoNeedle | recall@20 | +0.1239 | 68 / 265 / 12 | [+0.0572, +0.2430] | **yes** |
| Representation effect on BM25 | mrr | +0.0277 | 191 / 37 / 117 | [+0.0080, +0.0500] | **yes** |
| Representation effect on BM25 | recall@5 | +0.0640 | 50 / 277 / 18 | [+0.0270, +0.0992] | **yes** |
| Representation effect on BM25 | recall@10 | +0.1109 | 64 / 266 / 15 | [+0.0624, +0.1616] | **yes** |
| Representation effect on BM25 | recall@20 | +0.1534 | 78 / 252 / 15 | [+0.1142, +0.2200] | **yes** |
| RepoNeedle vs BM25, matched fragment input | mrr | +0.0940 | 239 / 33 / 73 | [+0.0570, +0.1201] | **yes** |
| RepoNeedle vs BM25, matched fragment input | recall@5 | +0.1412 | 76 / 249 / 20 | [+0.0785, +0.1873] | **yes** |
| RepoNeedle vs BM25, matched fragment input | recall@10 | +0.2018 | 96 / 228 / 21 | [+0.1203, +0.2651] | **yes** |
| RepoNeedle vs BM25, matched fragment input | recall@20 | +0.2199 | 107 / 218 / 20 | [+0.1278, +0.2938] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | mrr | +0.1073 | 233 / 28 / 84 | [+0.0647, +0.1596] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | recall@5 | +0.1980 | 100 / 218 / 27 | [+0.0952, +0.3102] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | recall@10 | +0.2364 | 116 / 196 / 33 | [+0.1152, +0.3551] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | recall@20 | +0.1904 | 97 / 226 / 22 | [+0.1114, +0.2715] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | mrr | +0.1269 | 250 / 20 / 75 | [+0.0921, +0.1671] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@5 | +0.2371 | 114 / 210 / 21 | [+0.1325, +0.3180] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@10 | +0.2828 | 135 / 180 / 30 | [+0.1650, +0.3681] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@20 | +0.2590 | 127 / 193 / 25 | [+0.1737, +0.3242] | **yes** |

| Latency per query (ms, 4 concurrent shards) | Mean | p50 |
| :--- | :---: | :---: |
| rn_fragment_retrieve | 549.2 | 222.1 |
| rn_wholefile_retrieve | 1368.4 | 498.5 |
| bm25_chunks | 1140.9 | 178.6 |
| bm25_fragment | 74.9 | 18.5 |
| bm25_wholefile | 93.1 | 16.6 |

## comment2context (queries = 80, repositories = 18)

| System | MRR | Recall@5 | Recall@10 | Recall@20 |
| :--- | :---: | :---: | :---: | :---: |
| RepoNeedle, fragment input | 0.1857 | 0.1646 | 0.2250 | 0.3146 |
| RepoNeedle, whole-file input | 0.2037 | 0.2458 | 0.3521 | 0.4896 |
| BM25, fragment input (file unit) | 0.1875 | 0.1875 | 0.2542 | 0.3563 |
| BM25, whole-file input (file unit) | 0.2063 | 0.2812 | 0.4333 | 0.5792 |
| BM25, all chunks → file by max (official baseline) | 0.1974 | 0.2146 | 0.4042 | 0.5292 |

| Packed context (CUD-Pack, 8,000 tokens) | Files packed | Utilisation | Gold coverage | Queries with ≥1 gold packed | Unselected files |
| :--- | :---: | :---: | :---: | :---: | :---: |
| fragment input | 10.1 | 99.5% | 19.4% | 32.5% | 2303 (no positions assigned) |
| wholefile input | 11.0 | 99.3% | 35.8% | 51.2% | 2302 (no positions assigned) |

| Comparison (paired, repo-clustered 95% CI) | Metric | Mean Δ | W / T / L | 95% CI | CI excludes 0 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Representation effect on RepoNeedle | mrr | +0.0180 | 43 / 9 / 28 | [-0.0362, +0.0772] | no |
| Representation effect on RepoNeedle | recall@5 | +0.0813 | 14 / 61 / 5 | [+0.0199, +0.1562] | **yes** |
| Representation effect on RepoNeedle | recall@10 | +0.1271 | 19 / 58 / 3 | [+0.0625, +0.2180] | **yes** |
| Representation effect on RepoNeedle | recall@20 | +0.1750 | 24 / 53 / 3 | [+0.0915, +0.2909] | **yes** |
| Representation effect on BM25 | mrr | +0.0188 | 43 / 9 / 28 | [-0.0289, +0.0749] | no |
| Representation effect on BM25 | recall@5 | +0.0938 | 18 / 55 / 7 | [-0.0014, +0.1902] | no |
| Representation effect on BM25 | recall@10 | +0.1792 | 24 / 52 / 4 | [+0.0682, +0.2868] | **yes** |
| Representation effect on BM25 | recall@20 | +0.2229 | 26 / 51 / 3 | [+0.1039, +0.3682] | **yes** |
| RepoNeedle vs BM25, matched fragment input | mrr | -0.0018 | 35 / 13 / 32 | [-0.0329, +0.0399] | no |
| RepoNeedle vs BM25, matched fragment input | recall@5 | -0.0229 | 4 / 69 / 7 | [-0.0601, +0.0084] | no |
| RepoNeedle vs BM25, matched fragment input | recall@10 | -0.0292 | 3 / 68 / 9 | [-0.0756, +0.0282] | no |
| RepoNeedle vs BM25, matched fragment input | recall@20 | -0.0417 | 7 / 61 / 12 | [-0.1240, +0.0515] | no |
| RepoNeedle vs BM25, matched whole-file input | mrr | -0.0026 | 32 / 10 / 38 | [-0.0297, +0.0337] | no |
| RepoNeedle vs BM25, matched whole-file input | recall@5 | -0.0354 | 7 / 59 / 14 | [-0.1205, +0.0647] | no |
| RepoNeedle vs BM25, matched whole-file input | recall@10 | -0.0813 | 7 / 54 / 19 | [-0.1594, +0.0287] | no |
| RepoNeedle vs BM25, matched whole-file input | recall@20 | -0.0896 | 6 / 60 / 14 | [-0.1779, -0.0056] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | mrr | +0.0063 | 38 / 12 / 30 | [-0.0481, +0.0576] | no |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@5 | +0.0312 | 11 / 61 / 8 | [-0.0316, +0.0786] | no |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@10 | -0.0521 | 13 / 49 / 18 | [-0.1952, +0.0675] | no |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@20 | -0.0396 | 14 / 49 / 17 | [-0.1961, +0.1120] | no |

| Latency per query (ms, 4 concurrent shards) | Mean | p50 |
| :--- | :---: | :---: |
| rn_fragment_retrieve | 411.0 | 232.5 |
| rn_wholefile_retrieve | 1049.3 | 635.5 |
| bm25_chunks | 1587.8 | 361.4 |
| bm25_fragment | 88.4 | 33.1 |
| bm25_wholefile | 85.2 | 33.5 |

## code2test (queries = 106, repositories = 12)

| System | MRR | Recall@5 | Recall@10 | Recall@20 |
| :--- | :---: | :---: | :---: | :---: |
| RepoNeedle, fragment input | 0.2736 | 0.3918 | 0.5742 | 0.6434 |
| RepoNeedle, whole-file input | 0.3556 | 0.4818 | 0.6579 | 0.7698 |
| BM25, fragment input (file unit) | 0.0656 | 0.0770 | 0.1462 | 0.2594 |
| BM25, whole-file input (file unit) | 0.1160 | 0.1336 | 0.2453 | 0.3381 |
| BM25, all chunks → file by max (official baseline) | 0.1057 | 0.1305 | 0.2186 | 0.3066 |

| Packed context (CUD-Pack, 8,000 tokens) | Files packed | Utilisation | Gold coverage | Queries with ≥1 gold packed | Unselected files |
| :--- | :---: | :---: | :---: | :---: | :---: |
| fragment input | 9.0 | 99.6% | 51.8% | 58.5% | 2260 (no positions assigned) |
| wholefile input | 12.3 | 99.4% | 68.3% | 74.5% | 2257 (no positions assigned) |

| Comparison (paired, repo-clustered 95% CI) | Metric | Mean Δ | W / T / L | 95% CI | CI excludes 0 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Representation effect on RepoNeedle | mrr | +0.0821 | 52 / 23 / 31 | [+0.0098, +0.1417] | **yes** |
| Representation effect on RepoNeedle | recall@5 | +0.0899 | 19 / 80 / 7 | [+0.0092, +0.1560] | **yes** |
| Representation effect on RepoNeedle | recall@10 | +0.0836 | 18 / 82 / 6 | [+0.0299, +0.1356] | **yes** |
| Representation effect on RepoNeedle | recall@20 | +0.1264 | 22 / 82 / 2 | [+0.0790, +0.1785] | **yes** |
| Representation effect on BM25 | mrr | +0.0504 | 63 / 3 / 40 | [+0.0150, +0.0895] | **yes** |
| Representation effect on BM25 | recall@5 | +0.0566 | 13 / 89 / 4 | [-0.0063, +0.1292] | no |
| Representation effect on BM25 | recall@10 | +0.0991 | 16 / 87 / 3 | [+0.0129, +0.2143] | **yes** |
| Representation effect on BM25 | recall@20 | +0.0786 | 15 / 86 / 5 | [+0.0352, +0.1317] | **yes** |
| RepoNeedle vs BM25, matched fragment input | mrr | +0.2080 | 97 / 2 / 7 | [+0.1672, +0.2511] | **yes** |
| RepoNeedle vs BM25, matched fragment input | recall@5 | +0.3148 | 45 / 56 / 5 | [+0.2033, +0.4207] | **yes** |
| RepoNeedle vs BM25, matched fragment input | recall@10 | +0.4280 | 55 / 50 / 1 | [+0.2936, +0.5545] | **yes** |
| RepoNeedle vs BM25, matched fragment input | recall@20 | +0.3840 | 49 / 56 / 1 | [+0.2544, +0.4880] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | mrr | +0.2397 | 92 / 5 / 9 | [+0.1783, +0.2994] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | recall@5 | +0.3481 | 45 / 60 / 1 | [+0.2401, +0.4401] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | recall@10 | +0.4126 | 52 / 51 / 3 | [+0.2880, +0.5133] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | recall@20 | +0.4318 | 54 / 52 / 0 | [+0.3207, +0.5229] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | mrr | +0.2500 | 92 / 4 / 10 | [+0.1694, +0.3149] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@5 | +0.3513 | 47 / 56 / 3 | [+0.2176, +0.4684] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@10 | +0.4393 | 53 / 51 / 2 | [+0.3015, +0.5616] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@20 | +0.4632 | 59 / 46 / 1 | [+0.3373, +0.5726] | **yes** |

| Latency per query (ms, 4 concurrent shards) | Mean | p50 |
| :--- | :---: | :---: |
| rn_fragment_retrieve | 867.6 | 201.0 |
| rn_wholefile_retrieve | 2410.4 | 330.4 |
| bm25_chunks | 1464.5 | 278.0 |
| bm25_fragment | 78.7 | 27.2 |
| bm25_wholefile | 75.2 | 24.6 |

## trace2code (queries = 101, repositories = 7)

| System | MRR | Recall@5 | Recall@10 | Recall@20 |
| :--- | :---: | :---: | :---: | :---: |
| RepoNeedle, fragment input | 0.2577 | 0.2855 | 0.4538 | 0.6782 |
| RepoNeedle, whole-file input | 0.2885 | 0.5050 | 0.7046 | 0.8300 |
| BM25, fragment input (file unit) | 0.1432 | 0.1535 | 0.2277 | 0.3927 |
| BM25, whole-file input (file unit) | 0.1476 | 0.2079 | 0.3119 | 0.6089 |
| BM25, all chunks → file by max (official baseline) | 0.1638 | 0.2228 | 0.3218 | 0.4934 |

| Packed context (CUD-Pack, 8,000 tokens) | Files packed | Utilisation | Gold coverage | Queries with ≥1 gold packed | Unselected files |
| :--- | :---: | :---: | :---: | :---: | :---: |
| fragment input | 8.1 | 99.7% | 35.5% | 37.6% | 248 (no positions assigned) |
| wholefile input | 12.1 | 99.6% | 70.8% | 75.2% | 244 (no positions assigned) |

| Comparison (paired, repo-clustered 95% CI) | Metric | Mean Δ | W / T / L | 95% CI | CI excludes 0 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Representation effect on RepoNeedle | mrr | +0.0307 | 50 / 16 / 35 | [-0.0658, +0.2125] | no |
| Representation effect on RepoNeedle | recall@5 | +0.2195 | 28 / 68 / 5 | [+0.0455, +0.5880] | **yes** |
| Representation effect on RepoNeedle | recall@10 | +0.2508 | 31 / 67 / 3 | [+0.0000, +0.5914] | no |
| Representation effect on RepoNeedle | recall@20 | +0.1518 | 20 / 76 / 5 | [-0.0097, +0.4725] | no |
| Representation effect on BM25 | mrr | +0.0043 | 58 / 11 / 32 | [-0.0283, +0.0858] | no |
| Representation effect on BM25 | recall@5 | +0.0545 | 10 / 88 / 3 | [+0.0311, +0.1875] | **yes** |
| Representation effect on BM25 | recall@10 | +0.0842 | 14 / 83 / 4 | [+0.0517, +0.2500] | **yes** |
| Representation effect on BM25 | recall@20 | +0.2162 | 27 / 70 / 4 | [+0.1292, +0.3636] | **yes** |
| RepoNeedle vs BM25, matched fragment input | mrr | +0.1145 | 79 / 9 / 13 | [-0.0396, +0.1619] | no |
| RepoNeedle vs BM25, matched fragment input | recall@5 | +0.1320 | 16 / 82 / 3 | [-0.0106, +0.1782] | no |
| RepoNeedle vs BM25, matched fragment input | recall@10 | +0.2261 | 28 / 69 / 4 | [+0.1351, +0.2693] | **yes** |
| RepoNeedle vs BM25, matched fragment input | recall@20 | +0.2855 | 34 / 64 / 3 | [+0.1000, +0.3373] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | mrr | +0.1409 | 80 / 8 / 13 | [-0.0344, +0.2275] | no |
| RepoNeedle vs BM25, matched whole-file input | recall@5 | +0.2970 | 37 / 56 / 8 | [-0.1053, +0.5914] | no |
| RepoNeedle vs BM25, matched whole-file input | recall@10 | +0.3927 | 45 / 53 / 3 | [-0.0476, +0.6505] | no |
| RepoNeedle vs BM25, matched whole-file input | recall@20 | +0.2211 | 27 / 71 / 3 | [-0.0358, +0.4056] | no |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | mrr | +0.1246 | 76 / 2 / 23 | [+0.0375, +0.2079] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@5 | +0.2822 | 37 / 56 / 8 | [-0.1190, +0.4615] | no |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@10 | +0.3828 | 45 / 51 / 5 | [+0.0000, +0.5222] | no |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@20 | +0.3366 | 38 / 60 / 3 | [+0.1143, +0.4560] | **yes** |

| Latency per query (ms, 4 concurrent shards) | Mean | p50 |
| :--- | :---: | :---: |
| rn_fragment_retrieve | 242.3 | 177.6 |
| rn_wholefile_retrieve | 553.7 | 412.3 |
| bm25_chunks | 84.6 | 43.2 |
| bm25_fragment | 7.0 | 3.3 |
| bm25_wholefile | 7.1 | 4.3 |

## edit2ripple (queries = 58, repositories = 10)

| System | MRR | Recall@5 | Recall@10 | Recall@20 |
| :--- | :---: | :---: | :---: | :---: |
| RepoNeedle, fragment input | 0.2104 | 0.3807 | 0.4713 | 0.6609 |
| RepoNeedle, whole-file input | 0.2259 | 0.4411 | 0.5718 | 0.6609 |
| BM25, fragment input (file unit) | 0.2283 | 0.3147 | 0.4066 | 0.4943 |
| BM25, whole-file input (file unit) | 0.2676 | 0.3678 | 0.4914 | 0.5790 |
| BM25, all chunks → file by max (official baseline) | 0.1536 | 0.2069 | 0.2874 | 0.4986 |

| Packed context (CUD-Pack, 8,000 tokens) | Files packed | Utilisation | Gold coverage | Queries with ≥1 gold packed | Unselected files |
| :--- | :---: | :---: | :---: | :---: | :---: |
| fragment input | 8.3 | 99.5% | 44.5% | 55.2% | 1869 (no positions assigned) |
| wholefile input | 10.7 | 99.5% | 58.3% | 69.0% | 1866 (no positions assigned) |

| Comparison (paired, repo-clustered 95% CI) | Metric | Mean Δ | W / T / L | 95% CI | CI excludes 0 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Representation effect on RepoNeedle | mrr | +0.0155 | 20 / 25 / 13 | [+0.0010, +0.0294] | **yes** |
| Representation effect on RepoNeedle | recall@5 | +0.0603 | 5 / 52 / 1 | [+0.0072, +0.1014] | **yes** |
| Representation effect on RepoNeedle | recall@10 | +0.1006 | 8 / 50 / 0 | [+0.0370, +0.1852] | **yes** |
| Representation effect on RepoNeedle | recall@20 | +0.0000 | 2 / 54 / 2 | [-0.0660, +0.0510] | no |
| Representation effect on BM25 | mrr | +0.0393 | 27 / 14 / 17 | [-0.0131, +0.0852] | no |
| Representation effect on BM25 | recall@5 | +0.0532 | 9 / 45 / 4 | [-0.0519, +0.1317] | no |
| Representation effect on BM25 | recall@10 | +0.0848 | 10 / 44 / 4 | [-0.0224, +0.1640] | no |
| Representation effect on BM25 | recall@20 | +0.0848 | 10 / 45 / 3 | [+0.0072, +0.1389] | **yes** |
| RepoNeedle vs BM25, matched fragment input | mrr | -0.0179 | 28 / 9 / 21 | [-0.0472, +0.0245] | no |
| RepoNeedle vs BM25, matched fragment input | recall@5 | +0.0661 | 11 / 42 / 5 | [-0.0023, +0.1471] | no |
| RepoNeedle vs BM25, matched fragment input | recall@10 | +0.0647 | 10 / 41 / 7 | [-0.0076, +0.1358] | no |
| RepoNeedle vs BM25, matched fragment input | recall@20 | +0.1667 | 17 / 37 / 4 | [+0.0861, +0.2519] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | mrr | -0.0417 | 29 / 5 / 24 | [-0.1095, +0.0466] | no |
| RepoNeedle vs BM25, matched whole-file input | recall@5 | +0.0733 | 11 / 43 / 4 | [-0.0174, +0.2035] | no |
| RepoNeedle vs BM25, matched whole-file input | recall@10 | +0.0805 | 12 / 38 / 8 | [+0.0108, +0.1827] | **yes** |
| RepoNeedle vs BM25, matched whole-file input | recall@20 | +0.0819 | 10 / 43 / 5 | [+0.0145, +0.1771] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | mrr | +0.0723 | 44 / 2 / 12 | [+0.0317, +0.1311] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@5 | +0.2342 | 19 / 37 / 2 | [+0.1037, +0.3316] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@10 | +0.2845 | 24 / 29 / 5 | [+0.1758, +0.4232] | **yes** |
| RepoNeedle whole-file vs official chunk BM25 (different BM25 unit) | recall@20 | +0.1624 | 16 / 38 / 4 | [+0.0570, +0.2926] | **yes** |

| Latency per query (ms, 4 concurrent shards) | Mean | p50 |
| :--- | :---: | :---: |
| rn_fragment_retrieve | 692.4 | 355.5 |
| rn_wholefile_retrieve | 1323.2 | 753.8 |
| bm25_chunks | 1772.6 | 352.5 |
| bm25_fragment | 168.0 | 27.4 |
| bm25_wholefile | 286.2 | 27.1 |
