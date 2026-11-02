# RepoNeedle — Mission 0.80+ (Ranking Intelligence Research Programme)
# Phase R1 Deliverable 3: Query Failure Taxonomy & Exhaustive Classification

**Document ID:** `QUERY_FAILURE_TAXONOMY.md`  
**Status:** Complete  
**Date:** November 2, 2026  
**Author:** Principal Search Relevance Engineer, Information Retrieval Researcher & ML Ranking Architect  
**Scope:** All 345 Queries across 25 Repositories in ARB v2 Set A  

---

## 1. Executive Summary & Taxonomy Distribution

Every single query in ARB v2 Set A (345 queries) has been audited, evaluated, and classified into the mandated 10 failure categories based on deterministic algorithmic criteria:

| Category ID & Name | Query Count | % of Benchmark | Description & Root Cause |
| :--- | :--- | :--- | :--- |
| **3. Query intent mismatch** | **143** | **41.45%** | Rank 1 is occupied by the query's input seed file (`changed_file`, `given_file`, `anchor_file`). |
| **4. Test versus implementation confusion** | **74** | **21.45%** | Query intent requires test files (`code2test`), but ranker surfaces implementation code at Ranks 1–5. |
| **6. Path mismatch** | **50** | **14.49%** | Gold file resides in a disjoint subtree with little path token overlap; ranker prefers unrelated files. |
| **5. Sibling implementation confusion** | **32** | **9.28%** | Rank 1 and gold target share the exact same package/directory, but ranker picked the wrong sibling. |
| **Rank 1 Success** | **31** | **8.99%** | Gold file correctly identified and placed at Rank 1 ($R_1 = 1$). |
| **8. Structural relationship error** | **6** | **1.74%** | Unconditioned graph expansion boosted an architectural hub file while gold file lacked structural link. |
| **2. Identifier mismatch** | **3** | **0.87%** | Gold file lacked query identifier match, while top displacer matched symbols prominently. |
| **10. Other / Unclassified** | **3** | **0.87%** | Residual complex displacements requiring multi-hop contextual reasoning. |
| **7. Symbol definition mismatch** | **2** | **0.58%** | Symbol defined in gold file was placed behind files containing multiple references/usages. |
| **1. Lexical mismatch** | **1** | **0.29%** | Severe lexical term dilution where high-frequency tokens in unrelated files outweighed gold. |
| **Total** | **345** | **100.00%** | Comprehensive audit across all 345 queries |

---

## 3. Query intent mismatch (143 Queries, 41.45%)

**Root Cause Analysis:** Rank 1 is occupied by the query's input seed file (`changed_file`, `given_file`, `anchor_file`).

| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `597f32e9` | `clap-rs/clap` | `code2test` | 6 | `clap_builder/src/output/help_tem...` | `tests/builder/help.rs` | Rank 1 is query input seed (clap_builder/src/output/help_template.rs) |
| `33c92549` | `clap-rs/clap` | `edit2ripple` | 326 | `clap_builder/src/error/format.rs` | `clap_builder/src/util/mod.rs` | Rank 1 is query input seed (clap_builder/src/error/format.rs) |
| `269e3e34` | `clap-rs/clap` | `edit2ripple` | 304 | `clap_builder/src/output/help_tem...` | `clap_builder/src/util/mod.rs` | Rank 1 is query input seed (clap_builder/src/output/help_template.rs) |
| `8e5f31c0` | `clap-rs/clap` | `code2test` | 2 | `clap_complete/src/engine/complet...` | `clap_complete/tests/testsuite/en...` | Rank 1 is query input seed (clap_complete/src/engine/complete.rs) |
| `30fded9a` | `clap-rs/clap` | `edit2ripple` | 30 | `clap_mangen/src/render.rs` | `clap_mangen/tests/testsuite/comm...` | Rank 1 is query input seed (clap_mangen/src/render.rs) |
| `0c60e782` | `etcd-io/etcd` | `code2test` | 5 | `cache/cache.go` | `cache/demux_test.go` | Rank 1 is query input seed (cache/cache.go) |
| `0265037c` | `etcd-io/etcd` | `comment2context` | 3 | `cache/demux_test.go` | `cache/demux.go` | Rank 1 is query input seed (cache/demux_test.go) |
| `191c9a48` | `etcd-io/etcd` | `comment2context` | 4 | `cache/cache.go` | `cache/demux.go` | Rank 1 is query input seed (cache/cache.go) |
| `41deac7d` | `etcd-io/etcd` | `comment2context` | 2 | `cache/cache.go` | `cache/demux.go` | Rank 1 is query input seed (cache/cache.go) |
| `7d5c2788` | `etcd-io/etcd` | `comment2context` | 3 | `cache/cache.go` | `cache/demux.go` | Rank 1 is query input seed (cache/cache.go) |
| `fa3c694a` | `etcd-io/etcd` | `comment2context` | 6 | `tests/integration/cache_test.go` | `cache/demux.go` | Rank 1 is query input seed (tests/integration/cache_test.go) |
| `15959167` | `etcd-io/etcd` | `code2test` | 16 | `cache/config.go` | `cache/cache_test.go` | Rank 1 is query input seed (cache/config.go) |
| `ba3c1cd2` | `etcd-io/etcd` | `comment2context` | 2 | `cache/cache.go` | `cache/cache_test.go` | Rank 1 is query input seed (cache/cache.go) |
| `d5f1198f` | `etcd-io/etcd` | `comment2context` | 4 | `server/storage/mvcc/kv.go` | `server/storage/mvcc/kv_test.go` | Rank 1 is query input seed (server/storage/mvcc/kv.go) |
| `e1280404` | `etcd-io/etcd` | `comment2context` | 3 | `cache/cache.go` | `cache/cache_test.go` | Rank 1 is query input seed (cache/cache.go) |
| `e45d17f0` | `etcd-io/etcd` | `comment2context` | 5 | `cache/cache.go` | `cache/cache_test.go` | Rank 1 is query input seed (cache/cache.go) |
| `b09afd5a` | `etcd-io/etcd` | `edit2ripple` | 34 | `cache/ringbuffer.go` | `cache/demux.go` | Rank 1 is query input seed (cache/ringbuffer.go) |
| `a8e245be` | `etcd-io/etcd` | `edit2ripple` | 2 | `server/etcdserver/util.go` | `server/etcdserver/util_test.go` | Rank 1 is query input seed (server/etcdserver/util.go) |
| `ac0571b1` | `etcd-io/etcd` | `comment2context` | 5 | `client/v3/config.go` | `etcdctl/ctlv3/command/ep_command...` | Rank 1 is query input seed (client/v3/config.go) |
| `148cbb03` | `etcd-io/etcd` | `edit2ripple` | 9 | `client/v3/config.go` | `etcdctl/ctlv3/command/ep_command...` | Rank 1 is query input seed (client/v3/config.go) |
| `ba14e2bd` | `etcd-io/etcd` | `code2test` | 22 | `server/etcdmain/help.go` | `server/embed/config_test.go` | Rank 1 is query input seed (server/etcdmain/help.go) |
| `38c2a13a` | `etcd-io/etcd` | `comment2context` | 43 | `server/embed/config_test.go` | `server/etcdmain/help.go` | Rank 1 is query input seed (server/embed/config_test.go) |
| `d6dbe66e` | `etcd-io/etcd` | `edit2ripple` | 10 | `server/embed/etcd.go` | `server/embed/config_test.go` | Rank 1 is query input seed (server/embed/etcd.go) |
| `e613783f` | `etcd-io/etcd` | `code2test` | 6 | `pkg/expect/expect.go` | `pkg/expect/expect_test.go` | Rank 1 is query input seed (pkg/expect/expect.go) |
| `f2ed9144` | `etcd-io/etcd` | `comment2context` | 2 | `pkg/expect/expect.go` | `pkg/expect/expect_test.go` | Rank 1 is query input seed (pkg/expect/expect.go) |
| `dd57d697` | `fastapi/fastapi` | `code2test` | 42 | `fastapi/_compat/v2.py` | `tests/test_jsonable_encoder.py` | Rank 1 is query input seed (fastapi/_compat/v2.py) |
| `bb9cf609` | `gin-gonic/gin` | `edit2ripple` | 24 | `gin.go` | `gin_integration_test.go` | Rank 1 is query input seed (gin.go) |
| `9bfe7e89` | `gin-gonic/gin` | `edit2ripple` | 3 | `recovery.go` | `recovery_test.go` | Rank 1 is query input seed (recovery.go) |
| `4f6c4f2d` | `gin-gonic/gin` | `edit2ripple` | 4 | `binding/form_mapping.go` | `binding/form_mapping_test.go` | Rank 1 is query input seed (binding/form_mapping.go) |
| `21093314` | `huggingface/diffusers` | `code2test` | 121 | `src/diffusers/utils/torch_utils....` | `tests/others/test_utils.py` | Rank 1 is query input seed (src/diffusers/utils/torch_utils.py) |
| `154523e8` | `huggingface/diffusers` | `comment2context` | 100 | `tests/pipelines/test_pipelines.p...` | `setup.py` | Rank 1 is query input seed (tests/pipelines/test_pipelines.py) |
| `7d661ed7` | `huggingface/diffusers` | `comment2context` | 134 | `tests/pipelines/test_pipelines.p...` | `examples/advanced_diffusion_trai...` | Rank 1 is query input seed (tests/pipelines/test_pipelines.py) |
| `8d19ca90` | `huggingface/diffusers` | `comment2context` | 37 | `src/diffusers/pipelines/pipeline...` | `tests/testing_utils.py` | Rank 1 is query input seed (src/diffusers/pipelines/pipeline_utils.py) |
| `4859c611` | `huggingface/diffusers` | `comment2context` | 37 | `scripts/convert_ltx2_to_diffuser...` | `src/diffusers/pipelines/ltx2/pip...` | Rank 1 is query input seed (scripts/convert_ltx2_to_diffusers.py) |
| `81051ce9` | `huggingface/diffusers` | `code2test` | 14 | `src/diffusers/pipelines/hunyuan_...` | `tests/pipelines/hunyuan_video/te...` | Rank 1 is query input seed (src/diffusers/pipelines/hunyuan_video/pipeline_hunyuan_video_image2video.py) |
| `bc87006b` | `huggingface/diffusers` | `comment2context` | 17 | `src/diffusers/pipelines/hunyuan_...` | `tests/pipelines/hunyuan_video/te...` | Rank 1 is query input seed (src/diffusers/pipelines/hunyuan_video/pipeline_hunyuan_video_image2video.py) |
| `c60a8891` | `huggingface/diffusers` | `code2test` | 14 | `src/diffusers/modular_pipelines/...` | `tests/modular_pipelines/test_mod...` | Rank 1 is query input seed (src/diffusers/modular_pipelines/modular_pipeline.py) |
| `d837c1ef` | `huggingface/diffusers` | `comment2context` | 4 | `src/diffusers/modular_pipelines/...` | `tests/modular_pipelines/test_mod...` | Rank 1 is query input seed (src/diffusers/modular_pipelines/modular_pipeline.py) |
| `0978d6fd` | `huggingface/diffusers` | `edit2ripple` | 115 | `src/diffusers/modular_pipelines/...` | `docs/source/en/api/modular_diffu...` | Rank 1 is query input seed (src/diffusers/modular_pipelines/modular_pipeline.py) |
| `12b84b0c` | `huggingface/transformers` | `code2test` | 7 | `src/transformers/core_model_load...` | `tests/test_modeling_common.py` | Rank 1 is query input seed (src/transformers/core_model_loading.py) |
| `051a22c7` | `huggingface/transformers` | `comment2context` | 48 | `src/transformers/core_model_load...` | `src/transformers/conversion_mapp...` | Rank 1 is query input seed (src/transformers/core_model_loading.py) |
| `3e57030f` | `huggingface/transformers` | `comment2context` | 4 | `tests/test_modeling_common.py` | `src/transformers/conversion_mapp...` | Rank 1 is query input seed (tests/test_modeling_common.py) |
| `ae6d94b3` | `huggingface/transformers` | `comment2context` | 9 | `tests/utils/test_core_model_load...` | `src/transformers/conversion_mapp...` | Rank 1 is query input seed (tests/utils/test_core_model_loading.py) |
| `210bcbf1` | `huggingface/transformers` | `code2test` | 118 | `src/transformers/loss/loss_d_fin...` | `tests/models/d_fine/test_modelin...` | Rank 1 is query input seed (src/transformers/loss/loss_d_fine.py) |
| `0a166358` | `huggingface/transformers` | `comment2context` | 3689 | `src/transformers/integrations/fi...` | `src/transformers/conversion_mapp...` | Rank 1 is query input seed (src/transformers/integrations/finegrained_fp8.py) |
| `9aa10bc6` | `huggingface/transformers` | `comment2context` | 3009 | `src/transformers/integrations/fi...` | `src/transformers/conversion_mapp...` | Rank 1 is query input seed (src/transformers/integrations/finegrained_fp8.py) |
| `a4b5977e` | `huggingface/transformers` | `comment2context` | 1474 | `src/transformers/conversion_mapp...` | `src/transformers/integrations/fi...` | Rank 1 is query input seed (src/transformers/conversion_mapping.py) |
| `8360be1c` | `huggingface/transformers` | `edit2ripple` | 1608 | `src/transformers/integrations/fi...` | `src/transformers/conversion_mapp...` | Rank 1 is query input seed (src/transformers/integrations/finegrained_fp8.py) |
| `23a2b9be` | `huggingface/transformers` | `code2test` | 2 | `src/transformers/cli/serving/uti...` | `tests/cli/test_serve.py` | Rank 1 is query input seed (src/transformers/cli/serving/utils.py) |
| `9c620240` | `huggingface/transformers` | `code2test` | 30 | `src/transformers/tokenization_ut...` | `tests/models/auto/test_tokenizat...` | Rank 1 is query input seed (src/transformers/tokenization_utils_tokenizers.py) |
| `335597ee` | `huggingface/transformers` | `comment2context` | 51 | `src/transformers/tokenization_ut...` | `tests/models/auto/test_tokenizat...` | Rank 1 is query input seed (src/transformers/tokenization_utils_tokenizers.py) |
| `1bd8ce68` | `huggingface/transformers` | `edit2ripple` | 2 | `src/transformers/models/mt5/conf...` | `src/transformers/models/umt5/con...` | Rank 1 is query input seed (src/transformers/models/mt5/configuration_mt5.py) |
| `85fc8542` | `huggingface/transformers` | `edit2ripple` | 4 | `src/transformers/models/umt5/con...` | `src/transformers/models/mt5/conf...` | Rank 1 is query input seed (src/transformers/models/umt5/configuration_umt5.py) |
| `896a5d9f` | `huggingface/transformers` | `code2test` | 30 | `src/transformers/integrations/te...` | `tests/test_tensor_parallel_mixin...` | Rank 1 is query input seed (src/transformers/integrations/tensor_parallel.py) |
| `2f529c8b` | `huggingface/transformers` | `comment2context` | 2 | `src/transformers/integrations/in...` | `src/transformers/training_args.p...` | Rank 1 is query input seed (src/transformers/integrations/integration_utils.py) |
| `70637f29` | `huggingface/transformers` | `comment2context` | 2 | `src/transformers/trainer.py` | `tests/trainer/test_trainer.py` | Rank 1 is query input seed (src/transformers/trainer.py) |
| `9c3a21b8` | `huggingface/transformers` | `comment2context` | 5 | `src/transformers/integrations/in...` | `src/transformers/training_args.p...` | Rank 1 is query input seed (src/transformers/integrations/integration_utils.py) |
| `78906550` | `spring-projects/spring-boot` | `edit2ripple` | 550 | `module/spring-boot-webflux/src/m...` | `module/spring-boot-webflux/src/m...` | Rank 1 is query input seed (module/spring-boot-webflux/src/main/java/org/springframework/boot/webflux/autoconfigure/WebFluxProperties.java) |
| `e8ef6b1c` | `spring-projects/spring-boot` | `code2test` | 2 | `spring-boot-project/spring-boot-...` | `spring-boot-project/spring-boot-...` | Rank 1 is query input seed (spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/web/reactive/error/AbstractErrorWebExceptionHandler.java) |
| `e271598f` | `spring-projects/spring-boot` | `edit2ripple` | 3 | `spring-boot-project/spring-boot-...` | `spring-boot-project/spring-boot-...` | Rank 1 is query input seed (spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/web/reactive/error/AbstractErrorWebExceptionHandler.java) |
| `445f0e5c` | `spring-projects/spring-boot` | `edit2ripple` | 7 | `spring-boot-project/spring-boot-...` | `spring-boot-project/spring-boot-...` | Rank 1 is query input seed (spring-boot-project/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/web/servlet/error/ErrorMvcAutoConfiguration.java) |
| `bbcbbc2c` | `tokio-rs/tokio` | `edit2ripple` | 19 | `tokio-util/src/codec/framed_impl...` | `tokio-util/tests/framed.rs` | Rank 1 is query input seed (tokio-util/src/codec/framed_impl.rs) |
| `ce7c3a91` | `tokio-rs/tokio` | `edit2ripple` | 28 | `tokio/src/runtime/blocking/pool....` | `tokio/src/runtime/tests/loom_blo...` | Rank 1 is query input seed (tokio/src/runtime/blocking/pool.rs) |
| `7ae166d7` | `tokio-rs/tokio` | `code2test` | 10 | `tokio/src/net/tcp/socket.rs` | `tokio/tests/udp.rs` | Rank 1 is query input seed (tokio/src/net/tcp/socket.rs) |
| `d354e818` | `tokio-rs/tokio` | `comment2context` | 9 | `tokio/src/task/spawn.rs` | `tokio/src/runtime/mod.rs` | Rank 1 is query input seed (tokio/src/task/spawn.rs) |
| `d42e82da` | `tokio-rs/tokio` | `comment2context` | 5 | `tokio/src/runtime/runtime.rs` | `tokio/src/runtime/mod.rs` | Rank 1 is query input seed (tokio/src/runtime/runtime.rs) |
| `eca2d26f` | `tokio-rs/tokio` | `comment2context` | 2 | `tokio/src/runtime/handle.rs` | `tokio/src/runtime/mod.rs` | Rank 1 is query input seed (tokio/src/runtime/handle.rs) |
| `a2519be1` | `tokio-rs/tokio` | `code2test` | 4 | `tokio-stream/src/stream_ext/coll...` | `tokio-stream/tests/stream_collec...` | Rank 1 is query input seed (tokio-stream/src/stream_ext/collect.rs) |
| `660e1d8e` | `tokio-rs/tokio` | `comment2context` | 2 | `tokio-stream/src/stream_ext/coll...` | `tokio-stream/tests/stream_collec...` | Rank 1 is query input seed (tokio-stream/src/stream_ext/collect.rs) |
| `aab82f38` | `tokio-rs/tokio` | `code2test` | 26 | `tokio/src/task/builder.rs` | `tokio/tests/task_builder.rs` | Rank 1 is query input seed (tokio/src/task/builder.rs) |
| `fd368dbd` | `tokio-rs/tokio` | `edit2ripple` | 4 | `tokio/src/task/builder.rs` | `tokio-util/tests/task_join_map.r...` | Rank 1 is query input seed (tokio/src/task/builder.rs) |
| `b4fc03b0` | `tokio-rs/tokio` | `code2test` | 7 | `tokio/src/sync/mpsc/list.rs` | `tokio/tests/sync_mpsc.rs` | Rank 1 is query input seed (tokio/src/sync/mpsc/list.rs) |
| `35154a76` | `tokio-rs/tokio` | `comment2context` | 12 | `tokio/tests/sync_mpsc.rs` | `tokio/src/sync/mpsc/chan.rs` | Rank 1 is query input seed (tokio/tests/sync_mpsc.rs) |
| `b6f3032d` | `tokio-rs/tokio` | `code2test` | 4 | `tokio-util/src/task/join_queue.r...` | `tokio-util/tests/task_join_queue...` | Rank 1 is query input seed (tokio-util/src/task/join_queue.rs) |
| `4eb8d031` | `vitejs/vite` | `edit2ripple` | 24 | `packages/vite/src/node/server/en...` | `playground/hmr-full-bundle-mode/...` | Rank 1 is query input seed (packages/vite/src/node/server/environments/fullBundleEnvironment.ts) |
| `03428c61` | `vitejs/vite` | `edit2ripple` | 27 | `packages/vite/src/node/server/in...` | `packages/vite/src/node/server/en...` | Rank 1 is query input seed (packages/vite/src/node/server/index.ts) |
| `96557f79` | `vitejs/vite` | `edit2ripple` | 24 | `packages/vite/src/node/server/mi...` | `playground/proxy-bypass/vite.con...` | Rank 1 is query input seed (packages/vite/src/node/server/middlewares/proxy.ts) |
| `99089b7d` | `vitejs/vite` | `edit2ripple` | 440 | `packages/vite/src/node/plugins/i...` | `packages/vite/package.json` | Rank 1 is query input seed (packages/vite/src/node/plugins/index.ts) |
| `bf0ff857` | `vitejs/vite` | `edit2ripple` | 533 | `packages/vite/src/node/plugins/o...` | `packages/vite/package.json` | Rank 1 is query input seed (packages/vite/src/node/plugins/oxc.ts) |
| `bf473089` | `HypothesisWorks/hypothesis` | `comment2context` | 2 | `hypothesis-python/tests/cover/te...` | `hypothesis-python/src/hypothesis...` | Rank 1 is query input seed (hypothesis-python/tests/cover/test_seed_printing.py) |
| `01323034` | `astral-sh/ruff` | `comment2context` | 4 | `crates/ty_python_semantic/src/ty...` | `crates/ty_python_semantic/src/ty...` | Rank 1 is query input seed (crates/ty_python_semantic/src/types/function.rs) |
| `413524fd` | `astral-sh/ruff` | `comment2context` | 61 | `crates/ty_project/src/db/changes...` | `crates/ty_server/tests/e2e/confi...` | Rank 1 is query input seed (crates/ty_project/src/db/changes.rs) |
| `538d3764` | `astral-sh/ruff` | `comment2context` | 24 | `crates/ty_project/src/db.rs` | `crates/ruff_db/src/diagnostic/mo...` | Rank 1 is query input seed (crates/ty_project/src/db.rs) |
| `f9c42afe` | `astral-sh/ruff` | `comment2context` | 49 | `crates/ty_project/src/db.rs` | `crates/ruff_db/src/diagnostic/mo...` | Rank 1 is query input seed (crates/ty_project/src/db.rs) |
| `8e6bf4a9` | `astral-sh/ruff` | `comment2context` | 6 | `crates/ty_python_semantic/resour...` | `crates/ty_python_semantic/src/ty...` | Rank 1 is query input seed (crates/ty_python_semantic/resources/mdtest/enums.md) |
| `449280b3` | `eslint/eslint` | `comment2context` | 197 | `lib/rules/no-param-reassign.js` | `eslint.config.js` | Rank 1 is query input seed (lib/rules/no-param-reassign.js) |
| `44eb66d7` | `etcd-io/etcd` | `comment2context` | 3 | `tests/integration/cache_test.go` | `cache/cache.go` | Rank 1 is query input seed (tests/integration/cache_test.go) |
| `bb23acb5` | `etcd-io/etcd` | `comment2context` | 3 | `server/storage/wal/repair.go` | `server/storage/wal/repair_test.g...` | Rank 1 is query input seed (server/storage/wal/repair.go) |
| `8c8c2eb1` | `huggingface/diffusers` | `comment2context` | 36 | `src/diffusers/pipelines/qwenimag...` | `tests/pipelines/qwenimage/test_q...` | Rank 1 is query input seed (src/diffusers/pipelines/qwenimage/pipeline_qwenimage_controlnet_inpaint.py) |
| `a17b0c14` | `huggingface/diffusers` | `comment2context` | 74 | `src/diffusers/pipelines/qwenimag...` | `tests/pipelines/qwenimage/test_q...` | Rank 1 is query input seed (src/diffusers/pipelines/qwenimage/pipeline_qwenimage.py) |
| `c7f3b691` | `huggingface/diffusers` | `comment2context` | 16 | `tests/pipelines/qwenimage/test_q...` | `src/diffusers/models/autoencoder...` | Rank 1 is query input seed (tests/pipelines/qwenimage/test_qwenimage.py) |
| `262ecc80` | `huggingface/transformers` | `edit2ripple` | 79 | `src/transformers/cli/serving/mod...` | `src/transformers/cli/serving/cha...` | Rank 1 is query input seed (src/transformers/cli/serving/model_manager.py) |
| `91057704` | `huggingface/transformers` | `edit2ripple` | 4 | `src/transformers/cli/serving/res...` | `src/transformers/cli/serving/cha...` | Rank 1 is query input seed (src/transformers/cli/serving/response.py) |
| `ca350356` | `huggingface/transformers` | `comment2context` | 7 | `tests/models/higgs_audio_v2/test...` | `src/transformers/models/higgs_au...` | Rank 1 is query input seed (tests/models/higgs_audio_v2/test_modeling_higgs_audio_v2.py) |
| `f97f273b` | `huggingface/transformers` | `comment2context` | 5 | `tests/quantization/torchao_integ...` | `src/transformers/quantizers/quan...` | Rank 1 is query input seed (tests/quantization/torchao_integration/test_torchao.py) |
| `147ffd16` | `ipython/ipython` | `comment2context` | 4 | `IPython/core/guarded_eval.py` | `tests/test_completer.py` | Rank 1 is query input seed (IPython/core/guarded_eval.py) |
| `a467dd60` | `ipython/ipython` | `comment2context` | 5 | `IPython/core/guarded_eval.py` | `tests/test_completer.py` | Rank 1 is query input seed (IPython/core/guarded_eval.py) |
| `2f39489d` | `microsoft/playwright` | `comment2context` | 26 | `packages/playwright-core/src/too...` | `packages/playwright-core/src/too...` | Rank 1 is query input seed (packages/playwright-core/src/tools/cli-client/program.ts) |
| `405caf34` | `microsoft/playwright` | `comment2context` | 12 | `packages/playwright-core/src/too...` | `packages/playwright-core/src/too...` | Rank 1 is query input seed (packages/playwright-core/src/tools/cli-client/program.ts) |
| `8cd3867f` | `microsoft/playwright` | `comment2context` | 34 | `packages/playwright-core/src/too...` | `packages/playwright-core/src/too...` | Rank 1 is query input seed (packages/playwright-core/src/tools/dashboard/dashboardApp.ts) |
| `933cf220` | `microsoft/playwright` | `comment2context` | 141 | `packages/playwright-core/src/too...` | `packages/playwright-core/src/too...` | Rank 1 is query input seed (packages/playwright-core/src/tools/dashboard/dashboardApp.ts) |
| `1aed02fc` | `numpy/numpy` | `comment2context` | 3 | `numpy/_core/src/multiarray/dlpac...` | `numpy/_core/tests/test_dtype.py` | Rank 1 is query input seed (numpy/_core/src/multiarray/dlpack.c) |
| `106d7add` | `pydantic/pydantic` | `comment2context` | 3 | `pydantic-core/src/serializers/ty...` | `tests/test_discriminated_union.p...` | Rank 1 is query input seed (pydantic-core/src/serializers/type_serializers/union.rs) |
| `0c2c605d` | `pypa/pip` | `comment2context` | 2 | `src/pip/_internal/index/package_...` | `src/pip/_internal/models/link.py` | Rank 1 is query input seed (src/pip/_internal/index/package_finder.py) |
| `7fcc9b91` | `pypa/pip` | `comment2context` | 3 | `src/pip/_internal/self_outdated_...` | `tests/unit/test_commands.py` | Rank 1 is query input seed (src/pip/_internal/self_outdated_check.py) |
| `a1ced661` | `pypa/pip` | `comment2context` | 5 | `src/pip/_internal/self_outdated_...` | `src/pip/_internal/commands/insta...` | Rank 1 is query input seed (src/pip/_internal/self_outdated_check.py) |
| `856a5754` | `pypa/pip` | `comment2context` | 12 | `src/pip/_internal/commands/index...` | `src/pip/_internal/cli/cmdoptions...` | Rank 1 is query input seed (src/pip/_internal/commands/index.py) |
| `c00e6405` | `pypa/pip` | `comment2context` | 3 | `src/pip/_internal/commands/insta...` | `tests/functional/test_install.py` | Rank 1 is query input seed (src/pip/_internal/commands/install.py) |
| `274d3a66` | `pytest-dev/pytest` | `comment2context` | 2 | `src/_pytest/config/__init__.py` | `testing/test_mark.py` | Rank 1 is query input seed (src/_pytest/config/__init__.py) |
| `a5ef6228` | `pytest-dev/pytest` | `comment2context` | 37 | `testing/test_warnings.py` | `src/_pytest/main.py` | Rank 1 is query input seed (testing/test_warnings.py) |
| `4cdc0890` | `python/mypy` | `comment2context` | 6 | `mypyc/build.py` | `mypyc/codegen/emitmodule.py` | Rank 1 is query input seed (mypyc/build.py) |
| `0b514d81` | `scrapy/scrapy` | `comment2context` | 38 | `scrapy/http/request/__init__.py` | `tests/test_http_request.py` | Rank 1 is query input seed (scrapy/http/request/__init__.py) |
| `3025e429` | `scrapy/scrapy` | `comment2context` | 2 | `scrapy/http/response/__init__.py` | `tests/test_http_response.py` | Rank 1 is query input seed (scrapy/http/response/__init__.py) |
| `128f9e22` | `scrapy/scrapy` | `comment2context` | 109 | `scrapy/core/downloader/webclient...` | `scrapy/extensions/corestats.py` | Rank 1 is query input seed (scrapy/core/downloader/webclient.py) |
| `224dd1f1` | `tokio-rs/tokio` | `comment2context` | 24 | `tokio/src/io/util/write_buf.rs` | `tokio/tests/io_write_buf.rs` | Rank 1 is query input seed (tokio/src/io/util/write_buf.rs) |
| `c1d1f7ca` | `tokio-rs/tokio` | `edit2ripple` | 157 | `tokio/src/io/util/write_buf.rs` | `tokio/src/io/poll_evented.rs` | Rank 1 is query input seed (tokio/src/io/util/write_buf.rs) |
| `2c17bde1` | `tokio-rs/tokio` | `comment2context` | 7 | `tokio/src/runtime/driver/op.rs` | `tokio/src/io/uring/open.rs` | Rank 1 is query input seed (tokio/src/runtime/driver/op.rs) |
| `a4bb43c5` | `tokio-rs/tokio` | `edit2ripple` | 2 | `tokio/src/io/uring/open.rs` | `tokio/src/fs/write.rs` | Rank 1 is query input seed (tokio/src/io/uring/open.rs) |
| `9473ef1b` | `tokio-rs/tokio` | `comment2context` | 9 | `tokio/src/macros/try_join.rs` | `tokio/src/macros/support.rs` | Rank 1 is query input seed (tokio/src/macros/try_join.rs) |
| `18a155ce` | `tokio-rs/tokio` | `edit2ripple` | 3 | `tokio/src/runtime/context.rs` | `tokio/src/runtime/mod.rs` | Rank 1 is query input seed (tokio/src/runtime/context.rs) |
| `3e3c5349` | `tox-dev/tox` | `comment2context` | 42 | `docs/config.rst` | `tests/config/loader/ini/test_fac...` | Rank 1 is query input seed (docs/config.rst) |
| `e52201a1` | `tox-dev/tox` | `comment2context` | 3 | `src/tox/tox_env/python/api.py` | `tests/tox_env/python/test_python...` | Rank 1 is query input seed (src/tox/tox_env/python/api.py) |
| `08152da0` | `vuejs/core` | `comment2context` | 3 | `packages/reactivity/__tests__/re...` | `packages/reactivity/src/collecti...` | Rank 1 is query input seed (packages/reactivity/__tests__/reactive.spec.ts) |
| `88f4b3f1` | `caddyserver/caddy` | `edit2ripple` | 9 | `listeners.go` | `listeners_test.go` | Rank 1 is query input seed (listeners.go) |
| `f0e2f6c4` | `caddyserver/caddy` | `edit2ripple` | 3 | `caddyconfig/caddyfile/formatter....` | `caddyconfig/caddyfile/parse.go` | Rank 1 is query input seed (caddyconfig/caddyfile/formatter.go) |
| `06314493` | `caddyserver/caddy` | `edit2ripple` | 2 | `caddyconfig/caddyfile/parse.go` | `caddyconfig/caddyfile/parse_test...` | Rank 1 is query input seed (caddyconfig/caddyfile/parse.go) |
| `365be403` | `caddyserver/caddy` | `edit2ripple` | 2 | `modules/caddyhttp/metrics.go` | `modules/caddyhttp/metrics_test.g...` | Rank 1 is query input seed (modules/caddyhttp/metrics.go) |
| `8b6ab1ba` | `clap-rs/clap` | `edit2ripple` | 2 | `clap_builder/src/parser/parser.r...` | `clap_builder/src/builder/arg.rs` | Rank 1 is query input seed (clap_builder/src/parser/parser.rs) |
| `fd824e5a` | `clap-rs/clap` | `edit2ripple` | 7 | `clap_builder/src/builder/arg.rs` | `clap_builder/src/parser/parser.r...` | Rank 1 is query input seed (clap_builder/src/builder/arg.rs) |
| `cbb729b2` | `gin-gonic/gin` | `edit2ripple` | 2 | `context.go` | `context_test.go` | Rank 1 is query input seed (context.go) |
| `0150e5de` | `gin-gonic/gin` | `edit2ripple` | 4 | `binding/form_mapping.go` | `binding/form_mapping_test.go` | Rank 1 is query input seed (binding/form_mapping.go) |
| `02faf838` | `gin-gonic/gin` | `edit2ripple` | 4 | `render/data.go` | `render/render_test.go` | Rank 1 is query input seed (render/data.go) |
| `fa3cd075` | `gin-gonic/gin` | `edit2ripple` | 5 | `gin.go` | `gin_integration_test.go` | Rank 1 is query input seed (gin.go) |
| `9edbbb53` | `gin-gonic/gin` | `edit2ripple` | 2 | `tree.go` | `gin_integration_test.go` | Rank 1 is query input seed (tree.go) |
| `09a72fcf` | `gin-gonic/gin` | `edit2ripple` | 3 | `binding/form_mapping.go` | `binding/form_mapping_test.go` | Rank 1 is query input seed (binding/form_mapping.go) |
| `5bf9c616` | `gin-gonic/gin` | `edit2ripple` | 3 | `logger.go` | `logger_test.go` | Rank 1 is query input seed (logger.go) |
| `45680752` | `gin-gonic/gin` | `edit2ripple` | 4 | `recovery.go` | `recovery_test.go` | Rank 1 is query input seed (recovery.go) |
| `157caed0` | `gin-gonic/gin` | `edit2ripple` | 2 | `context.go` | `context_test.go` | Rank 1 is query input seed (context.go) |
| `093314dc` | `gin-gonic/gin` | `edit2ripple` | 2 | `context.go` | `context_test.go` | Rank 1 is query input seed (context.go) |
| `f381bbb6` | `gin-gonic/gin` | `edit2ripple` | 3 | `binding/binding.go` | `binding/binding_nomsgpack.go` | Rank 1 is query input seed (binding/binding.go) |
| `845b2c20` | `gin-gonic/gin` | `edit2ripple` | 4 | `binding/form_mapping.go` | `binding/form_mapping_test.go` | Rank 1 is query input seed (binding/form_mapping.go) |
| `a7836555` | `gin-gonic/gin` | `edit2ripple` | 4 | `fs.go` | `routergroup.go` | Rank 1 is query input seed (fs.go) |
| `ec2aa4cf` | `gin-gonic/gin` | `edit2ripple` | 8 | `routergroup.go` | `fs.go` | Rank 1 is query input seed (routergroup.go) |

