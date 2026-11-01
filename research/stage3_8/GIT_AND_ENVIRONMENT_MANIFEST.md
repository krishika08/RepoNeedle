# RepoNeedle Stage 3.8: Git & Environment Manifest

---

## 1. Repository & Branch State

- **Repository Root**: `F:\RepoNeedle`
- **Active Branch**: `research/stage3_8`
- **Starting Git Commit**: `f61c6be926fa4df0caaba5a1bff5a0c2a00794d2`
- **Git Working Tree Status**: Clean (except uncommitted Stage 3.8 artifacts and regression tests)

---

## 2. Frozen Baseline Tags Verification

The immutable benchmark baseline tags are strictly verified and immutable:

| Tag Name | Target Commit Hash | Annotation / Description | Integrity Status |
|---|---|---|:---:|
| `v0.1.0-baseline` | `8e0042553a14b6e3c6cf5b35823c4da84181a8e9` | Baseline RepoNeedle v0.1.0 with full ARB v2 validation (427 samples) | **VERIFIED (Unchanged)** |
| `stage3-candidate-freeze` | `cd7f3b01e28695f9a9357e0815069e0eae85baca` | Stage 3 Experimental Candidate Freeze: Candidates A through E + Baselines | **VERIFIED (Unchanged)** |

---

## 3. Execution Environment

- **Operating System**: Microsoft Windows 11 Pro (win32)
- **Primary Shell**: PowerShell 5.1 / 7
- **Python Version**: Python 3.12.10
- **Pytest Version**: 9.1.1 (pluggy 1.6.0)
- **Key Installed Packages**:
  - `numpy`: 2.2.4
  - `scipy`: 1.15.2
  - `networkx`: 3.4.2
  - `ctypes` / Windows `kernel32` + `psapi`: Built-in Windows DLLs

---

## 4. Test Suite Health

- **Total Collected Tests**: 249 items
- **Passed Tests**: 249 passed (100%)
- **Failed Tests**: 0
- **Execution Time**: ~8.36 seconds

---

## 5. Stage 3.8 Core Scripts Checksums (SHA-256)

| File Path | SHA-256 Checksum |
|---|---|
| `research/stage3_8/scripts/evaluate_stage3_8_experiments.py` | `a9fa4077c7a72ccdfab5a0563373777779c43968e6c97f243db2760d13392180` |
| `research/stage3_8/scripts/compute_stage3_8_statistics.py` | `2864309cf2ab34eac8d020830edd55dc91648034cd0d33d111ee9f4699d4fcd3` |
| `research/stage3_8/scripts/benchmark_runtime_and_memory.py` | `36ad8436ef3b7fe00a5d3928ed233ebc4ca521c744fbc19de21758f50a6e3a4d` |
| `research/stage3_8/scripts/diagnose_repository_regressions.py` | `0fe628edb00eb2b9487da6d561e2e3959f91477d4fb49347353ed93456771137` |
| `research/stage3_8/scripts/explore_query_conditioning.py` | `db3b96347bcc39de0daeb87740b30957beb4f41612c1fbdaf160a7021b2b7e32` |
| `tests/test_stage3_8_query_conditioned_graph.py` | `c0f9da7b73816694e9f4eb84e54546413d31d4dcf9c98bc0151125268c12a7d6` |

