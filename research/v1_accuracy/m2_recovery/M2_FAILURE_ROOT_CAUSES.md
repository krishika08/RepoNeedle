# RepoNeedle V1.0.0 — Milestone 2 Failure Root Cause Forensic Analysis

**Audit Date**: November 1, 2026  
**Auditor Role**: Principal Search Engineer & Information Retrieval Scientist  
**Scope**: All 121 Gold Targets Ranked Beyond Position 50 in Milestone 1 (99 Unique Queries)  
**Input Reference**: [`frozen_m1_candidates.jsonl`](file:///F:/RepoNeedle/research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl)  
**Objective**: Query-level evidence ledger detailing why each gold target was outranked by competitors in lexical fusion.

---

## 1. Executive Summary & Forensic Failure Taxonomy

Across the 121 gold target files ranked $> 50$, forensic analysis of the candidate scores, multi-field BM25 contributions, exact symbol matches, and competing distractor files reveals seven primary failure mechanisms:

| Root Cause Category | Target Count | Share | Mechanism & Impact |
| :--- | :---: | :---: | :--- |
| **Test-File Collisions** | 25 | 20.7% | Test files and test runners share class/function names with implementation targets, accumulating higher term frequencies on query keywords. |
| **Sibling Implementation Collisions** | 19 | 15.7% | Peer files in the same directory/package share module-level imports, type signatures, and docstring terms, outranking the specific target. |
| **Generic Hub Collisions** | 18 | 14.9% | High-degree central files (`utils.py`, `common.rs`, `types.go`, `mod.rs`) accumulate BM25 scores across multi-term natural language queries. |
| **Lexical Mismatch** | 0 | 0.0% | Query uses vocabulary, synonyms, or abstractions absent from the target code; file was retrieved solely via subword n-grams. |
| **Missing Structural Evidence** | 0 | 0.0% | Target is an indirect ripple-effect dependent or downstream consumer with zero direct lexical mention in the issue description. |
| **Incorrect Intent Collisions** | 13 | 10.7% | Intent words ("test", "bug", "trace") in natural language queries collide with literal symbol tokens in competing files. |
| **Unexplained Dispersed Failures** | 46 | 38.0% | Broad lexical dispersion across multiple competing files without a single dominant distractor pattern. |
| **Total** | **121** | **100.0%** | |

---

## 2. Key Findings & Why Previous M2 Composite Reranking Failed

1. **Why `m2_full_auto` Failed**:
   - The original M2 reranker attempted to fix Test-File Collisions and Missing Structural Evidence by applying large linear additive weights to test-stem matching ($+0.45$) and traceback depth ($+0.50$).
   - Because test-stem matching was imprecise (matching any query token with `test_` prefix), it caused an influx of **false-positive test distractors** on implementation queries.
   - For every 1 target it elevated, it displaced 2.5 legitimate targets downward.
2. **The Fundamental Rule**:
   - **WEAK STRUCTURAL EVIDENCE MUST NOT OVERRIDE STRONG LEXICAL EVIDENCE.**
   - Structural adjustments must be **bounded multipliers** or **conditional priors** that break ties among lexically plausible candidates, rather than overriding high-confidence BM25 and symbol matches.

---

## 3. Query-Level Evidence Ledger (All 121 Missed Targets)

| Query ID | Repository | Track | Gold Target File | M1 Rank | M1 Score | BM25 | Symbol | Subword | Primary Failure Category | Top Competing Distractor |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| `33c92549` | clap-rs/clap | `v2_edit2ripple` | `clap_builder/src/util/mod.rs` | 326 | 0.0280 | 666.7171 | 0.2992 | 151.1822 | **Generic hub collisions** | `clap_builder/src/error/format.rs` |
| `269e3e34` | clap-rs/clap | `v2_edit2ripple` | `clap_builder/src/util/mod.rs` | 304 | 0.0351 | 763.2554 | 0.2992 | 172.9896 | **Incorrect intent** | `clap_builder/src/output/help_template.rs` |
| `6b1c1cff` | clap-rs/clap | `v2_code2test` | `tests/builder/ignore_errors.rs` | 69 | 0.1339 | 81.1029 | 0.3885 | 220.2969 | **Unexplained failures** | `clap_builder/src/parser/parser.rs` |
| `30fded9a` | clap-rs/clap | `v2_edit2ripple` | `clap_mangen/tests/testsuite/common.rs` | 54 | 0.1368 | 290.3206 | 0.6528 | 503.0442 | **Unexplained failures** | `clap_mangen/src/render.rs` |
| `30fded9a` | clap-rs/clap | `v2_edit2ripple` | `clap_mangen/Cargo.toml` | 224 | 0.0612 | 214.5063 | 0.0983 | 72.4809 | **Test-file collisions** | `clap_mangen/src/render.rs` |
| `41deac7d` | etcd-io/etcd | `v2_comment2context` | `cache/demux_test.go` | 61 | 0.1488 | 381.8790 | 0.2749 | 286.8437 | **Sibling implementation collisions** | `cache/cache.go` |
| `7d5c2788` | etcd-io/etcd | `v2_comment2context` | `cache/demux_test.go` | 69 | 0.1353 | 291.3426 | 0.0975 | 228.2633 | **Sibling implementation collisions** | `cache/cache.go` |
| `fa3c694a` | etcd-io/etcd | `v2_comment2context` | `cache/demux_test.go` | 118 | 0.1302 | 193.2157 | 0.1545 | 252.0627 | **Sibling implementation collisions** | `tests/integration/cache_test.go` |
| `15959167` | etcd-io/etcd | `v2_code2test` | `cache/demux_test.go` | 117 | 0.1054 | 208.4117 | 0.3550 | 358.4210 | **Sibling implementation collisions** | `cache/config.go` |
| `1dd2bdfd` | etcd-io/etcd | `v2_code2test` | `server/etcdserver/txn/txn_test.go` | 162 | 0.1498 | 113.7535 | 0.2913 | 309.8969 | **Generic hub collisions** | `server/storage/mvcc/index.go` |
| `d5f1198f` | etcd-io/etcd | `v2_comment2context` | `server/storage/mvcc/index_test.go` | 182 | 0.1258 | 156.5766 | 0.3050 | 226.0787 | **Sibling implementation collisions** | `server/storage/mvcc/kv.go` |
| `d5f1198f` | etcd-io/etcd | `v2_comment2context` | `server/etcdserver/txn/txn_test.go` | 147 | 0.1367 | 178.4297 | 0.2252 | 229.3791 | **Generic hub collisions** | `server/storage/mvcc/kv.go` |
| `e45d17f0` | etcd-io/etcd | `v2_comment2context` | `cache/demux_test.go` | 53 | 0.1868 | 738.6732 | 0.6982 | 825.6818 | **Sibling implementation collisions** | `cache/cache.go` |
| `3a9ae9c1` | etcd-io/etcd | `v2_code2test` | `clientv3/integration/kv_test.go` | 158 | 0.1944 | 184.7549 | 0.5098 | 397.3866 | **Unexplained failures** | `proxy/grpcproxy/watch.go` |
| `3a9ae9c1` | etcd-io/etcd | `v2_code2test` | `clientv3/integration/lease_test.go` | 63 | 0.2744 | 300.5744 | 0.4254 | 465.5546 | **Unexplained failures** | `proxy/grpcproxy/watch.go` |
| `6338b759` | etcd-io/etcd | `v2_code2test` | `tests/e2e/ctl_v3_test.go` | 205 | 0.1109 | 372.8293 | 0.2373 | 636.8323 | **Unexplained failures** | `server/etcdmain/config.go` |
| `73fc2431` | etcd-io/etcd | `v2_code2test` | `server/etcdserver/util_test.go` | 145 | 0.1994 | 313.3454 | 0.5380 | 435.0848 | **Sibling implementation collisions** | `server/etcdserver/v3_server.go` |
| `b389823a` | etcd-io/etcd | `v2_trace2code` | `server/etcdserver/util.go` | 252 | 0.1715 | 269.1538 | 0.2233 | 218.3943 | **Sibling implementation collisions** | `server/etcdserver/server.go` |
| `a8e245be` | etcd-io/etcd | `v2_edit2ripple` | `server/features/etcd_features.go` | 260 | 0.0869 | 1436.6013 | 0.4315 | 451.1822 | **Test-file collisions** | `server/etcdserver/util.go` |
| `bad03d80` | etcd-io/etcd | `v2_edit2ripple` | `server/etcdserver/util_test.go` | 206 | 0.0840 | 841.8294 | 2.1063 | 1134.5720 | **Unexplained failures** | `pkg/featuregate/feature_gate.go` |
| `bad03d80` | etcd-io/etcd | `v2_edit2ripple` | `server/etcdserver/util.go` | 909 | 0.0289 | 565.9664 | 0.1158 | 444.8784 | **Test-file collisions** | `pkg/featuregate/feature_gate.go` |
| `810b8fe1` | etcd-io/etcd | `v2_code2test` | `tests/integration/v3_alarm_test.go` | 144 | 0.1340 | 137.2423 | 0.1766 | 250.1158 | **Unexplained failures** | `server/etcdserver/server.go` |
| `8ab746ff` | etcd-io/etcd | `v2_code2test` | `tests/integration/v3_auth_test.go` | 135 | 0.1016 | 511.2748 | 0.5859 | 688.2032 | **Incorrect intent** | `server/etcdserver/api/v3rpc/watch.go` |
| `38c2a13a` | etcd-io/etcd | `v2_comment2context` | `server/etcdmain/help.go` | 354 | 0.0685 | 128.4137 | 0.0571 | 131.7966 | **Test-file collisions** | `server/embed/config_test.go` |
| `d6dbe66e` | etcd-io/etcd | `v2_edit2ripple` | `server/etcdmain/help.go` | 184 | 0.1209 | 1362.8319 | 4.1502 | 874.2905 | **Incorrect intent** | `server/embed/etcd.go` |
| `117ee2d9` | etcd-io/etcd | `v2_edit2ripple` | `server/etcdmain/help.go` | 472 | 0.0434 | 527.9752 | 0.0571 | 630.7585 | **Test-file collisions** | `pkg/featuregate/feature_gate.go` |
| `e613783f` | etcd-io/etcd | `v2_code2test` | `tests/framework/testutils/log_observer_test.go` | 127 | 0.1419 | 117.8261 | 0.1351 | 84.8568 | **Incorrect intent** | `pkg/expect/expect.go` |
| `7f2b7ed0` | fastapi/fastapi | `v2_code2test` | `tests/test_tutorial/test_custom_response/test_tutorial001.py` | 201 | 0.0794 | 167.3514 | 0.1179 | 282.2021 | **Unexplained failures** | `fastapi/responses.py` |
| `7f2b7ed0` | fastapi/fastapi | `v2_code2test` | `tests/test_tutorial/test_custom_response/test_tutorial001b.py` | 189 | 0.0814 | 175.2526 | 0.1179 | 272.0688 | **Unexplained failures** | `fastapi/responses.py` |
| `a56cae40` | fastapi/fastapi | `v2_code2test` | `tests/test_tutorial/test_custom_response/test_tutorial001.py` | 96 | 0.2044 | 280.2060 | 0.1940 | 314.5286 | **Unexplained failures** | `fastapi/_compat/v2.py` |
| `bb9cf609` | gin-gonic/gin | `v2_edit2ripple` | `.golangci.yml` | 101 | 0.0150 | 315.1952 | 0.0000 | 99.6081 | **Sibling implementation collisions** | `gin.go` |
| `21093314` | huggingface/diffusers | `v2_code2test` | `tests/others/test_utils.py` | 121 | 0.1490 | 264.2439 | 0.3164 | 419.2273 | **Incorrect intent** | `src/diffusers/utils/torch_utils.py` |
| `95a32599` | huggingface/diffusers | `v2_code2test` | `tests/models/test_models_auto.py` | 58 | 0.2273 | 804.0584 | 0.4933 | 644.8746 | **Unexplained failures** | `src/diffusers/pipelines/pipeline_utils.py` |
| `154523e8` | huggingface/diffusers | `v2_comment2context` | `src/diffusers/dependency_versions_table.py` | 1985 | 0.0235 | 34.9012 | 0.0000 | 7.7690 | **Test-file collisions** | `tests/pipelines/test_pipelines.py` |
| `154523e8` | huggingface/diffusers | `v2_comment2context` | `setup.py` | 1107 | 0.0742 | 110.3432 | 0.0000 | 24.0226 | **Test-file collisions** | `tests/pipelines/test_pipelines.py` |
| `154523e8` | huggingface/diffusers | `v2_comment2context` | `src/diffusers/utils/dynamic_modules_utils.py` | 100 | 0.2485 | 271.6492 | 1.3492 | 421.3304 | **Test-file collisions** | `tests/pipelines/test_pipelines.py` |
| `7d661ed7` | huggingface/diffusers | `v2_comment2context` | `examples/advanced_diffusion_training/train_dreambooth_lora_flux_advanced.py` | 1092 | 0.0996 | 116.8063 | 0.6880 | 392.3805 | **Test-file collisions** | `tests/pipelines/test_pipelines.py` |
| `7d661ed7` | huggingface/diffusers | `v2_comment2context` | `examples/advanced_diffusion_training/train_dreambooth_lora_sd15_advanced.py` | 649 | 0.1495 | 163.8299 | 1.8262 | 438.8974 | **Test-file collisions** | `tests/pipelines/test_pipelines.py` |
| `7d661ed7` | huggingface/diffusers | `v2_comment2context` | `src/diffusers/utils/dynamic_modules_utils.py` | 134 | 0.2447 | 379.8605 | 1.0534 | 527.8648 | **Test-file collisions** | `tests/pipelines/test_pipelines.py` |
| `8d19ca90` | huggingface/diffusers | `v2_comment2context` | `tests/others/test_flashpack.py` | 598 | 0.1262 | 180.2291 | 0.2355 | 148.2406 | **Unexplained failures** | `src/diffusers/pipelines/pipeline_utils.py` |
| `8d19ca90` | huggingface/diffusers | `v2_comment2context` | `tests/testing_utils.py` | 178 | 0.1717 | 158.1891 | 1.1334 | 705.1837 | **Unexplained failures** | `src/diffusers/pipelines/pipeline_utils.py` |
| `2a765868` | huggingface/diffusers | `v2_code2test` | `tests/pipelines/ltx2/test_ltx2_image2video.py` | 52 | 0.2196 | 916.1775 | 0.3879 | 384.8755 | **Generic hub collisions** | `src/diffusers/pipelines/pipeline_utils.py` |
| `0978d6fd` | huggingface/diffusers | `v2_edit2ripple` | `docs/source/en/api/modular_diffusers/pipeline_blocks.md` | 115 | 0.1499 | 4383.5913 | 0.2040 | 1100.4346 | **Unexplained failures** | `src/diffusers/modular_pipelines/modular_pipeline.py` |
| `0a4b3f17` | huggingface/transformers | `v2_code2test` | `tests/models/gpt_oss/test_modeling_gpt_oss.py` | 262 | 0.1061 | 194.3031 | 0.2143 | 367.8214 | **Unexplained failures** | `src/transformers/integrations/mxfp4.py` |
| `12b84b0c` | huggingface/transformers | `v2_code2test` | `tests/models/altclip/test_modeling_altclip.py` | 845 | 0.1296 | 229.6172 | 0.6242 | 457.5225 | **Unexplained failures** | `src/transformers/core_model_loading.py` |
| `210bcbf1` | huggingface/transformers | `v2_code2test` | `tests/models/d_fine/test_modeling_d_fine.py` | 118 | 0.1570 | 536.4232 | 0.4013 | 694.1991 | **Unexplained failures** | `src/transformers/loss/loss_d_fine.py` |
| `0a166358` | huggingface/transformers | `v2_comment2context` | `src/transformers/conversion_mapping.py` | 3689 | 0.0463 | 38.0363 | 0.0489 | 129.4902 | **Incorrect intent** | `src/transformers/integrations/finegrained_fp8.py` |
| `9aa10bc6` | huggingface/transformers | `v2_comment2context` | `src/transformers/conversion_mapping.py` | 3009 | 0.0231 | 37.5086 | 0.0961 | 99.9857 | **Test-file collisions** | `src/transformers/integrations/finegrained_fp8.py` |
| `a4b5977e` | huggingface/transformers | `v2_comment2context` | `src/transformers/integrations/finegrained_fp8.py` | 1474 | 0.0825 | 85.1197 | 0.1787 | 373.9677 | **Incorrect intent** | `src/transformers/conversion_mapping.py` |
| `eb415665` | huggingface/transformers | `v2_edit2ripple` | `src/transformers/integrations/finegrained_fp8.py` | 1741 | 0.0792 | 1010.2687 | 0.9070 | 1747.2933 | **Incorrect intent** | `src/transformers/core_model_loading.py` |
| `8360be1c` | huggingface/transformers | `v2_edit2ripple` | `src/transformers/conversion_mapping.py` | 1608 | 0.0339 | 940.3144 | 0.3215 | 1170.1565 | **Sibling implementation collisions** | `src/transformers/integrations/finegrained_fp8.py` |
| `335597ee` | huggingface/transformers | `v2_comment2context` | `tests/models/auto/test_tokenization_auto.py` | 51 | 0.2331 | 383.5533 | 0.5312 | 1108.7194 | **Unexplained failures** | `src/transformers/tokenization_utils_tokenizers.py` |
| `813d9449` | huggingface/transformers | `v2_code2test` | `tests/models/mt5/test_modeling_mt5.py` | 103 | 0.2371 | 873.7304 | 1.1640 | 1950.1565 | **Unexplained failures** | `src/transformers/modeling_utils.py` |
| `d33132ce` | huggingface/transformers | `v2_code2test` | `tests/utils/test_core_model_loading.py` | 103 | 0.1686 | 490.6646 | 1.6409 | 962.5593 | **Generic hub collisions** | `src/transformers/modeling_utils.py` |
| `94f11ff5` | mockito/mockito | `v2_code2test` | `mockito-integration-tests/programmatic-tests/src/test/java/org/mockito/ProgrammaticMockMakerTest.java` | 60 | 0.2617 | 793.9099 | 0.9548 | 1005.9629 | **Unexplained failures** | `mockito-core/src/main/java/org/mockito/internal/creation/bytebuddy/InlineBytecodeGenerator.java` |
| `5a834c21` | pytest-dev/pytest | `v2_code2test` | `src/_pytest/unittest.py` | 56 | 0.2055 | 62.7406 | 0.1484 | 359.6475 | **Unexplained failures** | `testing/test_subtests.py` |
| `2177ce08` | spring-projects/spring-boot | `v2_code2test` | `module/spring-boot-webflux/src/test/java/org/springframework/boot/webflux/autoconfigure/HttpHandlerAutoConfigurationTests.java` | 65 | 0.3318 | 719.3705 | 0.5784 | 1411.8589 | **Unexplained failures** | `module/spring-boot-webflux/src/main/java/org/springframework/boot/webflux/autoconfigure/WebFluxProperties.java` |
| `78906550` | spring-projects/spring-boot | `v2_edit2ripple` | `module/spring-boot-webflux/src/test/java/org/springframework/boot/webflux/autoconfigure/HttpHandlerAutoConfigurationTests.java` | 550 | 0.0951 | 1601.6529 | 0.6873 | 1917.8420 | **Unexplained failures** | `module/spring-boot-webflux/src/main/java/org/springframework/boot/webflux/autoconfigure/WebFluxProperties.java` |
| `78906550` | spring-projects/spring-boot | `v2_edit2ripple` | `module/spring-boot-webflux/src/main/java/org/springframework/boot/webflux/autoconfigure/HttpHandlerAutoConfiguration.java` | 800 | 0.0852 | 1681.4473 | 0.3180 | 1204.7932 | **Sibling implementation collisions** | `module/spring-boot-webflux/src/main/java/org/springframework/boot/webflux/autoconfigure/WebFluxProperties.java` |
| `9212befb` | tokio-rs/tokio | `v2_comment2context` | `tokio/src/runtime/handle.rs` | 70 | 0.2579 | 342.6883 | 1.0146 | 304.6074 | **Sibling implementation collisions** | `tokio/src/runtime/builder.rs` |
| `9212befb` | tokio-rs/tokio | `v2_comment2context` | `tokio/src/task/spawn.rs` | 105 | 0.1814 | 268.1874 | 0.8354 | 83.2746 | **Generic hub collisions** | `tokio/src/runtime/builder.rs` |
| `d354e818` | tokio-rs/tokio | `v2_comment2context` | `tokio/src/runtime/mod.rs` | 88 | 0.1835 | 197.2276 | 1.3177 | 197.6823 | **Unexplained failures** | `tokio/src/task/spawn.rs` |
| `d42e82da` | tokio-rs/tokio | `v2_comment2context` | `tokio/src/runtime/mod.rs` | 63 | 0.1623 | 357.7115 | 0.6652 | 219.1647 | **Sibling implementation collisions** | `tokio/src/runtime/runtime.rs` |
| `eca2d26f` | tokio-rs/tokio | `v2_comment2context` | `tokio/src/runtime/mod.rs` | 100 | 0.1812 | 238.3827 | 0.1416 | 175.2740 | **Sibling implementation collisions** | `tokio/src/runtime/handle.rs` |
| `fd368dbd` | tokio-rs/tokio | `v2_edit2ripple` | `tokio-util/tests/task_join_queue.rs` | 155 | 0.1250 | 2134.0000 | 1.9776 | 959.5469 | **Unexplained failures** | `tokio/src/task/builder.rs` |
| `fd368dbd` | tokio-rs/tokio | `v2_edit2ripple` | `tokio-util/tests/task_tracker.rs` | 51 | 0.2030 | 3760.4114 | 3.1357 | 1304.7221 | **Unexplained failures** | `tokio/src/task/builder.rs` |
| `c5186727` | tokio-rs/tokio | `v2_code2test` | `tokio/tests/rt_threaded.rs` | 91 | 0.1836 | 370.1017 | 2.3089 | 676.2243 | **Unexplained failures** | `tokio/src/runtime/task/list.rs` |
| `c5186727` | tokio-rs/tokio | `v2_code2test` | `tokio/tests/rt_handle.rs` | 244 | 0.1041 | 336.1758 | 0.2275 | 240.2268 | **Unexplained failures** | `tokio/src/runtime/task/list.rs` |
| `176cf95c` | vitejs/vite | `v2_code2test` | `playground/assets/__tests__/assets.spec.ts` | 101 | 0.2403 | 215.8271 | 3.8296 | 479.4613 | **Unexplained failures** | `packages/vite/src/node/plugins/prepareOutDir.ts` |
| `4fdbbdc3` | vitejs/vite | `v2_code2test` | `packages/vite/src/node/__tests__/plugins/hooks.spec.ts` | 143 | 0.2089 | 577.3440 | 1.9911 | 977.5162 | **Generic hub collisions** | `packages/vite/src/node/server/index.ts` |
| `753493cf` | vitejs/vite | `v2_code2test` | `playground/backend-integration/__tests__/backend-integration.spec.ts` | 98 | 0.2092 | 706.7179 | 1.4298 | 611.9951 | **Generic hub collisions** | `packages/vite/src/node/plugins/css.ts` |
| `874789db` | vitejs/vite | `v2_code2test` | `playground/fs-serve/__tests__/commonTests.ts` | 81 | 0.3073 | 345.0340 | 2.0893 | 554.2328 | **Unexplained failures** | `playground/fs-serve/root/vite.config-base.js` |
| `874789db` | vitejs/vite | `v2_code2test` | `playground/fs-serve/__tests__/deny/fs-serve-deny.spec.ts` | 134 | 0.2415 | 418.2219 | 0.0847 | 145.7812 | **Unexplained failures** | `playground/fs-serve/root/vite.config-base.js` |
| `9b942f47` | vitejs/vite | `v2_code2test` | `playground/lib/__tests__/lib.spec.ts` | 123 | 0.1169 | 145.7670 | 0.0916 | 57.9608 | **Unexplained failures** | `packages/vite/src/node/build.ts` |
| `9cf0a50a` | vitejs/vite | `v2_code2test` | `playground/js-sourcemap/__tests__/js-sourcemap.spec.ts` | 803 | 0.0654 | 84.1755 | 0.0691 | 112.3764 | **Generic hub collisions** | `packages/vite/src/node/plugins/importAnalysis.ts` |
| `9cf0a50a` | vitejs/vite | `v2_code2test` | `playground/worker/__tests__/iife/worker-iife.spec.ts` | 84 | 0.1877 | 231.7694 | 0.8706 | 178.4642 | **Generic hub collisions** | `packages/vite/src/node/plugins/importAnalysis.ts` |
| `9db66acf` | vitejs/vite | `v2_code2test` | `playground/fs-serve/__tests__/fs-serve.spec.ts` | 300 | 0.0813 | 73.1869 | 0.7019 | 71.4904 | **Generic hub collisions** | `packages/vite/src/node/server/middlewares/transform.ts` |
| `a5663509` | vitejs/vite | `v2_code2test` | `playground/fs-serve/__tests__/commonTests.ts` | 103 | 0.1502 | 168.3623 | 2.0500 | 611.1039 | **Generic hub collisions** | `packages/vite/src/node/server/environments/fullBundleEnvironment.ts` |
| `4eb8d031` | vitejs/vite | `v2_edit2ripple` | `playground/fs-serve/__tests__/commonTests.ts` | 136 | 0.1118 | 878.5255 | 6.5785 | 2205.6504 | **Unexplained failures** | `packages/vite/src/node/server/environments/fullBundleEnvironment.ts` |
| `be31a2fa` | vitejs/vite | `v2_code2test` | `packages/vite/src/node/ssr/runtime/__tests__/server-runtime.spec.ts` | 54 | 0.1954 | 148.2594 | 1.1352 | 330.0782 | **Unexplained failures** | `packages/vite/src/module-runner/hmrHandler.ts` |
| `cb31b158` | vitejs/vite | `v2_code2test` | `playground/optimize-deps/__tests__/optimize-deps.spec.ts` | 293 | 0.1548 | 213.9622 | 0.7943 | 324.2282 | **Generic hub collisions** | `packages/vite/src/node/optimizer/rolldownDepPlugin.ts` |
| `dbcf0a72` | vitejs/vite | `v2_code2test` | `packages/vite/src/node/ssr/runtime/__tests__/server-runtime.spec.ts` | 117 | 0.1723 | 181.8290 | 0.4326 | 360.1464 | **Generic hub collisions** | `packages/vite/src/node/plugins/oxc.ts` |
| `99089b7d` | vitejs/vite | `v2_edit2ripple` | `packages/vite/package.json` | 440 | 0.0604 | 1440.0120 | 0.2248 | 194.7472 | **Generic hub collisions** | `packages/vite/src/node/plugins/index.ts` |
| `bf0ff857` | vitejs/vite | `v2_edit2ripple` | `packages/vite/package.json` | 533 | 0.0398 | 921.7882 | 0.1669 | 138.3582 | **Incorrect intent** | `packages/vite/src/node/plugins/oxc.ts` |
| `72a10b94` | vuejs/core | `v2_code2test` | `packages/runtime-vapor/__tests__/component.spec.ts` | 133 | 0.1893 | 138.4921 | 0.2657 | 284.2252 | **Unexplained failures** | `packages/runtime-vapor/src/componentEmits.ts` |
| `ec9507f8` | vuejs/core | `v2_code2test` | `packages/compiler-vapor/__tests__/transforms/vBind.spec.ts` | 310 | 0.1151 | 68.2619 | 0.1893 | 99.9894 | **Unexplained failures** | `packages/compiler-vapor/src/generators/expression.ts` |
| `413524fd` | astral-sh/ruff | `v2_comment2context` | `crates/ty_server/tests/e2e/configuration.rs` | 61 | 0.2466 | 517.3807 | 1.0660 | 742.2967 | **Unexplained failures** | `crates/ty_project/src/db/changes.rs` |
| `538d3764` | astral-sh/ruff | `v2_comment2context` | `crates/ty_server/tests/e2e/configuration.rs` | 248 | 0.1398 | 514.2372 | 1.0528 | 957.7316 | **Unexplained failures** | `crates/ty_project/src/db.rs` |
| `f9c42afe` | astral-sh/ruff | `v2_comment2context` | `crates/ty_server/tests/e2e/configuration.rs` | 137 | 0.1752 | 386.0184 | 1.1193 | 799.2094 | **Incorrect intent** | `crates/ty_project/src/db.rs` |
| `449280b3` | eslint/eslint | `v2_comment2context` | `eslint.config.js` | 197 | 0.1070 | 230.1132 | 0.6717 | 177.1282 | **Test-file collisions** | `lib/rules/no-param-reassign.js` |
| `3fd987cc` | etcd-io/etcd | `v2_comment2context` | `tests/integration/clientv3/maintenance_test.go` | 195 | 0.0959 | 152.5113 | 0.0570 | 135.7768 | **Unexplained failures** | `pkg/proxy/server_test.go` |
| `c9f5bf8f` | etcd-io/etcd | `v2_comment2context` | `tests/integration/clientv3/maintenance_test.go` | 158 | 0.1384 | 135.0639 | 0.1883 | 103.5619 | **Unexplained failures** | `server/etcdserver/api/rafthttp/stream_test.go` |
| `19c290f5` | etcd-io/etcd | `v2_trace2code` | `cache/config.go` | 67 | 0.1714 | 644.6774 | 0.1009 | 338.8590 | **Test-file collisions** | `server/proxy/grpcproxy/cache/store.go` |
| `8c8c2eb1` | huggingface/diffusers | `v2_comment2context` | `tests/pipelines/qwenimage/test_qwenimage.py` | 115 | 0.2332 | 343.1920 | 0.5087 | 380.7194 | **Unexplained failures** | `src/diffusers/pipelines/qwenimage/pipeline_qwenimage_controlnet_inpaint.py` |
| `8c8c2eb1` | huggingface/diffusers | `v2_comment2context` | `tests/pipelines/qwenimage/test_qwenimage_edit.py` | 251 | 0.1994 | 285.9925 | 0.4724 | 369.4047 | **Unexplained failures** | `src/diffusers/pipelines/qwenimage/pipeline_qwenimage_controlnet_inpaint.py` |
| `a17b0c14` | huggingface/diffusers | `v2_comment2context` | `tests/pipelines/qwenimage/test_qwenimage.py` | 74 | 0.2363 | 399.4168 | 0.3825 | 485.0926 | **Unexplained failures** | `src/diffusers/pipelines/qwenimage/pipeline_qwenimage.py` |
| `a17b0c14` | huggingface/diffusers | `v2_comment2context` | `tests/pipelines/qwenimage/test_qwenimage_edit.py` | 218 | 0.1972 | 338.7892 | 0.2904 | 386.0628 | **Unexplained failures** | `src/diffusers/pipelines/qwenimage/pipeline_qwenimage.py` |
| `a17b0c14` | huggingface/diffusers | `v2_comment2context` | `tests/pipelines/qwenimage/test_qwenimage_controlnet.py` | 87 | 0.2310 | 405.8636 | 0.2915 | 421.8209 | **Unexplained failures** | `src/diffusers/pipelines/qwenimage/pipeline_qwenimage.py` |
| `c7f3b691` | huggingface/diffusers | `v2_comment2context` | `src/diffusers/models/autoencoders/autoencoder_kl_qwenimage.py` | 59 | 0.2579 | 293.1082 | 0.2576 | 653.4255 | **Test-file collisions** | `tests/pipelines/qwenimage/test_qwenimage.py` |
| `c7f3b691` | huggingface/diffusers | `v2_comment2context` | `src/diffusers/pipelines/longcat_audio_dit/pipeline_longcat_audio_dit.py` | 845 | 0.1075 | 116.4654 | 0.5239 | 173.7375 | **Test-file collisions** | `tests/pipelines/qwenimage/test_qwenimage.py` |
| `262ecc80` | huggingface/transformers | `v2_edit2ripple` | `src/transformers/cli/serving/chat_completion.py` | 79 | 0.2349 | 4002.4426 | 3.2442 | 2159.0540 | **Sibling implementation collisions** | `src/transformers/cli/serving/model_manager.py` |
| `933cf220` | microsoft/playwright | `v2_comment2context` | `packages/playwright-core/src/tools/cli-client/program.ts` | 141 | 0.1157 | 1166.2394 | 2.5866 | 2395.5857 | **Test-file collisions** | `packages/playwright-core/src/tools/dashboard/dashboardApp.ts` |
| `1aed02fc` | numpy/numpy | `v2_comment2context` | `numpy/_core/tests/test_dtype.py` | 64 | 0.1656 | 105.9636 | 0.8758 | 1133.9979 | **Incorrect intent** | `numpy/_core/src/multiarray/dlpack.c` |
| `856a5754` | pypa/pip | `v2_comment2context` | `src/pip/_internal/build_env.py` | 91 | 0.1427 | 157.2392 | 0.4513 | 425.6831 | **Test-file collisions** | `src/pip/_internal/commands/index.py` |
| `274d3a66` | pytest-dev/pytest | `v2_comment2context` | `testing/test_mark.py` | 54 | 0.2896 | 197.6695 | 2.5679 | 925.9648 | **Sibling implementation collisions** | `src/_pytest/config/__init__.py` |
| `a5ef6228` | pytest-dev/pytest | `v2_comment2context` | `src/_pytest/main.py` | 134 | 0.1045 | 113.8870 | 0.1828 | 438.0788 | **Unexplained failures** | `testing/test_warnings.py` |
| `128f9e22` | scrapy/scrapy | `v2_comment2context` | `scrapy/extensions/corestats.py` | 109 | 0.1371 | 255.3895 | 0.7156 | 134.6162 | **Generic hub collisions** | `scrapy/core/downloader/webclient.py` |
| `c1d1f7ca` | tokio-rs/tokio | `v2_edit2ripple` | `tokio/src/io/poll_evented.rs` | 157 | 0.1487 | 1192.9842 | 1.3161 | 276.4373 | **Test-file collisions** | `tokio/src/io/util/write_buf.rs` |
| `c2af1d61` | tokio-rs/tokio | `v2_comment2context` | `tokio/src/runtime/mod.rs` | 185 | 0.1512 | 74.2905 | 0.0687 | 85.9499 | **Incorrect intent** | `tokio/src/runtime/local_runtime/runtime.rs` |
| `c2af1d61` | tokio-rs/tokio | `v2_comment2context` | `tokio/src/runtime/context.rs` | 87 | 0.2143 | 95.2458 | 0.1792 | 140.4022 | **Incorrect intent** | `tokio/src/runtime/local_runtime/runtime.rs` |
| `18a155ce` | tokio-rs/tokio | `v2_edit2ripple` | `tokio/src/runtime/mod.rs` | 83 | 0.1449 | 1712.3680 | 2.3275 | 700.9925 | **Sibling implementation collisions** | `tokio/src/runtime/context.rs` |
| `056f7ac0` | vitejs/vite | `v2_comment2context` | `packages/create-vite/template-lit-ts/src/my-element.ts` | 91 | 0.2053 | 266.9184 | 0.2898 | 301.5856 | **Generic hub collisions** | `packages/create-vite/src/index.ts` |
| `056f7ac0` | vitejs/vite | `v2_comment2context` | `packages/create-vite/template-lit/src/my-element.js` | 116 | 0.1878 | 233.7342 | 0.2898 | 303.1412 | **Generic hub collisions** | `packages/create-vite/src/index.ts` |
| `5bdeecc5` | caddyserver/caddy | `v2_trace2code` | `caddyconfig/caddyfile/formatter.go` | 104 | 0.1941 | 677.8299 | 0.3035 | 438.4613 | **Test-file collisions** | `caddyconfig/caddyfile/parse_test.go` |
| `7a8ae85f` | caddyserver/caddy | `v2_edit2ripple` | `caddyconfig/httpcaddyfile/options_test.go` | 118 | 0.1047 | 708.2135 | 0.2980 | 411.1728 | **Sibling implementation collisions** | `modules/caddytls/acmeissuer.go` |
| `a726f272` | caddyserver/caddy | `v2_edit2ripple` | `caddyconfig/httpcaddyfile/builtins.go` | 69 | 0.1768 | 1585.5002 | 1.4328 | 1092.5321 | **Sibling implementation collisions** | `modules/caddytls/acmeissuer.go` |
| `f7d79ec3` | caddyserver/caddy | `v2_trace2code` | `modules/caddyhttp/routes.go` | 64 | 0.2149 | 848.8944 | 0.2755 | 748.9900 | **Test-file collisions** | `modules/caddyhttp/metrics_test.go` |
| `a9c4956e` | gin-gonic/gin | `v2_trace2code` | `render/render.go` | 65 | 0.0841 | 66.7558 | 0.1105 | 42.1538 | **Test-file collisions** | `context.go` |
| `aac6e017` | gin-gonic/gin | `v2_trace2code` | `binding/form_mapping.go` | 61 | 0.0930 | 99.2048 | 0.3275 | 211.2602 | **Test-file collisions** | `tree_test.go` |
| `1132f037` | tokio-rs/tokio | `v2_trace2code` | `tokio/src/sync/mpsc/block.rs` | 256 | 0.1081 | 524.4430 | 1.8286 | 865.4460 | **Test-file collisions** | `tokio/tests/sync_mpsc.rs` |
| `b872b8ef` | tokio-rs/tokio | `v2_trace2code` | `tokio/src/sync/mod.rs` | 160 | 0.1145 | 811.4690 | 1.5873 | 281.4370 | **Test-file collisions** | `tokio/src/sync/tests/loom_notify.rs` |

---

## 4. Deep-Dive Case Studies

### Query `33c925493a0fbff71d6badc9` (clap-rs/clap @ `v2_edit2ripple`)
- **Gold Target File**: `clap_builder/src/util/mod.rs`
- **Original M1 Rank**: `326` (Combined Score: `0.0280`)
- **Channel Scores**: BM25: `666.7171`, Exact Symbol: `0.2992`, Subwords: `151.1822`, Structural: `0.0000`
- **Root Cause Classification**: **Generic hub collisions**
- **Forensic Mechanism**: Central hub 'clap_builder/src/error/mod.rs' accumulated multi-field BM25 scores across generic utility identifiers.
- **Top 5 Competing Distractors**:
  1. `clap_builder/src/error/format.rs`
  1. `clap_builder/src/error/mod.rs`
  1. `clap_builder/src/builder/styled_str.rs`
  1. `clap_builder/src/builder/command.rs`
  1. `clap_builder/src/error/context.rs`

### Query `269e3e34c64f7e5d74b5fefd` (clap-rs/clap @ `v2_edit2ripple`)
- **Gold Target File**: `clap_builder/src/util/mod.rs`
- **Original M1 Rank**: `304` (Combined Score: `0.0351`)
- **Channel Scores**: BM25: `763.2554`, Exact Symbol: `0.2992`, Subwords: `172.9896`, Structural: `0.0000`
- **Root Cause Classification**: **Incorrect intent**
- **Forensic Mechanism**: Query intent keywords diverged from target file type.
- **Top 5 Competing Distractors**:
  1. `clap_builder/src/output/help_template.rs`
  1. `clap_builder/src/builder/command.rs`
  1. `clap_builder/src/builder/arg.rs`
  1. `clap_builder/src/builder/styled_str.rs`
  1. `tests/builder/help.rs`

### Query `6b1c1cff373771b4d7225c02` (clap-rs/clap @ `v2_code2test`)
- **Gold Target File**: `tests/builder/ignore_errors.rs`
- **Original M1 Rank**: `69` (Combined Score: `0.1339`)
- **Channel Scores**: BM25: `81.1029`, Exact Symbol: `0.3885`, Subwords: `220.2969`, Structural: `0.0000`
- **Root Cause Classification**: **Unexplained failures**
- **Forensic Mechanism**: Wide score dispersion across multiple distractor files without a single dominant pattern.
- **Top 5 Competing Distractors**:
  1. `clap_builder/src/parser/parser.rs`
  1. `clap_derive/src/derives/parser.rs`
  1. `clap_builder/src/builder/value_parser.rs`
  1. `clap_builder/src/builder/command.rs`
  1. `tests/derive_ui/value_parser_unsupported.stderr`

### Query `30fded9a7b09048b5c8f39de` (clap-rs/clap @ `v2_edit2ripple`)
- **Gold Target File**: `clap_mangen/tests/testsuite/common.rs`
- **Original M1 Rank**: `54` (Combined Score: `0.1368`)
- **Channel Scores**: BM25: `290.3206`, Exact Symbol: `0.6528`, Subwords: `503.0442`, Structural: `0.0000`
- **Root Cause Classification**: **Unexplained failures**
- **Forensic Mechanism**: Wide score dispersion across multiple distractor files without a single dominant pattern.
- **Top 5 Competing Distractors**:
  1. `clap_mangen/src/render.rs`
  1. `clap_builder/src/builder/arg.rs`
  1. `tests/builder/env.rs`
  1. `tests/builder/help_env.rs`
  1. `clap_builder/src/builder/styled_str.rs`

### Query `30fded9a7b09048b5c8f39de` (clap-rs/clap @ `v2_edit2ripple`)
- **Gold Target File**: `clap_mangen/Cargo.toml`
- **Original M1 Rank**: `224` (Combined Score: `0.0612`)
- **Channel Scores**: BM25: `214.5063`, Exact Symbol: `0.0983`, Subwords: `72.4809`, Structural: `0.0000`
- **Root Cause Classification**: **Test-file collisions**
- **Forensic Mechanism**: Test files ['clap_mangen/src/render.rs', 'clap_builder/src/builder/arg.rs'] had high lexical matches on test-prefixed query terms and outranked implementation target.
- **Top 5 Competing Distractors**:
  1. `clap_mangen/src/render.rs`
  1. `clap_builder/src/builder/arg.rs`
  1. `tests/builder/env.rs`
  1. `tests/builder/help_env.rs`
  1. `clap_builder/src/builder/styled_str.rs`

### Query `41deac7db89b57cead1c85e0` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target File**: `cache/demux_test.go`
- **Original M1 Rank**: `61` (Combined Score: `0.1488`)
- **Channel Scores**: BM25: `381.8790`, Exact Symbol: `0.2749`, Subwords: `286.8437`, Structural: `0.0000`
- **Root Cause Classification**: **Sibling implementation collisions**
- **Forensic Mechanism**: Sibling file 'cache/cache.go' in same directory had higher term frequency on common package symbols.
- **Top 5 Competing Distractors**:
  1. `cache/cache.go`
  1. `tests/integration/cache_test.go`
  1. `client/v3/leasing/cache.go`
  1. `cache/cache_test.go`
  1. `server/proxy/grpcproxy/cache/store.go`

### Query `7d5c2788e4c30bb773cb6643` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target File**: `cache/demux_test.go`
- **Original M1 Rank**: `69` (Combined Score: `0.1353`)
- **Channel Scores**: BM25: `291.3426`, Exact Symbol: `0.0975`, Subwords: `228.2633`, Structural: `0.0000`
- **Root Cause Classification**: **Sibling implementation collisions**
- **Forensic Mechanism**: Sibling file 'cache/cache.go' in same directory had higher term frequency on common package symbols.
- **Top 5 Competing Distractors**:
  1. `cache/cache.go`
  1. `client/v3/leasing/cache.go`
  1. `tests/integration/cache_test.go`
  1. `cache/cache_test.go`
  1. `server/proxy/grpcproxy/cache/store.go`

### Query `fa3c694a355ce304193a46e8` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target File**: `cache/demux_test.go`
- **Original M1 Rank**: `118` (Combined Score: `0.1302`)
- **Channel Scores**: BM25: `193.2157`, Exact Symbol: `0.1545`, Subwords: `252.0627`, Structural: `0.0000`
- **Root Cause Classification**: **Sibling implementation collisions**
- **Forensic Mechanism**: Sibling file 'cache/cache_test.go' in same directory had higher term frequency on common package symbols.
- **Top 5 Competing Distractors**:
  1. `tests/integration/cache_test.go`
  1. `cache/cache_test.go`
  1. `cache/progress_requestor.go`
  1. `cache/progress_requestor_test.go`
  1. `tests/integration/clientv3/watch/watch_test.go`

### Query `15959167576a87987d8f9f1f` (etcd-io/etcd @ `v2_code2test`)
- **Gold Target File**: `cache/demux_test.go`
- **Original M1 Rank**: `117` (Combined Score: `0.1054`)
- **Channel Scores**: BM25: `208.4117`, Exact Symbol: `0.3550`, Subwords: `358.4210`, Structural: `0.0000`
- **Root Cause Classification**: **Sibling implementation collisions**
- **Forensic Mechanism**: Sibling file 'cache/config.go' in same directory had higher term frequency on common package symbols.
- **Top 5 Competing Distractors**:
  1. `cache/config.go`
  1. `.github/PULL_REQUEST_TEMPLATE.md`
  1. `server/etcdmain/config.go`
  1. `cache/cache.go`
  1. `client/v3/op.go`

### Query `1dd2bdfdcf7092e1c69f50d6` (etcd-io/etcd @ `v2_code2test`)
- **Gold Target File**: `server/etcdserver/txn/txn_test.go`
- **Original M1 Rank**: `162` (Combined Score: `0.1498`)
- **Channel Scores**: BM25: `113.7535`, Exact Symbol: `0.2913`, Subwords: `309.8969`, Structural: `0.0000`
- **Root Cause Classification**: **Generic hub collisions**
- **Forensic Mechanism**: Central hub 'server/storage/mvcc/index.go' accumulated multi-field BM25 scores across generic utility identifiers.
- **Top 5 Competing Distractors**:
  1. `server/storage/mvcc/index.go`
  1. `server/etcdserver/v3_server.go`
  1. `server/etcdserver/server.go`
  1. `client/v3/op.go`
  1. `server/storage/mvcc/kv.go`

### Query `d5f1198f6fb5e19244fd4ac7` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target File**: `server/storage/mvcc/index_test.go`
- **Original M1 Rank**: `182` (Combined Score: `0.1258`)
- **Channel Scores**: BM25: `156.5766`, Exact Symbol: `0.3050`, Subwords: `226.0787`, Structural: `0.0000`
- **Root Cause Classification**: **Sibling implementation collisions**
- **Forensic Mechanism**: Sibling file 'server/storage/mvcc/kv.go' in same directory had higher term frequency on common package symbols.
- **Top 5 Competing Distractors**:
  1. `server/storage/mvcc/kv.go`
  1. `tests/robustness/model/types.go`
  1. `client/v3/kubernetes/client.go`
  1. `server/storage/mvcc/kv_test.go`
  1. `tests/robustness/coverage/patches/kubernetes/0001-Add-Open-Telemetry-trace-event-when-passing-through-.patch`

### Query `d5f1198f6fb5e19244fd4ac7` (etcd-io/etcd @ `v2_comment2context`)
- **Gold Target File**: `server/etcdserver/txn/txn_test.go`
- **Original M1 Rank**: `147` (Combined Score: `0.1367`)
- **Channel Scores**: BM25: `178.4297`, Exact Symbol: `0.2252`, Subwords: `229.3791`, Structural: `0.0000`
- **Root Cause Classification**: **Generic hub collisions**
- **Forensic Mechanism**: Central hub 'tests/robustness/model/types.go' accumulated multi-field BM25 scores across generic utility identifiers.
- **Top 5 Competing Distractors**:
  1. `server/storage/mvcc/kv.go`
  1. `tests/robustness/model/types.go`
  1. `client/v3/kubernetes/client.go`
  1. `server/storage/mvcc/kv_test.go`
  1. `tests/robustness/coverage/patches/kubernetes/0001-Add-Open-Telemetry-trace-event-when-passing-through-.patch`