---

## 4. Test versus implementation confusion (74 Queries, 21.45%)

**Root Cause Analysis:** Query intent requires test files (`code2test`), but ranker surfaces implementation code at Ranks 1–5.

| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `6b1c1cff` | `clap-rs/clap` | `code2test` | 69 | `clap_builder/src/parser/parser.r...` | `tests/builder/ignore_errors.rs` | Rank 1 is impl file (clap_builder/src/parser/parser.rs), gold is test file (tests/builder/ignore_errors.rs) |
| `f39b3eb2` | `clap-rs/clap` | `code2test` | 23 | `clap_mangen/src/render.rs` | `clap_mangen/tests/testsuite/comm...` | Rank 1 is impl file (clap_mangen/src/render.rs), gold is test file (clap_mangen/tests/testsuite/roff.rs) |
| `120f8ebe` | `etcd-io/etcd` | `code2test` | 21 | `server/etcdmain/grpc_proxy.go` | `tests/e2e/etcd_grpcproxy_test.go` | Rank 1 is impl file (server/etcdmain/grpc_proxy.go), gold is test file (tests/e2e/etcd_grpcproxy_test.go) |
| `1dd2bdfd` | `etcd-io/etcd` | `code2test` | 8 | `server/storage/mvcc/index.go` | `server/storage/mvcc/index_test.g...` | Rank 1 is impl file (server/storage/mvcc/index.go), gold is test file (server/storage/mvcc/kvstore_test.go) |
| `29168597` | `etcd-io/etcd` | `code2test` | 10 | `server/etcdserver/txn/txn.go` | `server/etcdserver/txn/txn_test.g...` | Rank 1 is impl file (server/etcdserver/txn/txn.go), gold is test file (server/etcdserver/txn/txn_test.go) |
| `3a9ae9c1` | `etcd-io/etcd` | `code2test` | 63 | `proxy/grpcproxy/watch.go` | `clientv3/integration/lease_test....` | Rank 1 is impl file (proxy/grpcproxy/watch.go), gold is test file (clientv3/integration/lease_test.go) |
| `6338b759` | `etcd-io/etcd` | `code2test` | 25 | `server/etcdmain/config.go` | `tests/e2e/ctl_v3_test.go` | Rank 1 is impl file (server/etcdmain/config.go), gold is test file (tests/framework/e2e/cluster.go) |
| `73fc2431` | `etcd-io/etcd` | `code2test` | 2 | `server/etcdserver/v3_server.go` | `server/etcdserver/util_test.go` | Rank 1 is impl file (server/etcdserver/v3_server.go), gold is test file (server/etcdserver/server_test.go) |
| `7ccc6b7b` | `etcd-io/etcd` | `code2test` | 14 | `etcdctl/ctlv3/command/ep_command...` | `client/v3/config_test.go` | Rank 1 is impl file (etcdctl/ctlv3/command/ep_command.go), gold is test file (client/v3/config_test.go) |
| `810b8fe1` | `etcd-io/etcd` | `code2test` | 144 | `server/etcdserver/server.go` | `tests/integration/v3_alarm_test....` | Rank 1 is impl file (server/etcdserver/server.go), gold is test file (tests/integration/v3_alarm_test.go) |
| `8ab746ff` | `etcd-io/etcd` | `code2test` | 15 | `server/etcdserver/api/v3rpc/watc...` | `tests/integration/v3_auth_test.g...` | Rank 1 is impl file (server/etcdserver/api/v3rpc/watch.go), gold is test file (tests/integration/v3_watch_test.go) |
| `d7a097e1` | `etcd-io/etcd` | `code2test` | 46 | `etcdctl/ctlv3/command/ep_command...` | `tests/e2e/ctl_v3_auth_test.go` | Rank 1 is impl file (etcdctl/ctlv3/command/ep_command.go), gold is test file (tests/e2e/ctl_v3_auth_test.go) |
| `7f2b7ed0` | `fastapi/fastapi` | `code2test` | 4 | `fastapi/responses.py` | `tests/test_tutorial/test_custom_...` | Rank 1 is impl file (fastapi/responses.py), gold is test file (tests/test_orjson_response_class.py) |
| `a56cae40` | `fastapi/fastapi` | `code2test` | 96 | `fastapi/_compat/v2.py` | `tests/test_tutorial/test_custom_...` | Rank 1 is impl file (fastapi/_compat/v2.py), gold is test file (tests/test_tutorial/test_custom_response/test_tutorial001.py) |
| `17ed1867` | `gin-gonic/gin` | `code2test` | 18 | `binding/multipart_form_mapping.g...` | `gin_integration_test.go` | Rank 1 is impl file (binding/multipart_form_mapping.go), gold is test file (gin_integration_test.go) |
| `4efdeafc` | `gin-gonic/gin` | `code2test` | 4 | `binding/binding.go` | `binding/binding_test.go` | Rank 1 is impl file (binding/binding.go), gold is test file (context_test.go) |
| `5c889813` | `gin-gonic/gin` | `code2test` | 7 | `binding/form_mapping.go` | `binding/form_mapping_test.go` | Rank 1 is impl file (binding/form_mapping.go), gold is test file (binding/form_mapping_test.go) |
| `725dd77b` | `gin-gonic/gin` | `code2test` | 5 | `gin.go` | `path_test.go` | Rank 1 is impl file (gin.go), gold is test file (path_test.go) |
| `a29f65fc` | `gin-gonic/gin` | `code2test` | 26 | `context.go` | `binding/form_mapping_test.go` | Rank 1 is impl file (context.go), gold is test file (binding/form_mapping_test.go) |
| `aec3dd1a` | `gin-gonic/gin` | `code2test` | 3 | `context.go` | `context_test.go` | Rank 1 is impl file (context.go), gold is test file (context_test.go) |
| `eb144542` | `gin-gonic/gin` | `code2test` | 2 | `context.go` | `context_test.go` | Rank 1 is impl file (context.go), gold is test file (context_test.go) |
| `b2bcc7a9` | `gin-gonic/gin` | `code2test` | 2 | `binding/form_mapping.go` | `binding/binding_test.go` | Rank 1 is impl file (binding/form_mapping.go), gold is test file (binding/binding_test.go) |
| `c3931963` | `gin-gonic/gin` | `code2test` | 2 | `context.go` | `context_test.go` | Rank 1 is impl file (context.go), gold is test file (context_test.go) |
| `d7869de7` | `gin-gonic/gin` | `code2test` | 7 | `render/html.go` | `render/render_test.go` | Rank 1 is impl file (render/html.go), gold is test file (gin_test.go) |
| `f2f7ad9e` | `gin-gonic/gin` | `code2test` | 5 | `context.go` | `context_test.go` | Rank 1 is impl file (context.go), gold is test file (context_test.go) |
| `95a32599` | `huggingface/diffusers` | `code2test` | 8 | `src/diffusers/pipelines/pipeline...` | `tests/pipelines/test_pipelines.p...` | Rank 1 is impl file (src/diffusers/pipelines/pipeline_utils.py), gold is test file (tests/pipelines/test_pipelines.py) |
| `2a765868` | `huggingface/diffusers` | `code2test` | 46 | `src/diffusers/pipelines/pipeline...` | `tests/pipelines/ltx2/test_ltx2_i...` | Rank 1 is impl file (src/diffusers/pipelines/pipeline_utils.py), gold is test file (tests/pipelines/ltx2/test_ltx2.py) |
| `c7ea7d6f` | `huggingface/diffusers` | `code2test` | 13 | `src/diffusers/modular_pipelines/...` | `tests/modular_pipelines/test_mod...` | Rank 1 is impl file (src/diffusers/modular_pipelines/modular_pipeline.py), gold is test file (tests/modular_pipelines/test_modular_pipelines_common.py) |
| `0a4b3f17` | `huggingface/transformers` | `code2test` | 4 | `src/transformers/integrations/mx...` | `tests/quantization/mxfp4/test_mx...` | Rank 1 is impl file (src/transformers/integrations/mxfp4.py), gold is test file (tests/quantization/mxfp4/test_mxfp4.py) |
| `63104a18` | `huggingface/transformers` | `code2test` | 13 | `src/transformers/models/whisper/...` | `tests/models/whisper/test_tokeni...` | Rank 1 is impl file (src/transformers/models/whisper/tokenization_whisper.py), gold is test file (tests/models/whisper/test_tokenization_whisper.py) |
| `813d9449` | `huggingface/transformers` | `code2test` | 47 | `src/transformers/modeling_utils....` | `tests/models/mt5/test_modeling_m...` | Rank 1 is impl file (src/transformers/modeling_utils.py), gold is test file (tests/models/umt5/test_modeling_umt5.py) |
| `9fb496bd` | `huggingface/transformers` | `code2test` | 8 | `src/transformers/models/smolvlm/...` | `tests/models/smolvlm/test_modeli...` | Rank 1 is impl file (src/transformers/models/smolvlm/video_processing_smolvlm.py), gold is test file (tests/models/smolvlm/test_modeling_smolvlm.py) |
| `a4afc36f` | `huggingface/transformers` | `code2test` | 10 | `src/transformers/generation/cont...` | `tests/generation/test_continuous...` | Rank 1 is impl file (src/transformers/generation/continuous_batching/continuous_api.py), gold is test file (tests/generation/test_continuous_batching.py) |
| `c8318e72` | `huggingface/transformers` | `code2test` | 30 | `src/transformers/utils/generic.p...` | `tests/utils/test_generic.py` | Rank 1 is impl file (src/transformers/utils/generic.py), gold is test file (tests/utils/test_generic.py) |
| `c9059c66` | `huggingface/transformers` | `code2test` | 10 | `src/transformers/generation/cont...` | `tests/generation/test_paged_atte...` | Rank 1 is impl file (src/transformers/generation/continuous_batching/cache.py), gold is test file (tests/generation/test_continuous_batching.py) |
| `d33132ce` | `huggingface/transformers` | `code2test` | 5 | `src/transformers/modeling_utils....` | `tests/utils/test_core_model_load...` | Rank 1 is impl file (src/transformers/modeling_utils.py), gold is test file (tests/test_fsdp_mixin.py) |
| `e2d0725f` | `huggingface/transformers` | `code2test` | 18 | `src/transformers/models/auto/tok...` | `tests/models/auto/test_tokenizat...` | Rank 1 is impl file (src/transformers/models/auto/tokenization_auto.py), gold is test file (tests/models/auto/test_tokenization_auto.py) |
| `94f11ff5` | `mockito/mockito` | `code2test` | 60 | `mockito-core/src/main/java/org/m...` | `mockito-integration-tests/progra...` | Rank 1 is impl file (mockito-core/src/main/java/org/mockito/internal/creation/bytebuddy/InlineBytecodeGenerator.java), gold is test file (mockito-integration-tests/programmatic-tests/src/test/java/org/mockito/ProgrammaticMockMakerTest.java) |
| `2177ce08` | `spring-projects/spring-boot` | `code2test` | 65 | `module/spring-boot-webflux/src/m...` | `module/spring-boot-webflux/src/t...` | Rank 1 is impl file (module/spring-boot-webflux/src/main/java/org/springframework/boot/webflux/autoconfigure/WebFluxProperties.java), gold is test file (module/spring-boot-webflux/src/test/java/org/springframework/boot/webflux/autoconfigure/HttpHandlerAutoConfigurationTests.java) |
| `9c3412df` | `spring-projects/spring-boot` | `code2test` | 8 | `module/spring-boot-session/src/m...` | `module/spring-boot-session-jdbc/...` | Rank 1 is impl file (module/spring-boot-session/src/main/java/org/springframework/boot/session/autoconfigure/SessionAutoConfiguration.java), gold is test file (module/spring-boot-session-data-redis/src/dockerTest/java/org/springframework/boot/session/data/redis/autoconfigure/SessionDataRedisAutoConfigurationTests.java) |
| `1bb41301` | `tokio-rs/tokio` | `code2test` | 26 | `tokio/src/runtime/scheduler/mult...` | `tokio/tests/rt_threaded.rs` | Rank 1 is impl file (tokio/src/runtime/scheduler/multi_thread/worker.rs), gold is test file (tokio/tests/rt_threaded.rs) |
| `290f9b4b` | `tokio-rs/tokio` | `code2test` | 3 | `tokio/src/sync/mpsc/chan.rs` | `tokio/tests/sync_mpsc.rs` | Rank 1 is impl file (tokio/src/sync/mpsc/chan.rs), gold is test file (tokio/tests/sync_mpsc.rs) |
| `3e1ace6b` | `tokio-rs/tokio` | `code2test` | 2 | `tokio/src/sync/watch.rs` | `tokio/tests/sync_watch.rs` | Rank 1 is impl file (tokio/src/sync/watch.rs), gold is test file (tokio/tests/sync_watch.rs) |
| `4630dbe0` | `tokio-rs/tokio` | `code2test` | 3 | `tokio-util/src/codec/framed_impl...` | `tokio-util/tests/framed.rs` | Rank 1 is impl file (tokio-util/src/codec/framed_impl.rs), gold is test file (tokio-util/tests/framed.rs) |
| `65484488` | `tokio-rs/tokio` | `code2test` | 23 | `tokio/src/runtime/blocking/pool....` | `tokio/src/runtime/tests/loom_blo...` | Rank 1 is impl file (tokio/src/runtime/blocking/pool.rs), gold is test file (tokio/src/runtime/tests/loom_blocking.rs) |
| `8ccd4fc7` | `tokio-rs/tokio` | `code2test` | 5 | `tokio/src/macros/try_join.rs` | `tokio/tests/macros_join.rs` | Rank 1 is impl file (tokio/src/macros/try_join.rs), gold is test file (tokio/tests/macros_try_join.rs) |
| `9dec25e4` | `tokio-rs/tokio` | `code2test` | 4 | `tokio/src/time/timeout.rs` | `tokio/tests/time_panic.rs` | Rank 1 is impl file (tokio/src/time/timeout.rs), gold is test file (tokio/tests/time_panic.rs) |
| `a395d9eb` | `tokio-rs/tokio` | `code2test` | 11 | `tokio/src/runtime/enter.rs` | `tokio/tests/rt_common.rs` | Rank 1 is impl file (tokio/src/runtime/enter.rs), gold is test file (tokio/tests/rt_common.rs) |
| `c5186727` | `tokio-rs/tokio` | `code2test` | 91 | `tokio/src/runtime/task/list.rs` | `tokio/tests/rt_threaded.rs` | Rank 1 is impl file (tokio/src/runtime/task/list.rs), gold is test file (tokio/tests/rt_threaded.rs) |
| `eb7fc5c7` | `tokio-rs/tokio` | `code2test` | 6 | `tokio/src/fs/open_options.rs` | `tokio/tests/fs_open_options.rs` | Rank 1 is impl file (tokio/src/fs/open_options.rs), gold is test file (tokio/tests/fs_open_options.rs) |
| `176cf95c` | `vitejs/vite` | `code2test` | 101 | `packages/vite/src/node/plugins/p...` | `playground/assets/__tests__/asse...` | Rank 1 is impl file (packages/vite/src/node/plugins/prepareOutDir.ts), gold is test file (playground/assets/__tests__/assets.spec.ts) |
| `5d512b3d` | `vitejs/vite` | `code2test` | 23 | `packages/vite/src/node/utils.ts` | `packages/vite/src/node/__tests__...` | Rank 1 is impl file (packages/vite/src/node/utils.ts), gold is test file (packages/vite/src/node/__tests__/utils.spec.ts) |
| `4fdbbdc3` | `vitejs/vite` | `code2test` | 143 | `packages/vite/src/node/server/in...` | `packages/vite/src/node/__tests__...` | Rank 1 is impl file (packages/vite/src/node/server/index.ts), gold is test file (packages/vite/src/node/__tests__/plugins/hooks.spec.ts) |
| `5cd819d4` | `vitejs/vite` | `code2test` | 11 | `packages/vite/src/node/server/so...` | `playground/js-sourcemap/__tests_...` | Rank 1 is impl file (packages/vite/src/node/server/sourcemap.ts), gold is test file (playground/js-sourcemap/__tests__/js-sourcemap.spec.ts) |
| `753493cf` | `vitejs/vite` | `code2test` | 98 | `packages/vite/src/node/plugins/c...` | `playground/backend-integration/_...` | Rank 1 is impl file (packages/vite/src/node/plugins/css.ts), gold is test file (playground/backend-integration/__tests__/backend-integration.spec.ts) |
| `874789db` | `vitejs/vite` | `code2test` | 41 | `playground/fs-serve/root/vite.co...` | `playground/fs-serve/__tests__/fs...` | Rank 1 is impl file (playground/fs-serve/root/vite.config-base.js), gold is test file (playground/fs-serve/__tests__/fs-serve.spec.ts) |
| `9b942f47` | `vitejs/vite` | `code2test` | 123 | `packages/vite/src/node/build.ts` | `playground/lib/__tests__/lib.spe...` | Rank 1 is impl file (packages/vite/src/node/build.ts), gold is test file (playground/lib/__tests__/lib.spec.ts) |
| `9cf0a50a` | `vitejs/vite` | `code2test` | 28 | `packages/vite/src/node/plugins/i...` | `playground/js-sourcemap/__tests_...` | Rank 1 is impl file (packages/vite/src/node/plugins/importAnalysis.ts), gold is test file (packages/vite/src/node/__tests__/plugins/import.spec.ts) |
| `9db66acf` | `vitejs/vite` | `code2test` | 300 | `packages/vite/src/node/server/mi...` | `playground/fs-serve/__tests__/fs...` | Rank 1 is impl file (packages/vite/src/node/server/middlewares/transform.ts), gold is test file (playground/fs-serve/__tests__/fs-serve.spec.ts) |
| `a5663509` | `vitejs/vite` | `code2test` | 50 | `packages/vite/src/node/server/en...` | `playground/hmr-full-bundle-mode/...` | Rank 1 is impl file (packages/vite/src/node/server/environments/fullBundleEnvironment.ts), gold is test file (playground/hmr-full-bundle-mode/__tests__/hmr-full-bundle-mode.spec.ts) |
| `a7470b07` | `vitejs/vite` | `code2test` | 28 | `packages/vite/src/node/server/mi...` | `playground/proxy-bypass/__tests_...` | Rank 1 is impl file (packages/vite/src/node/server/middlewares/proxy.ts), gold is test file (playground/proxy-bypass/__tests__/proxy-bypass.spec.ts) |
| `b2b892eb` | `vitejs/vite` | `code2test` | 25 | `packages/vite/src/node/utils.ts` | `packages/vite/src/node/__tests__...` | Rank 1 is impl file (packages/vite/src/node/utils.ts), gold is test file (packages/vite/src/node/__tests__/config.spec.ts) |
| `e66b86e3` | `vitejs/vite` | `code2test` | 20 | `packages/vite/src/node/plugins/r...` | `playground/resolve-tsconfig-path...` | Rank 1 is impl file (packages/vite/src/node/plugins/resolve.ts), gold is test file (playground/resolve-tsconfig-paths/__tests__/resolve.spec.ts) |
| `be31a2fa` | `vitejs/vite` | `code2test` | 54 | `packages/vite/src/module-runner/...` | `packages/vite/src/node/ssr/runti...` | Rank 1 is impl file (packages/vite/src/module-runner/hmrHandler.ts), gold is test file (packages/vite/src/node/ssr/runtime/__tests__/server-runtime.spec.ts) |
| `c81f5402` | `vitejs/vite` | `code2test` | 4 | `playground/glob-import/vite.conf...` | `playground/glob-import/__tests__...` | Rank 1 is impl file (playground/glob-import/vite.config.ts), gold is test file (playground/glob-import/__tests__/glob-import.spec.ts) |
| `c859445c` | `vitejs/vite` | `code2test` | 24 | `packages/vite/src/node/plugins/c...` | `packages/vite/src/node/__tests__...` | Rank 1 is impl file (packages/vite/src/node/plugins/css.ts), gold is test file (packages/vite/src/node/__tests__/build.spec.ts) |
| `cb31b158` | `vitejs/vite` | `code2test` | 293 | `packages/vite/src/node/optimizer...` | `playground/optimize-deps/__tests...` | Rank 1 is impl file (packages/vite/src/node/optimizer/rolldownDepPlugin.ts), gold is test file (playground/optimize-deps/__tests__/optimize-deps.spec.ts) |
| `dbcf0a72` | `vitejs/vite` | `code2test` | 117 | `packages/vite/src/node/plugins/o...` | `packages/vite/src/node/ssr/runti...` | Rank 1 is impl file (packages/vite/src/node/plugins/oxc.ts), gold is test file (packages/vite/src/node/ssr/runtime/__tests__/server-runtime.spec.ts) |
| `fe73fb28` | `vitejs/vite` | `code2test` | 41 | `packages/vite/src/node/plugins/c...` | `packages/vite/src/node/__tests__...` | Rank 1 is impl file (packages/vite/src/node/plugins/css.ts), gold is test file (packages/vite/src/node/__tests__/plugins/css.spec.ts) |
| `58a56ad1` | `vuejs/core` | `code2test` | 29 | `packages/runtime-vapor/src/vdomI...` | `packages/runtime-vapor/__tests__...` | Rank 1 is impl file (packages/runtime-vapor/src/vdomInterop.ts), gold is test file (packages/runtime-vapor/__tests__/hydration.spec.ts) |
| `72a10b94` | `vuejs/core` | `code2test` | 133 | `packages/runtime-vapor/src/compo...` | `packages/runtime-vapor/__tests__...` | Rank 1 is impl file (packages/runtime-vapor/src/componentEmits.ts), gold is test file (packages/runtime-vapor/__tests__/component.spec.ts) |
| `a7c7ef59` | `vuejs/core` | `code2test` | 9 | `packages/runtime-vapor/src/vdomI...` | `packages/runtime-vapor/__tests__...` | Rank 1 is impl file (packages/runtime-vapor/src/vdomInterop.ts), gold is test file (packages/runtime-vapor/__tests__/hydration.spec.ts) |
| `e3045841` | `vuejs/core` | `code2test` | 23 | `packages/runtime-vapor/src/compo...` | `packages-private/vapor-e2e-test/...` | Rank 1 is impl file (packages/runtime-vapor/src/components/Transition.ts), gold is test file (packages-private/vapor-e2e-test/__tests__/transition-group.spec.ts) |
| `ec9507f8` | `vuejs/core` | `code2test` | 39 | `packages/compiler-vapor/src/gene...` | `packages/compiler-vapor/__tests_...` | Rank 1 is impl file (packages/compiler-vapor/src/generators/expression.ts), gold is test file (packages/compiler-vapor/__tests__/transforms/expression.spec.ts) |

