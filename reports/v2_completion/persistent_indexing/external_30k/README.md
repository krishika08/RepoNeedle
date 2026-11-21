# RepoNeedle V2 Stage 4.1: external 30,000-file scalability benchmark

This package runs the RepoNeedle Stage 4 benchmark harness, unmodified, at **30,000 reduced files**. It compares three revisions in the same rounds, on a Windows machine with 32–64 GB of RAM. The run needs a bigger machine than the 16 GB laptop used so far: there, Stage 3 commits about 7.9 GiB at 30,000 files, and other software leaves too little memory free for clean phases.

The package changes nothing in RepoNeedle: no production code, no harness and no worktree. It prepares the machine, runs the harness with the recorded methodology, records the conditions before and after the run, and validates the output independently.

> **Results are not claims.** A run produces raw data and a validation report for independent review. Do not copy numbers into a report, PR, changelog or design document, and do not merge them into `stage4_1_benchmark.json`, until the results have been reviewed.

## Revisions

| Name in the results | Revision | Commit | Tree |
| :--- | :--- | :--- | :--- |
| `baseline` | Stage 3, merged `main` | `60fbfc072dcb35209aaea113ecd4162a9092a432` | `5491ca89c71f5c22e5405072845ac7996eeaed94` |
| `intern` | Stage 4, PR #28 head (`sys.intern`) | `643fa228a9ca01cf0088aa078f20856d77a4790e` | `e6e41e1b83be3e6c117e883590b19c3d0ee83223` |
| `candidate` | Stage 4.1, PR #29 head (shared feature dictionary) | `42b59bb13fab027e104e31f3faf22d6069f9310c` | `49d760cee81960faeee26988744ae616b374ab5c` |

- `42b59bb`'s production code is identical to `41991e8`, the candidate of the 10,000-file round; the commits between them change only docs and benchmark data.
- The generator (`stage1_benchmark.py`), the Stage 2 and Stage 3 harnesses and `tests/index_equivalence.py` are the same git blobs in all three revisions.
- The harness that runs is `reports/v2_completion/persistent_indexing/stage4_benchmark.py` at `42b59bb`.

## Contents

| File | Purpose |
| :--- | :--- |
| `rn30k.py` | Orchestrator, with the commands `setup`, `preflight`, `run` and `validate` |
| `verify_datasets.py` | Regenerates a corpus with the candidate's own generator and compares its manifest SHA-256 |
| `expected.json` | Commits, trees, dataset manifests, benchmark arguments, Python version, and the memory and power policy |
| `requirements-lock.txt` | The exact runtime dependencies of the recorded runs, pinned by SHA-256 |
| `reponeedle_30k.bundle` | Git bundle with the three revisions, for offline setup. It is in the zip only, not in the repository copy, which fetches the same commits from GitHub (`--source github`, the default when no bundle is present) |
| `SHA256SUMS.txt` | Checksums of the files above (zip only; in the repository, git provides integrity) |

## Requirements

- **OS:** Windows 10 or 11, or Windows Server 2019 or later, x64. The memory, power and sleep probes are Windows-only.
- **RAM:** 32–64 GB installed, with at least 16 GiB available when the run starts. Preflight refuses to start otherwise.
- **Disk:** 10 GB free on the work directory's drive. An SSD is best. The run needs about 1.5 GB: one 46 MB corpus copy and one 386 MB cache per revision.
- **Python:** CPython **3.12.10**, 64-bit, from the python.org installer, with the `py` launcher. This is the exact version of the recorded runs; other versions are refused.
- **Git for Windows.**
- **Network** for setup only: `pip` downloads the locked wheels from PyPI. `--source github` also fetches the commits from GitHub.

### Cloud VMs

- Use an instance with **dedicated, non-burstable vCPUs**: not Azure B-series, AWS T-series or GCE shared-core types. Their CPU credits throttle silently, and no probe here detects that.
- Use at least 8 vCPUs, and run nothing else on the VM.
- Record the instance type in your notes. Preflight records the manufacturer and model, the CPU, cores, RAM and disks, but not the cloud SKU.
- An RDP disconnect does not stop the run. Do not let the VM shut itself down: the harness requests keep-awake for the duration, but cloud auto-shutdown policies override it.

### Power: `--require-ac` stays on

The harness reads `GetSystemPowerStatus` before and after every phase. `--require-ac` waits for 30 s of mains power before each phase, and a phase that starts or ends on battery is excluded. This package never turns that off. Preflight classifies the machine as follows:

| `BatteryFlag` / `ACLineStatus` | Classification | Result |
| :--- | :--- | :--- |
| 128 (no system battery) / 1 or 255 | `not_applicable_no_system_battery`: desktops, servers, most VMs | Accepted; recorded explicitly at preflight and postflight |
| any other / 1 | `mains` (laptop plugged in) | Accepted |
| any other / 0 | `battery` | Refused; plug in and retry |
| any other / 255 | `unknown_with_battery` | Refused: throttling could not be detected |

- On a machine without a battery that reports AC as unknown (255), the harness records each phase's `ac_power` as `[null, null]`, and `--require-ac` proceeds after its 30 s wait.
- The validator accepts `null` only when preflight *and* postflight both recorded `not_applicable_no_system_battery`. Otherwise an unknown power state fails validation, so it is never silently counted as mains.

## Steps

Run every command from a normal PowerShell window in the package directory. Use a work directory on a local disk, for example `C:\rn30k`.

1. **Copy and check the package.** Compare each file with `SHA256SUMS.txt`, for example `Get-FileHash .\reponeedle_30k.bundle -Algorithm SHA256`.
2. **Set up.** This takes about 2 minutes:
   ```powershell
   py -3.12 rn30k.py setup --workdir C:\rn30k
   ```
   Setup does the following:
   - creates a repository at `C:\rn30k\src` with `core.autocrlf=true`, as in the recorded runs;
   - fetches the bundle, or GitHub with `--source github`;
   - adds three detached worktrees under `C:\rn30k\trees`;
   - checks each worktree's commit SHA, tree SHA and clean status;
   - creates `C:\rn30k\venv` and installs the lock with `--require-hashes --no-deps`.

   **RepoNeedle itself is never installed:** each revision runs from its own worktree.
3. **Smoke test.** This takes about 25 minutes, almost all of it the 30 s `--require-ac` wait before each of the 45 child runs. It checks the whole pipeline on a small corpus:
   ```powershell
   py -3.12 rn30k.py run --workdir C:\rn30k --smoke-files 300
   ```
   The expected status is `SMOKE_PASS`. A smoke result is never a benchmark result.