---

## 6. Path mismatch (50 Queries, 14.49%)

**Root Cause Analysis:** Gold file resides in a disjoint subtree with little path token overlap; ranker prefers unrelated files.

| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `bad03d80` | `etcd-io/etcd` | `edit2ripple` | 3 | `pkg/featuregate/feature_gate.go` | `server/etcdserver/server_test.go` | Disjoint directory paths: pkg/featuregate/feature_gate.go vs server/etcdserver/server_test.go |
| `2a108bc0` | `gin-gonic/gin` | `trace2code` | 3 | `ginS/gins.go` | `gin.go` | Disjoint directory paths: ginS/gins.go vs gin.go |
| `2097c0a5` | `gin-gonic/gin` | `trace2code` | 6 | `binding/default_validator_test.g...` | `gin.go` | Disjoint directory paths: binding/default_validator_test.go vs gin.go |
| `72f498bd` | `pytest-dev/pytest` | `edit2ripple` | 3 | `doc/en/changelog.rst` | `src/_pytest/runner.py` | Disjoint directory paths: doc/en/changelog.rst vs testing/deprecated_test.py |
| `e6b3d083` | `pytest-dev/pytest` | `code2test` | 24 | `src/_pytest/fixtures.py` | `testing/acceptance_test.py` | Disjoint directory paths: src/_pytest/fixtures.py vs testing/acceptance_test.py |
| `c6555320` | `tokio-rs/tokio` | `comment2context` | 7 | `tokio-util/src/task/join_queue.r...` | `tokio-util/tests/task_join_queue...` | Disjoint directory paths: tokio-util/src/task/join_queue.rs vs tokio-util/tests/task_join_queue.rs |
| `c9f5bf8f` | `etcd-io/etcd` | `comment2context` | 158 | `server/etcdserver/api/rafthttp/s...` | `tests/integration/clientv3/maint...` | Disjoint directory paths: server/etcdserver/api/rafthttp/stream_test.go vs tests/integration/clientv3/maintenance_test.go |
| `19c290f5` | `etcd-io/etcd` | `trace2code` | 2 | `server/proxy/grpcproxy/cache/sto...` | `cache/cache.go` | Disjoint directory paths: server/proxy/grpcproxy/cache/store.go vs cache/cache.go |
| `42f8d463` | `caddyserver/caddy` | `trace2code` | 2 | `modules/caddyhttp/celmatcher.go` | `listeners.go` | Disjoint directory paths: modules/caddyhttp/celmatcher.go vs listeners.go |
| `de059c1c` | `caddyserver/caddy` | `trace2code` | 20 | `modules/caddyhttp/errors.go` | `caddyconfig/httpcaddyfile/tlsapp...` | Disjoint directory paths: modules/caddyhttp/errors.go vs caddyconfig/httpcaddyfile/tlsapp.go |
| `7a8ae85f` | `caddyserver/caddy` | `edit2ripple` | 10 | `modules/caddytls/acmeissuer.go` | `caddyconfig/httpcaddyfile/tlsapp...` | Disjoint directory paths: modules/caddytls/acmeissuer.go vs caddyconfig/httpcaddyfile/tlsapp.go |
| `a726f272` | `caddyserver/caddy` | `edit2ripple` | 26 | `modules/caddytls/acmeissuer.go` | `caddyconfig/httpcaddyfile/option...` | Disjoint directory paths: modules/caddytls/acmeissuer.go vs caddyconfig/httpcaddyfile/options_test.go |
| `0f4d4723` | `gin-gonic/gin` | `trace2code` | 14 | `binding/default_validator_test.g...` | `context.go` | Disjoint directory paths: binding/default_validator_test.go vs context.go |
| `0f88458f` | `gin-gonic/gin` | `trace2code` | 6 | `binding/default_validator_test.g...` | `debug.go` | Disjoint directory paths: binding/default_validator_test.go vs debug.go |
| `1e7cac8c` | `gin-gonic/gin` | `trace2code` | 17 | `binding/default_validator_test.g...` | `recovery.go` | Disjoint directory paths: binding/default_validator_test.go vs recovery.go |
| `73e85c15` | `gin-gonic/gin` | `trace2code` | 8 | `tree_test.go` | `binding/form_mapping.go` | Disjoint directory paths: tree_test.go vs binding/form_mapping.go |
| `9151d23c` | `gin-gonic/gin` | `trace2code` | 2 | `binding/default_validator.go` | `gin.go` | Disjoint directory paths: binding/default_validator.go vs gin.go |
| `98ca5fc6` | `gin-gonic/gin` | `trace2code` | 17 | `binding/default_validator_test.g...` | `recovery.go` | Disjoint directory paths: binding/default_validator_test.go vs recovery.go |
| `a9f6b8ad` | `gin-gonic/gin` | `trace2code` | 4 | `context_test.go` | `render/yaml.go` | Disjoint directory paths: context_test.go vs render/yaml.go |
| `fa19b2ec` | `gin-gonic/gin` | `trace2code` | 5 | `binding/default_validator_test.g...` | `gin.go` | Disjoint directory paths: binding/default_validator_test.go vs gin.go |
| `08d24e63` | `pallets/click` | `trace2code` | 5 | `tests/test_options.py` | `src/click/core.py` | Disjoint directory paths: tests/test_options.py vs src/click/core.py |
| `2bf38b97` | `pallets/click` | `trace2code` | 3 | `tests/test_options.py` | `src/click/core.py` | Disjoint directory paths: tests/test_options.py vs src/click/core.py |
| `2c98330b` | `pallets/click` | `trace2code` | 6 | `tests/test_defaults.py` | `src/click/core.py` | Disjoint directory paths: tests/test_defaults.py vs src/click/core.py |
| `399f735b` | `pallets/click` | `trace2code` | 4 | `tests/test_options.py` | `src/click/core.py` | Disjoint directory paths: tests/test_options.py vs src/click/core.py |
| `461a1aaf` | `pallets/click` | `trace2code` | 4 | `tests/test_utils.py` | `src/click/termui.py` | Disjoint directory paths: tests/test_utils.py vs src/click/termui.py |
| `49589b87` | `pallets/click` | `trace2code` | 2 | `tests/test_options.py` | `src/click/core.py` | Disjoint directory paths: tests/test_options.py vs src/click/core.py |
| `4dfab03e` | `pallets/click` | `trace2code` | 2 | `tests/test_context.py` | `src/click/core.py` | Disjoint directory paths: tests/test_context.py vs src/click/core.py |
| `51fc5202` | `pallets/click` | `trace2code` | 3 | `tests/test_arguments.py` | `src/click/core.py` | Disjoint directory paths: tests/test_arguments.py vs src/click/core.py |
| `6d3773a9` | `pallets/click` | `trace2code` | 2 | `tests/test_options.py` | `src/click/core.py` | Disjoint directory paths: tests/test_options.py vs src/click/core.py |
| `8882930f` | `pallets/click` | `trace2code` | 2 | `tests/test_options.py` | `src/click/core.py` | Disjoint directory paths: tests/test_options.py vs src/click/core.py |
| `8fbcfd32` | `pallets/click` | `trace2code` | 2 | `tests/test_options.py` | `src/click/core.py` | Disjoint directory paths: tests/test_options.py vs src/click/core.py |
| `9372208a` | `pallets/click` | `trace2code` | 4 | `tests/test_options.py` | `src/click/core.py` | Disjoint directory paths: tests/test_options.py vs src/click/core.py |
| `9f0d0d1b` | `pallets/click` | `trace2code` | 4 | `tests/test_utils.py` | `src/click/termui.py` | Disjoint directory paths: tests/test_utils.py vs src/click/termui.py |
| `a4218c7e` | `pallets/click` | `trace2code` | 4 | `tests/test_termui.py` | `src/click/core.py` | Disjoint directory paths: tests/test_termui.py vs src/click/core.py |
| `a94f5208` | `pallets/click` | `trace2code` | 2 | `tests/test_defaults.py` | `src/click/core.py` | Disjoint directory paths: tests/test_defaults.py vs src/click/core.py |
| `af8170e7` | `pallets/click` | `trace2code` | 2 | `tests/test_options.py` | `src/click/types.py` | Disjoint directory paths: tests/test_options.py vs src/click/types.py |
| `bed9a23b` | `pallets/click` | `trace2code` | 2 | `tests/test_commands.py` | `src/click/exceptions.py` | Disjoint directory paths: tests/test_commands.py vs src/click/core.py |
| `bf9f481e` | `pallets/click` | `trace2code` | 2 | `tests/test_defaults.py` | `src/click/core.py` | Disjoint directory paths: tests/test_defaults.py vs src/click/core.py |
| `cdca9bf2` | `pallets/click` | `trace2code` | 2 | `tests/test_commands.py` | `src/click/core.py` | Disjoint directory paths: tests/test_commands.py vs src/click/core.py |
| `d9073750` | `pallets/click` | `trace2code` | 3 | `tests/test_commands.py` | `src/click/core.py` | Disjoint directory paths: tests/test_commands.py vs src/click/core.py |
| `dfa7089d` | `pallets/click` | `trace2code` | 2 | `tests/test_chain.py` | `src/click/core.py` | Disjoint directory paths: tests/test_chain.py vs src/click/core.py |
| `e50d9d50` | `pallets/click` | `trace2code` | 2 | `tests/test_termui.py` | `src/click/core.py` | Disjoint directory paths: tests/test_termui.py vs src/click/core.py |
| `e7f9f3fc` | `pallets/click` | `trace2code` | 4 | `tests/test_termui.py` | `src/click/_termui_impl.py` | Disjoint directory paths: tests/test_termui.py vs src/click/_termui_impl.py |
| `ed5f5fce` | `pallets/click` | `trace2code` | 3 | `tests/test_commands.py` | `src/click/core.py` | Disjoint directory paths: tests/test_commands.py vs src/click/core.py |
| `f4fccd0d` | `pallets/click` | `trace2code` | 24 | `tests/test_formatting.py` | `src/click/exceptions.py` | Disjoint directory paths: tests/test_formatting.py vs src/click/exceptions.py |
| `1132f037` | `tokio-rs/tokio` | `trace2code` | 256 | `tokio/tests/sync_mpsc.rs` | `tokio/src/sync/mpsc/block.rs` | Disjoint directory paths: tokio/tests/sync_mpsc.rs vs tokio/src/sync/mpsc/block.rs |
| `118b720b` | `tokio-rs/tokio` | `trace2code` | 23 | `tokio/tests/sync_mpsc.rs` | `tokio/src/sync/mpsc/chan.rs` | Disjoint directory paths: tokio/tests/sync_mpsc.rs vs tokio/src/sync/mpsc/chan.rs |
| `30a18c73` | `tokio-rs/tokio` | `trace2code` | 6 | `tokio/tests/sync_mpsc.rs` | `tokio/src/sync/mpsc/bounded.rs` | Disjoint directory paths: tokio/tests/sync_mpsc.rs vs tokio/src/sync/mpsc/bounded.rs |
| `34b14301` | `tokio-rs/tokio` | `trace2code` | 18 | `tokio/tests/sync_mpsc.rs` | `tokio/src/sync/mpsc/list.rs` | Disjoint directory paths: tokio/tests/sync_mpsc.rs vs tokio/src/sync/mpsc/chan.rs |
| `954f4ea5` | `tokio-rs/tokio` | `trace2code` | 7 | `tokio/tests/sync_semaphore.rs` | `tokio/src/sync/batch_semaphore.r...` | Disjoint directory paths: tokio/tests/sync_semaphore.rs vs tokio/src/sync/batch_semaphore.rs |

---

## 5. Sibling implementation confusion (32 Queries, 9.28%)

**Root Cause Analysis:** Rank 1 and gold target share the exact same package/directory, but ranker picked the wrong sibling.

| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `b389823a` | `etcd-io/etcd` | `trace2code` | 9 | `server/etcdserver/server.go` | `server/features/etcd_features.go` | Rank 1 (server/etcdserver/server.go) sibling to gold (server/etcdserver/v3_server.go) |
| `c7ce74f4` | `gin-gonic/gin` | `trace2code` | 11 | `binding/binding_test.go` | `binding/form_mapping.go` | Rank 1 (binding/binding_test.go) sibling to gold (binding/form_mapping.go) |
| `5f4c149c` | `gin-gonic/gin` | `code2test` | 9 | `tree_test.go` | `routes_test.go` | Rank 1 (tree_test.go) sibling to gold (routes_test.go) |
| `d3fe4d15` | `gin-gonic/gin` | `trace2code` | 2 | `gin.go` | `tree.go` | Rank 1 (gin.go) sibling to gold (tree.go) |
| `8a121947` | `gin-gonic/gin` | `code2test` | 4 | `context_test.go` | `recovery_test.go` | Rank 1 (context_test.go) sibling to gold (recovery_test.go) |
| `cd5fdafb` | `gin-gonic/gin` | `trace2code` | 6 | `binding/form_mapping_test.go` | `binding/form_mapping.go` | Rank 1 (binding/form_mapping_test.go) sibling to gold (binding/form_mapping.go) |
| `d0551ed5` | `gin-gonic/gin` | `trace2code` | 29 | `binding/binding_test.go` | `binding/form_mapping.go` | Rank 1 (binding/binding_test.go) sibling to gold (binding/form_mapping.go) |
| `0765b7d2` | `gin-gonic/gin` | `trace2code` | 11 | `binding/binding_test.go` | `binding/form_mapping.go` | Rank 1 (binding/binding_test.go) sibling to gold (binding/form_mapping.go) |
| `05041faa` | `gin-gonic/gin` | `trace2code` | 3 | `tree_test.go` | `gin.go` | Rank 1 (tree_test.go) sibling to gold (gin.go) |
| `9a326250` | `huggingface/transformers` | `edit2ripple` | 3 | `src/transformers/training_args.p...` | `src/transformers/modeling_utils....` | Rank 1 (src/transformers/training_args.py) sibling to gold (src/transformers/modeling_utils.py) |
| `d58f6487` | `spring-projects/spring-boot` | `code2test` | 5 | `spring-boot-project/spring-boot-...` | `spring-boot-project/spring-boot-...` | Rank 1 (spring-boot-project/spring-boot-actuator/src/test/java/org/springframework/boot/actuate/env/EnvironmentEndpointWebIntegrationTests.java) sibling to gold (spring-boot-project/spring-boot-actuator/src/test/java/org/springframework/boot/actuate/env/EnvironmentEndpointTests.java) |
| `9212befb` | `tokio-rs/tokio` | `comment2context` | 5 | `tokio/src/runtime/builder.rs` | `tokio/src/runtime/handle.rs` | Rank 1 (tokio/src/runtime/builder.rs) sibling to gold (tokio/src/runtime/runtime.rs) |
| `ae7f8cc6` | `huggingface/transformers` | `comment2context` | 3 | `src/transformers/cli/serving/uti...` | `src/transformers/cli/serving/res...` | Rank 1 (src/transformers/cli/serving/utils.py) sibling to gold (src/transformers/cli/serving/response.py) |
| `5bdeecc5` | `caddyserver/caddy` | `trace2code` | 2 | `caddyconfig/caddyfile/parse_test...` | `caddyconfig/caddyfile/formatter....` | Rank 1 (caddyconfig/caddyfile/parse_test.go) sibling to gold (caddyconfig/caddyfile/parse.go) |
| `9d7b952a` | `caddyserver/caddy` | `trace2code` | 9 | `modules/caddytls/matchers_test.g...` | `modules/caddytls/acmeissuer.go` | Rank 1 (modules/caddytls/matchers_test.go) sibling to gold (modules/caddytls/acmeissuer.go) |
| `eb750774` | `caddyserver/caddy` | `trace2code` | 6 | `caddyconfig/caddyfile/parse_test...` | `caddyconfig/caddyfile/parse.go` | Rank 1 (caddyconfig/caddyfile/parse_test.go) sibling to gold (caddyconfig/caddyfile/parse.go) |
| `f7d79ec3` | `caddyserver/caddy` | `trace2code` | 2 | `modules/caddyhttp/metrics_test.g...` | `modules/caddyhttp/routes.go` | Rank 1 (modules/caddyhttp/metrics_test.go) sibling to gold (modules/caddyhttp/metrics.go) |
| `13dc9868` | `gin-gonic/gin` | `trace2code` | 3 | `render/render_test.go` | `render/data.go` | Rank 1 (render/render_test.go) sibling to gold (render/data.go) |
| `24b8f50a` | `gin-gonic/gin` | `trace2code` | 21 | `binding/binding_test.go` | `binding/form_mapping.go` | Rank 1 (binding/binding_test.go) sibling to gold (binding/form_mapping.go) |
| `30fb9ae3` | `gin-gonic/gin` | `trace2code` | 8 | `context_test.go` | `response_writer.go` | Rank 1 (context_test.go) sibling to gold (response_writer.go) |
| `3bd1eecf` | `gin-gonic/gin` | `trace2code` | 2 | `binding/form_mapping_test.go` | `binding/form_mapping.go` | Rank 1 (binding/form_mapping_test.go) sibling to gold (binding/form_mapping.go) |
| `4480edb6` | `gin-gonic/gin` | `trace2code` | 2 | `debug_test.go` | `debug.go` | Rank 1 (debug_test.go) sibling to gold (debug.go) |
| `4ac3545d` | `gin-gonic/gin` | `trace2code` | 4 | `context.go` | `recovery.go` | Rank 1 (context.go) sibling to gold (recovery.go) |
| `589abc55` | `gin-gonic/gin` | `trace2code` | 2 | `context_test.go` | `context.go` | Rank 1 (context_test.go) sibling to gold (context.go) |
| `8c235537` | `gin-gonic/gin` | `trace2code` | 9 | `binding/form_mapping_test.go` | `binding/form_mapping.go` | Rank 1 (binding/form_mapping_test.go) sibling to gold (binding/form_mapping.go) |
| `95131f4a` | `gin-gonic/gin` | `trace2code` | 2 | `gin.go` | `tree.go` | Rank 1 (gin.go) sibling to gold (tree.go) |
| `9e63d7a0` | `gin-gonic/gin` | `trace2code` | 11 | `context.go` | `errors.go` | Rank 1 (context.go) sibling to gold (errors.go) |
| `a69837e5` | `gin-gonic/gin` | `trace2code` | 2 | `context_test.go` | `context.go` | Rank 1 (context_test.go) sibling to gold (context.go) |
| `b8c820bb` | `gin-gonic/gin` | `trace2code` | 13 | `binding/binding_test.go` | `binding/form_mapping.go` | Rank 1 (binding/binding_test.go) sibling to gold (binding/form_mapping.go) |
| `cc9de6b2` | `gin-gonic/gin` | `trace2code` | 10 | `logger_test.go` | `logger.go` | Rank 1 (logger_test.go) sibling to gold (logger.go) |
| `e843a55e` | `gin-gonic/gin` | `trace2code` | 6 | `context_test.go` | `context.go` | Rank 1 (context_test.go) sibling to gold (context.go) |
| `e8f3298d` | `gin-gonic/gin` | `trace2code` | 2 | `context_test.go` | `context.go` | Rank 1 (context_test.go) sibling to gold (context.go) |