4. **Prepare the machine.** Close all other applications, plug in the power if it has a battery, and disable scheduled scans and updates for the duration if you can.
5. **Full run.** Plan for **2.5–3.5 hours**. On the reference laptop (18 logical CPUs) one round of the three revisions takes about 35 minutes of building. `--require-ac` adds 30 s before each of the 15 child runs per round (about 23 minutes over 3 rounds), and the component-memory builds come on top of that.
   ```powershell
   py -3.12 rn30k.py run --workdir C:\rn30k
   ```
   Do not use the machine while it runs. The output goes to a new directory, `C:\rn30k\results\<UTC timestamp>\`.
6. **Return the whole results directory,** zipped as it is.

To check the conditions without running anything: `py -3.12 rn30k.py preflight --workdir C:\rn30k`.

## What `run` does

1. **Preflight** (`preflight.json`; the run stops if any check fails). It checks:
   - Windows, CPython 3.12.10 64-bit, and the package's venv;
   - every installed distribution against the lock, and that `reponeedle` is not installed;
   - each worktree's commit, tree and clean status, plus `core.autocrlf`;
   - that each revision's child process imports `reponeedle` from its own worktree;
   - that the harness parent process imports no `reponeedle` module;
   - the power classification;
   - total RAM of at least 30 GiB, and at least 16 GiB available;
   - 10 GB of free disk;
   - CPU busy at most 25% over a 10 s sample;
   - the 30,000-file corpus, regenerated, against manifest SHA-256 `9498fea5849c70bd31cde5e0025fb2edc82e47d9cb24546d7cebab6791326d94` (`dataset_verification.json`).

   It also records the execution environment: OS edition and build, CPU model, cores and clock, RAM and page file, whether this is a VM and which, the power plan, the disks, every installed distribution, and the Git version. Host names, user names and local paths are not recorded.
2. **Benchmark.** It runs exactly this:
   ```
   python stage4_benchmark.py --baseline-root trees\stage3_60fbfc0 --extra-root intern=trees\stage4_643fa22 ^
       --files 30000 --profile reduced --rounds 3 --verify --component-memory --require-ac ^
       --out stage4_1_benchmark_30k.json
   ```
   It writes `stage4_1_benchmark_30k.json`, then `stage4_1_benchmark_30k.md`, which the harness renders from the JSON, and `harness.log`. The environment is the run's, with three changes:
   - `PYTHONPATH`, `PYTHONHASHSEED` and `PYTHONHOME` are removed;
   - `TEMP` and `TMP` point to `C:\rn30k\tmp`;
   - the harness itself sets `PYTHONHASHSEED=0` for the digest builds.
3. **Postflight** (`postflight.json`): the power state, available memory and the harness exit code.
4. **Validation** (`validation.json`), described in the next section.
5. **`SHA256SUMS.txt`** over every file in the results directory.

The harness saves the JSON after every round, so an interrupted run keeps the rounds it finished. Start any rerun in a new results directory. `run` refuses to write into a non-empty one, because the harness would overwrite the workload's earlier raw data.

## Methodology (unchanged)

- **Dataset:** `stage1-generator/reduced/30000/seed-7`, generator `stage1_benchmark.generate/seed-7 + stage4-manifest/1`, 30,000 files, 46,158,970 bytes. The manifest SHA-256 covers every file's path and content digest. The 10,000 reduced (`4d7140fe…`), 10,000 realistic (`32b89259…`) and 30,000 reduced (`9498fea5…`) corpora all regenerate byte-identically from `42b59bb`, and `expected.json` records where each value comes from.
- **Per round and revision:** an uncached build, a cold cached build, and an unchanged warm restart. Each records:
  - engine phase timings, the semantic-fit timer, peak working set and peak committed memory;
  - available memory at the start, peak WAL, the maximum heartbeat gap, and the power state;
  - retrieval latency for 25 fixed queries on the warm engine.
- **Rotation:** the three revisions are rotated so that each round starts with a different one.
- **Verification** (`--verify`): every round rebuilds each revision warm and uncached with `PYTHONHASHSEED=0`. All six digests of the complete index and retrieval state must be identical, and the validator also requires one digest across all 18.
- **Component memory** (`--component-memory`): once per revision, an uncached build measures the deep retained size of each engine component.
- **Isolation:** every phase, digest build and component-memory build runs in a fresh `python -c` child process, which exits when it finishes. The harness parent imports no `reponeedle` module, and preflight checks this, so no engine object outlives its phase or crosses to another revision. Each revision starts from a fresh copy of the corpus and an empty cache.
- **Exclusions:** a phase stays in the raw JSON with its flags and is left out of the summary statistics if:
  - its peak committed memory exceeded the memory available when it started (`paging_suspected`);
  - its heartbeat gap exceeded 5 s (`suspended_suspected`);
  - it started or ended on battery (`on_battery_suspected`).

  The harness's 12 GiB memory watchdog stays at its default. Nothing is extrapolated.

## Validation statuses

`rn30k.py validate --results <dir> [--workdir C:\rn30k]` can be re-run anywhere, for example by an independent reviewer. With `--workdir`, it also checks that the Markdown is exactly the harness's rendering of the JSON.

| Status | Meaning |
| :--- | :--- |
| `PASS` | Every required check passed and no phase was excluded. |
| `PASS_WITH_EXCLUSIONS` | Every required check passed, but some phases were excluded. They are listed with their flags, with clean rounds counted per revision and phase, and their raw data is kept. Fewer than 3 clean rounds in any cell means a reviewer should decide whether to rerun. |
| `FAIL` | A required check failed. The results must not be used. |

The required checks are:
- exact commits, clean trees and version 1.2.0;
- Python and dependency versions;
- the exact benchmark flags (`--files 30000 --profile reduced --rounds 3 --verify --component-memory --require-ac`);
- preflight passed;
- only the 30,000-file workload is present, with the expected manifest SHA-256;
- three rounds with rotated revision order, and every phase completed with the `--require-ac` wait recorded;
- no failed or aborted phase;
- identical digests in every round, and one digest across all 18;
- component memory for all three revisions at 30,000 documents;
- a reliable power state for every phase;
- no sleep or standby events, and keep-awake requested;
- the validator's exclusions agree with the harness's.

## Do not

- Install RepoNeedle (`pip install -e .`) into the venv, or edit, check out or build inside a worktree. Any of these makes a revision unclean or changes which code runs.
- Change the benchmark flags, the memory limit or the Python version.
- Reuse a results directory, or merge these results into the committed benchmark JSON files.
- Merge PRs, create tags or publish releases on the strength of a run.

## Troubleshooting

| Symptom | What to do |
| :--- | :--- |
| `preflight failed: ['memory']` | Close applications, or use a larger machine. Each phase is compared with the memory free when it starts. |
| `preflight failed: ['cpu_idle']` | Something is using the CPU. Wait for updates or scans to finish. |
| `preflight failed: ['power']` | Plug in the power. On a VM reporting `unknown_with_battery`, use a different instance type. |
| `preflight failed: ['dataset']` | The corpus differs from the recorded one. Check the Python version and that the trees are clean, and report it; do not run. |
| `preflight failed: ['revisions']` | A worktree was modified. Delete the work directory and run `setup` again. |
| Status `FAIL` after the run | `validation.json` names the failed requirements. Keep the directory, which is evidence, and rerun into a new one. |