---

## Rank 1 Success (31 Queries, 8.99%)

**Root Cause Analysis:** Gold file correctly identified and placed at Rank 1 ($R_1 = 1$).

| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `a9432b3d` | `etcd-io/etcd` | `trace2code` | 1 | `cache/demux.go` | `cache/demux.go` | Gold target placed at Rank 1 |
| `46cbbb20` | `gin-gonic/gin` | `code2test` | 1 | `routes_test.go` | `routes_test.go` | Gold target placed at Rank 1 |
| `d5a6bc19` | `gin-gonic/gin` | `trace2code` | 1 | `context.go` | `binding/binding_nomsgpack.go` | Gold target placed at Rank 1 |
| `c0681692` | `gin-gonic/gin` | `trace2code` | 1 | `context.go` | `context.go` | Gold target placed at Rank 1 |
| `4c232faf` | `gin-gonic/gin` | `trace2code` | 1 | `context.go` | `context.go` | Gold target placed at Rank 1 |
| `7db765ce` | `gin-gonic/gin` | `trace2code` | 1 | `gin.go` | `render/html.go` | Gold target placed at Rank 1 |
| `fbf9c4f7` | `gin-gonic/gin` | `code2test` | 1 | `routes_test.go` | `routes_test.go` | Gold target placed at Rank 1 |
| `a82117a5` | `huggingface/transformers` | `code2test` | 1 | `tests/models/pe_audio_video/test...` | `tests/models/pe_audio_video/test...` | Gold target placed at Rank 1 |
| `8a60031f` | `spring-projects/spring-boot` | `code2test` | 1 | `spring-boot-project/spring-boot-...` | `spring-boot-project/spring-boot-...` | Gold target placed at Rank 1 |
| `d63c6816` | `etcd-io/etcd` | `trace2code` | 1 | `server/proxy/grpcproxy/adapter/c...` | `server/proxy/grpcproxy/adapter/c...` | Gold target placed at Rank 1 |
| `d4149b3f` | `caddyserver/caddy` | `trace2code` | 1 | `modules/caddyhttp/caddyauth/cadd...` | `modules/caddyhttp/caddyauth/cadd...` | Gold target placed at Rank 1 |
| `2d65eeb2` | `clap-rs/clap` | `trace2code` | 1 | `clap_builder/src/builder/arg.rs` | `clap_builder/src/builder/arg.rs` | Gold target placed at Rank 1 |
| `035c3b77` | `gin-gonic/gin` | `trace2code` | 1 | `logger.go` | `logger.go` | Gold target placed at Rank 1 |
| `34b3f2f2` | `gin-gonic/gin` | `trace2code` | 1 | `gin.go` | `gin.go` | Gold target placed at Rank 1 |
| `4543cc1c` | `gin-gonic/gin` | `trace2code` | 1 | `logger.go` | `logger.go` | Gold target placed at Rank 1 |
| `4882164f` | `gin-gonic/gin` | `trace2code` | 1 | `tree.go` | `tree.go` | Gold target placed at Rank 1 |
| `4af738a8` | `gin-gonic/gin` | `trace2code` | 1 | `context.go` | `context.go` | Gold target placed at Rank 1 |
| `5bc1aa35` | `gin-gonic/gin` | `trace2code` | 1 | `recovery.go` | `recovery.go` | Gold target placed at Rank 1 |
| `5eeea2e7` | `gin-gonic/gin` | `trace2code` | 1 | `context.go` | `context.go` | Gold target placed at Rank 1 |
| `5fe7a88d` | `gin-gonic/gin` | `trace2code` | 1 | `binding/form_mapping.go` | `binding/form_mapping.go` | Gold target placed at Rank 1 |
| `6c6d138c` | `gin-gonic/gin` | `trace2code` | 1 | `logger.go` | `logger.go` | Gold target placed at Rank 1 |
| `81012a10` | `gin-gonic/gin` | `trace2code` | 1 | `gin.go` | `gin.go` | Gold target placed at Rank 1 |
| `82a5db6d` | `gin-gonic/gin` | `trace2code` | 1 | `context.go` | `context.go` | Gold target placed at Rank 1 |
| `85a691c2` | `gin-gonic/gin` | `trace2code` | 1 | `context.go` | `context.go` | Gold target placed at Rank 1 |
| `89958959` | `gin-gonic/gin` | `trace2code` | 1 | `context.go` | `context.go` | Gold target placed at Rank 1 |
| `94882dae` | `gin-gonic/gin` | `trace2code` | 1 | `gin.go` | `gin.go` | Gold target placed at Rank 1 |
| `a72e294e` | `gin-gonic/gin` | `trace2code` | 1 | `context.go` | `context.go` | Gold target placed at Rank 1 |
| `a9c4956e` | `gin-gonic/gin` | `trace2code` | 1 | `context.go` | `render/render.go` | Gold target placed at Rank 1 |
| `c4a057d9` | `gin-gonic/gin` | `trace2code` | 1 | `binding/default_validator.go` | `binding/default_validator.go` | Gold target placed at Rank 1 |
| `ddc4c496` | `gin-gonic/gin` | `trace2code` | 1 | `fs.go` | `fs.go` | Gold target placed at Rank 1 |
| `27801f38` | `pallets/click` | `trace2code` | 1 | `src/click/core.py` | `src/click/types.py` | Gold target placed at Rank 1 |

---

## 8. Structural relationship error (6 Queries, 1.74%)

**Root Cause Analysis:** Unconditioned graph expansion boosted an architectural hub file while gold file lacked structural link.

| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `d65a03b1` | `gin-gonic/gin` | `trace2code` | 4 | `context.go` | `binding/form_mapping.go` | Distractor boosted by structural expansion (972.5) |
| `eb415665` | `huggingface/transformers` | `edit2ripple` | 1741 | `src/transformers/core_model_load...` | `src/transformers/integrations/fi...` | Distractor boosted by structural expansion (2801.2) |
| `2bbbe7ec` | `pytest-dev/pytest` | `code2test` | 7 | `src/_pytest/deprecated.py` | `testing/test_unittest.py` | Distractor boosted by structural expansion (481.5) |
| `3fd987cc` | `etcd-io/etcd` | `comment2context` | 2 | `pkg/proxy/server_test.go` | `tests/integration/clientv3/maint...` | Distractor boosted by structural expansion (335.6) |
| `12951fd6` | `gin-gonic/gin` | `trace2code` | 15 | `context.go` | `binding/form_mapping.go` | Distractor boosted by structural expansion (1201.0) |
| `c727abdb` | `pytest-dev/pytest` | `trace2code` | 3 | `testing/python/show_fixtures_per...` | `src/_pytest/fixtures.py` | Distractor boosted by structural expansion (1694.0) |

---

## 2. Identifier mismatch (3 Queries, 0.87%)

**Root Cause Analysis:** Gold file lacked query identifier match, while top displacer matched symbols prominently.

| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `117ee2d9` | `etcd-io/etcd` | `edit2ripple` | 472 | `pkg/featuregate/feature_gate.go` | `server/etcdmain/help.go` | Gold lacks query identifier (exact_symbol: 0.06) |
| `e0a0b8ad` | `etcd-io/etcd` | `code2test` | 3 | `client/pkg/testutil/recorder.go` | `server/etcdserver/api/v3compacto...` | Gold lacks query identifier (exact_symbol: 0.22) |
| `5a834c21` | `pytest-dev/pytest` | `code2test` | 56 | `testing/test_subtests.py` | `src/_pytest/unittest.py` | Gold lacks query identifier (exact_symbol: 0.15) |

---

## 10. Other / Unclassified (3 Queries, 0.87%)

**Root Cause Analysis:** Residual complex displacements requiring multi-hop contextual reasoning.

| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `2ab29030` | `huggingface/transformers` | `edit2ripple` | 4 | `src/transformers/integrations/in...` | `src/transformers/modeling_utils....` | General ranking displacement (first gold rank 4) |
| `db9648de` | `astral-sh/ruff` | `comment2context` | 5 | `crates/ty_python_core/src/builde...` | `crates/ty_python_semantic/src/ty...` | General ranking displacement (first gold rank 5) |
| `b872b8ef` | `tokio-rs/tokio` | `trace2code` | 2 | `tokio/src/sync/tests/loom_notify...` | `tokio/src/sync/notify.rs` | General ranking displacement (first gold rank 2) |

---

## 7. Symbol definition mismatch (2 Queries, 0.58%)

**Root Cause Analysis:** Symbol defined in gold file was placed behind files containing multiple references/usages.

| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `c2af1d61` | `tokio-rs/tokio` | `comment2context` | 20 | `tokio/src/runtime/local_runtime/...` | `tokio/src/runtime/mod.rs` | Symbol found in gold (tokio/src/runtime/scheduler/mod.rs) but placed at rank 20 behind usages |
| `056f7ac0` | `vitejs/vite` | `comment2context` | 91 | `packages/create-vite/src/index.t...` | `packages/create-vite/template-li...` | Symbol found in gold (packages/create-vite/template-lit-ts/src/my-element.ts) but placed at rank 91 behind usages |

---

## 1. Lexical mismatch (1 Queries, 0.29%)

**Root Cause Analysis:** Severe lexical term dilution where high-frequency tokens in unrelated files outweighed gold.

| Query ID | Repository | Task Track | First Gold Rank ($R_1$) | Top 1 Candidate | First Gold Target | Specific Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `aac6e017` | `gin-gonic/gin` | `trace2code` | 61 | `tree_test.go` | `binding/form_mapping.go` | Lexical score ratio: gold 99.2 vs top1 596.2 |

---
