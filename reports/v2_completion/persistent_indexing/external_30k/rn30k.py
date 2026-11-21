"""
RepoNeedle V2 Stage 4.1: external 30,000-file scalability benchmark (Windows, 32-64 GB RAM).

Runs the unmodified Stage 4 harness (stage4_benchmark.py at 42b59bb) over Stage 3 (60fbfc0), Stage 4 (643fa22) and
Stage 4.1 (42b59bb) with the recorded methodology. This orchestrator never edits a worktree and never changes a
measurement: it prepares and checks the environment, runs the harness, records conditions before and after, and
validates the result independently.

    py -3.12 rn30k.py setup    --workdir C:\\rn30k                # worktrees, venv, locked dependencies
    py -3.12 rn30k.py run      --workdir C:\\rn30k                # preflight -> benchmark -> postflight -> validate
    py -3.12 rn30k.py validate --results <results dir> [--workdir C:\\rn30k]

See README.md.
"""

import argparse
import ctypes
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
EXPECTED = json.loads((PACKAGE / "expected.json").read_text(encoding="utf-8"))
LOCK = PACKAGE / "requirements-lock.txt"
BUNDLE = PACKAGE / "reponeedle_30k.bundle"
GITHUB = "https://github.com/krishika08/RepoNeedle.git"
TREE_DIRS = {"baseline": "stage3_60fbfc0", "intern": "stage4_643fa22", "candidate": "stage4_1_42b59bb"}
BENCH_REL = Path("reports") / "v2_completion" / "persistent_indexing"
FULL_FILES = 30000
OUT_JSON = "stage4_1_benchmark_30k.json"
SMOKE_JSON = "stage4_1_benchmark_smoke.json"
GIB = 2 ** 30
MAX_PREFLIGHT_CPU_BUSY = 25.0       # percent, 10-second sample before the run
ALLOWED_EXTRA_DISTRIBUTIONS = {"pip"}


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def die(msg: str) -> None:
    print(f"\nERROR: {msg}", flush=True)
    sys.exit(2)


def git(*args, cwd=None) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        die(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def paths(workdir: str) -> dict:
    w = Path(workdir).resolve()
    return {"work": w, "src": w / "src", "trees": w / "trees", "venv": w / "venv",
            "py": w / "venv" / "Scripts" / "python.exe", "tmp": w / "tmp", "results": w / "results",
            **{k: w / "trees" / d for k, d in TREE_DIRS.items()}}


def lock_pins() -> dict:
    pins = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            name, ver = line.split()[0].split("==")
            pins[canon(name)] = ver
    return pins


def canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# ------------------------------------------------------------------------------------------------- Windows probes

def power_status() -> dict:
    """GetSystemPowerStatus, raw, plus a classification (see expected.json power_policy)."""
    if sys.platform != "win32":
        return {"available": False, "classification": "unsupported_platform", "ok": False}

    class S(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                    ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                    ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
    s = S()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
        return {"available": False, "classification": "query_failed", "ok": False, "utc": utc()}
    ac, flag = s.ACLineStatus, s.BatteryFlag
    if flag == 128:                         # "No system battery": desktops, servers and most cloud VMs
        cls, ok = "not_applicable_no_system_battery", ac in (1, 255)
    elif ac == 1:
        cls, ok = "mains", True
    elif ac == 0:
        cls, ok = "battery", False
    else:                                   # AC state unknown on a machine that has (or may have) a battery
        cls, ok = "unknown_with_battery", False
    return {"available": True, "utc": utc(), "ACLineStatus": ac, "BatteryFlag": flag,
            "BatteryLifePercent": s.BatteryLifePercent, "SystemStatusFlag": s.SystemStatusFlag,
            "harness_ac_power_value": True if ac == 1 else (False if ac == 0 else None),
            "classification": cls, "ok": ok}


def memory_status() -> dict:
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return {"total_bytes": m.ullTotalPhys, "available_bytes": m.ullAvailPhys, "commit_limit_bytes": m.ullTotalPageFile,
            "commit_available_bytes": m.ullAvailPageFile, "memory_load_percent": m.dwMemoryLoad}


def cpu_busy_percent(seconds: float) -> float:
    def times():
        idle, kernel, user = (ctypes.c_ulonglong() for _ in range(3))
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
        return idle.value, kernel.value + user.value      # kernel time includes idle time
    i0, t0 = times()
    time.sleep(seconds)
    i1, t1 = times()
    total = t1 - t0
    return round(100.0 * (1 - (i1 - i0) / total), 1) if total else 0.0


def cim(query: str):
    """One PowerShell CIM query as JSON (no host names, user names or paths are requested)."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            f"{query} | ConvertTo-Json -Depth 3 -Compress"], capture_output=True, text=True, timeout=120)
        return json.loads(r.stdout) if r.stdout.strip() else None
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}


VM_PATTERNS = (("Microsoft Corporation", "Virtual Machine", "Hyper-V / Azure VM"), ("", "VMware", "VMware VM"),
               ("", "VirtualBox", "VirtualBox VM"), ("Amazon EC2", "", "AWS EC2"), ("Google", "Google Compute Engine", "GCE"),
               ("QEMU", "", "QEMU/KVM VM"), ("", "KVM", "KVM VM"), ("Xen", "", "Xen VM"), ("", "HVM domU", "Xen HVM VM"),
               ("Parallels", "", "Parallels VM"))


def execution_environment() -> dict:
    cs = cim("Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,SystemType,HypervisorPresent,"
             "NumberOfProcessors,NumberOfLogicalProcessors,TotalPhysicalMemory,PCSystemType")
    bios = cim("Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion")
    kind = "physical (no virtual-machine signature found)"
    man, model = (cs or {}).get("Manufacturer") or "", (cs or {}).get("Model") or ""
    for m_pat, mod_pat, label in VM_PATTERNS:
        if (m_pat and m_pat.lower() in man.lower() and (not mod_pat or mod_pat.lower() in model.lower())) or \
                (not m_pat and mod_pat.lower() in model.lower()):
            kind = f"virtual machine ({label})"
            break
    return {"classification": kind, "computer_system": cs, "bios": bios,
            "note": "HypervisorPresent is also true on physical machines with Hyper-V or VBS enabled"}


def environment_record(p: dict) -> dict:
    pf = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True).stdout.strip()
    drive = p["work"].drive or str(p["work"])[:2]
    from importlib import metadata
    return {
        "recorded_utc": utc(),
        "os": {"platform": platform.platform(), "win32_ver": platform.win32_ver(),
               "cim": cim("Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,"
                          "OSArchitecture")},
        "cpu": {"platform_processor": platform.processor(), "logical_cpus": os.cpu_count(),
                "cim": cim("Get-CimInstance Win32_Processor | Select-Object Name,Manufacturer,NumberOfCores,"
                           "NumberOfLogicalProcessors,MaxClockSpeed,L2CacheSize,L3CacheSize")},
        "memory": memory_status(),
        "page_files": cim("Get-CimInstance Win32_PageFileUsage | Select-Object AllocatedBaseSize,CurrentUsage"),
        "execution_environment": execution_environment(),
        "power_plan": pf,
        "disk": {"workdir_drive": drive, "free_bytes": shutil.disk_usage(p["work"]).free,
                 "physical_disks": cim("Get-PhysicalDisk | Select-Object MediaType,BusType,Size")},
        "python": {"version": sys.version, "implementation": platform.python_implementation(),
                   "bits": ctypes.sizeof(ctypes.c_void_p) * 8, "in_package_venv": in_venv(p)},
        "distributions": sorted(f"{d.metadata['Name']}=={d.version}" for d in metadata.distributions()),
        "git": git("--version"),
        "environment_variables": {k: os.environ.get(k) for k in ("PYTHONHASHSEED", "PYTHONPATH", "PYTHONOPTIMIZE",
                                                                 "PYTHONDONTWRITEBYTECODE", "OMP_NUM_THREADS",
                                                                 "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
        "temp_dir_under_workdir": True,
    }


def in_venv(p: dict) -> bool:
    return Path(sys.prefix).resolve() == p["venv"].resolve()


# ------------------------------------------------------------------------------------------------- checks

def check_revisions(p: dict) -> dict:
    out, ok = {}, True
    autocrlf = git("config", "core.autocrlf", cwd=p["src"]) if p["src"].exists() else None
    for name, exp in EXPECTED["revisions"].items():
        root = p[name]
        if not root.exists():
            out[name] = {"ok": False, "error": f"missing worktree {root.name}"}
            ok = False
            continue
        head, tree = git("rev-parse", "HEAD", cwd=root), git("rev-parse", "HEAD^{tree}", cwd=root)
        porcelain = git("status", "--porcelain", cwd=root)
        r = {"commit": head, "tree": tree, "clean": porcelain == "", "commit_ok": head == exp["commit"],
             "tree_ok": tree == exp["tree"]}
        r["ok"] = r["commit_ok"] and r["tree_ok"] and r["clean"]
        ok &= r["ok"]
        out[name] = r
    out["core.autocrlf"] = autocrlf
    out["autocrlf_ok"] = autocrlf == EXPECTED["git"]["core.autocrlf"]
    out["ok"] = ok and out["autocrlf_ok"]
    return out


CHILD_IMPORT = ("import sys, json; sys.path.insert(0, sys.argv[1]); import reponeedle, reponeedle.engine; "
                "print(json.dumps({'file': reponeedle.__file__, 'version': reponeedle.__version__}))")
PARENT_IMPORT = ("import sys, json; sys.path.insert(0, sys.argv[1]); import stage4_benchmark; "
                 "print(json.dumps(sorted(m for m in sys.modules if m.split('.')[0] == 'reponeedle')))")


def clean_env(p: dict) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHASHSEED", "PYTHONHOME")}
    env.update(TEMP=str(p["tmp"]), TMP=str(p["tmp"]))
    return env


def check_imports(p: dict) -> dict:
    """Each revision's child imports reponeedle from its own worktree (as stage3 run_child does: cwd = worktree,
    worktree first on sys.path, PYTHONPATH removed); the harness parent imports no reponeedle module."""
    out, ok = {}, True
    env = clean_env(p)
    for name in EXPECTED["revisions"]:
        root = p[name]
        r = subprocess.run([str(p["py"]), "-c", CHILD_IMPORT, str(root)], cwd=root, capture_output=True, text=True, env=env)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
            inside = Path(info["file"]).resolve().is_relative_to(root.resolve())
            out[name] = {"imports_own_worktree": inside, "version": info["version"]}
            ok &= inside and info["version"] == EXPECTED["revisions"][name]["package_version"]
        except (ValueError, IndexError, KeyError):
            out[name] = {"error": r.stderr[-800:]}
            ok = False
    bench = p["candidate"] / BENCH_REL
    r = subprocess.run([str(p["py"]), "-c", PARENT_IMPORT, str(bench)], cwd=bench, capture_output=True, text=True, env=env)
    try:
        mods = json.loads(r.stdout.strip().splitlines()[-1])
        out["harness_parent_reponeedle_modules"] = mods
        ok &= mods == []
    except (ValueError, IndexError):
        out["harness_parent_error"] = r.stderr[-800:]
        ok = False
    out["ok"] = ok
    return out


def check_dependencies() -> dict:
    from importlib import metadata
    pins = lock_pins()
    installed = {canon(d.metadata["Name"]): d.version for d in metadata.distributions()}
    mismatched = {n: {"locked": v, "installed": installed.get(n)} for n, v in pins.items() if installed.get(n) != v}
    extra = sorted(n for n in installed if n not in pins and n not in ALLOWED_EXTRA_DISTRIBUTIONS)
    return {"locked": pins, "mismatched": mismatched, "unexpected_distributions": extra,
            "reponeedle_installed": "reponeedle" in installed,
            "ok": not mismatched and not extra and "reponeedle" not in installed}


def preflight(p: dict, results: Path, smoke_files=None) -> dict:
    print("preflight: checking environment ...", flush=True)
    checks, record = {}, {}
    checks["platform"] = {"value": sys.platform, "ok": sys.platform == "win32"}
    exp_py = EXPECTED["python"]["version"]
    checks["python"] = {"value": platform.python_version(), "expected": exp_py,
                        "ok": platform.python_version() == exp_py and platform.python_implementation() == "CPython"
                        and ctypes.sizeof(ctypes.c_void_p) == 8}
    checks["venv"] = {"ok": in_venv(p)}
    checks["dependencies"] = check_dependencies()
    checks["revisions"] = check_revisions(p)
    checks["imports"] = check_imports(p)
    pw = power_status()
    checks["power"] = pw
    mem = memory_status()
    req = EXPECTED["memory_requirements"]
    checks["memory"] = {"total_gib": round(mem["total_bytes"] / GIB, 2), "available_gib": round(mem["available_bytes"] / GIB, 2),
                        "required_total_gib": req["minimum_total_ram_gib"] - 2,  # a "32 GB" machine reports ~31.7 GiB
                        "required_available_gib": req["minimum_available_gib_before_start"]}
    checks["memory"]["ok"] = bool(smoke_files) or (
        checks["memory"]["total_gib"] >= checks["memory"]["required_total_gib"]
        and checks["memory"]["available_gib"] >= checks["memory"]["required_available_gib"])
    if smoke_files:
        checks["memory"]["not_enforced"] = "smoke run"
    free = shutil.disk_usage(p["work"]).free
    checks["disk"] = {"free_gib": round(free / GIB, 1), "required_gib": 10, "ok": free >= 10 * GIB}
    busy = cpu_busy_percent(10.0)
    checks["cpu_idle"] = {"busy_percent_10s": busy, "max_allowed": MAX_PREFLIGHT_CPU_BUSY, "ok": busy <= MAX_PREFLIGHT_CPU_BUSY}
    print("preflight: regenerating the 30,000-file dataset and checking its manifest ...", flush=True)
    ds_out = results / "dataset_verification.json"
    r = subprocess.run([str(p["py"]), str(PACKAGE / "verify_datasets.py"), "--candidate-root", str(p["candidate"]),
                        "--workload", "reduced 30000", "--out", str(ds_out)], capture_output=True, text=True, env=clean_env(p))
    print(r.stdout.strip(), flush=True)
    checks["dataset"] = json.loads(ds_out.read_text(encoding="utf-8")) if ds_out.exists() else {"error": r.stderr[-800:]}
    checks["dataset"]["ok"] = r.returncode == 0
    record = environment_record(p)
    failed = [k for k, v in checks.items() if not v.get("ok")]
    out = {"utc": utc(), "ok": not failed, "failed_checks": failed,
           "mode": {"smoke": bool(smoke_files), "files": smoke_files or FULL_FILES}, "checks": checks,
           "environment": record,
           "package": {"expected_json_sha256": sha256_file(PACKAGE / "expected.json"), "lock_sha256": sha256_file(LOCK),
                       "rn30k_sha256": sha256_file(Path(__file__))}}
    (results / "preflight.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for k, v in checks.items():
        print(f"  {'ok  ' if v.get('ok') else 'FAIL'} {k}", flush=True)
    return out


# ------------------------------------------------------------------------------------------------- commands

def cmd_setup(a) -> int:
    p = paths(a.workdir)
    if platform.python_version() != EXPECTED["python"]["version"]:
        die(f"setup must run with CPython {EXPECTED['python']['version']} (this is {platform.python_version()}); "
            "install it from python.org and use: py -3.12 rn30k.py setup ...")
    if p["src"].exists() or p["trees"].exists() or p["venv"].exists():
        die(f"{p['work']} already contains a setup; use a new, empty --workdir")
    p["work"].mkdir(parents=True, exist_ok=True)
    print(f"setup: repository ({a.source}) ...", flush=True)
    git("init", "-q", str(p["src"]))
    git("config", "core.autocrlf", EXPECTED["git"]["core.autocrlf"], cwd=p["src"])
    if a.source == "bundle":
        git("bundle", "verify", "-q", str(BUNDLE), cwd=p["src"])
        git("fetch", "-q", str(BUNDLE), "refs/remotes/origin/*:refs/remotes/origin/*", cwd=p["src"])
    else:
        git("fetch", "-q", GITHUB, *[r["commit"] for r in EXPECTED["revisions"].values()], cwd=p["src"])
    for name, exp in EXPECTED["revisions"].items():
        print(f"setup: worktree {TREE_DIRS[name]} at {exp['commit']} ...", flush=True)
        git("worktree", "add", "-q", "--detach", str(p[name]), exp["commit"], cwd=p["src"])
    rev = check_revisions(p)
    if not rev["ok"]:
        die(f"revision check failed: {json.dumps(rev, indent=1)}")
    print("setup: virtual environment and locked dependencies ...", flush=True)
    subprocess.run([sys.executable, "-m", "venv", str(p["venv"])], check=True)
    subprocess.run([str(p["py"]), "-m", "pip", "install", "-q", "--disable-pip-version-check", "--require-hashes",
                    "--no-deps", "--only-binary=:all:", "-r", str(LOCK)], check=True)
    pip_check = subprocess.run([str(p["py"]), "-m", "pip", "check"], capture_output=True, text=True)
    p["tmp"].mkdir(exist_ok=True)
    rec = {"utc": utc(), "source": a.source, "bundle_sha256": sha256_file(BUNDLE) if a.source == "bundle" else None,
           "revisions": rev, "python": platform.python_version(), "pip_check": pip_check.stdout.strip(),
           "lock_sha256": sha256_file(LOCK), "git": git("--version")}
    (p["work"] / "setup.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rev, indent=1))
    print(f"\nsetup complete. Next:  py -3.12 \"{Path(__file__)}\" run --workdir \"{p['work']}\"")
    return 0 if pip_check.returncode == 0 else 1


def reexec_in_venv(p: dict) -> None:
    if not in_venv(p):
        if not p["py"].exists():
            die(f"no virtual environment at {p['venv']}; run setup first")
        sys.exit(subprocess.run([str(p["py"]), str(Path(__file__)), *sys.argv[1:]]).returncode)


def cmd_preflight(a) -> int:
    p = paths(a.workdir)
    reexec_in_venv(p)
    results = Path(a.results).resolve() if a.results else p["work"] / "preflight_only"
    results.mkdir(parents=True, exist_ok=True)
    return 0 if preflight(p, results)["ok"] else 1


def cmd_run(a) -> int:
    p = paths(a.workdir)
    reexec_in_venv(p)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    smoke = a.smoke_files
    results = Path(a.results).resolve() if a.results else p["results"] / (stamp + ("_smoke" if smoke else ""))
    if results.exists() and any(results.iterdir()):
        die(f"{results} is not empty; raw results are never overwritten. Use a new --results directory.")
    results.mkdir(parents=True, exist_ok=True)
    p["tmp"].mkdir(exist_ok=True)
    pre = preflight(p, results, smoke)
    if not pre["ok"]:
        die(f"preflight failed: {pre['failed_checks']} (details in {results / 'preflight.json'}). Nothing was run.")
    harness = p["candidate"] / BENCH_REL / "stage4_benchmark.py"
    args = list(EXPECTED["benchmark"]["args"])
    if smoke:
        args[args.index("--files") + 1] = str(smoke)
    cmd = [str(p["py"]), str(harness), "--baseline-root", str(p["baseline"]),
           "--extra-root", f"{EXPECTED['benchmark']['extra_root_name']}={p['intern']}",
           *args, "--out", str(results / (SMOKE_JSON if smoke else OUT_JSON))]
    print(f"\nbenchmark: started {utc()} (expect several hours on a fast machine; do not use the machine meanwhile)",
          flush=True)
    started = utc()
    with open(results / "harness.log", "w", encoding="utf-8") as log:
        log.write(f"started {started}\n")
        proc = subprocess.Popen(cmd, cwd=results, env=clean_env(p), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        rc = proc.wait()
        log.write(f"exit {rc} {utc()}\n")
    post = {"utc": utc(), "harness_started_utc": started, "harness_exit_code": rc, "power": power_status(),
            "memory": memory_status()}
    (results / "postflight.json").write_text(json.dumps(post, indent=1) + "\n", encoding="utf-8")
    val = validate(results, p)
    write_checksums(results)
    print(f"\nresults: {results}\nstatus:  {val['status']}")
    return 0 if rc == 0 and not val["status"].endswith("FAIL") else 1


def write_checksums(results: Path) -> None:
    lines = [f"{sha256_file(f)}  {f.name}" for f in sorted(results.iterdir()) if f.is_file() and f.name != "SHA256SUMS.txt"]
    (results / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------------------------------------------------------------- validation

def validate(results: Path, p=None) -> dict:
    """Independent checks of a finished run. Never modifies the harness output."""
    req, info, excluded = {}, {}, []
    pre = json.loads((results / "preflight.json").read_text(encoding="utf-8")) if (results / "preflight.json").exists() else {}
    smoke = bool(pre.get("mode", {}).get("smoke"))
    n_files = pre.get("mode", {}).get("files", FULL_FILES)
    workload = f"reduced {n_files} files"
    data_path = results / (SMOKE_JSON if smoke else OUT_JSON)
    if not data_path.exists():
        out = {"status": "FAIL", "required": {"result_json_exists": False}}
        (results / "validation.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
        return out
    d = json.loads(data_path.read_text(encoding="utf-8"))
    post = json.loads((results / "postflight.json").read_text(encoding="utf-8")) if (results / "postflight.json").exists() else {}
    names = list(EXPECTED["revisions"])

    revs = d.get("revisions", {})
    req["revisions_match"] = all(revs.get(n, {}).get("commit") == EXPECTED["revisions"][n]["commit"] for n in names) \
        and set(revs) == set(names)
    req["revisions_clean"] = all(revs.get(n, {}).get("tree_clean") is True for n in names)
    req["package_versions"] = all(revs.get(n, {}).get("package_version") == "1.2.0" for n in names)
    env = d.get("environment", {})
    req["python_version"] = env.get("python") == EXPECTED["python"]["version"]
    pins = lock_pins()
    req["dependency_versions"] = all(env.get(m) == pins.get(m) for m in ("numpy", "scipy", "networkx", "pydantic", "pathspec"))
    argv = env.get("argv", [])

    def value(flag):
        return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None
    req["benchmark_flags"] = (all(f in argv for f in ("--verify", "--component-memory", "--require-ac"))
                              and value("--files") == str(n_files) and value("--rounds") == "3"
                              and value("--profile") == "reduced")
    req["preflight_passed"] = bool(pre.get("ok"))

    run = d.get("runs", {}).get(workload)
    req["workload_present"] = run is not None and list(d.get("runs", {})) == [workload]
    run = run or {}
    m = run.get("dataset", {})
    exp_ds = EXPECTED["datasets"].get(workload)
    req["dataset_manifest"] = m.get("file_count") == n_files and (
        True if smoke else exp_ds is not None and m.get("manifest_sha256") == exp_ds["manifest_sha256"])
    info["dataset_manifest_sha256"] = m.get("manifest_sha256")
    rounds = run.get("rounds", [])
    req["three_rounds"] = len(rounds) == 3
    orders = [[k for k in r if k in names] for r in rounds]
    req["revisions_rotated"] = len({o[0] for o in orders if o}) == len(rounds) and all(sorted(o) == sorted(names) for o in orders)

    phases = ("uncached", "cold_cached", "warm_restart")
    complete, digests = True, []
    na_power = (pre.get("checks", {}).get("power", {}).get("classification") == "not_applicable_no_system_battery"
                and post.get("power", {}).get("classification") == "not_applicable_no_system_battery")
    unreliable_power = []
    for i, r in enumerate(rounds, 1):
        for n in names:
            ph = r.get(n, {})
            for phase in phases:
                x = ph.get(phase)
                if not isinstance(x, dict) or "seconds_to_ready_engine" not in x:
                    complete = False
                    continue
                if "waited_for_ac_s" not in x:
                    complete = False                     # --require-ac did not run before this phase
                ac = x.get("ac_power", [])
                if not (all(v is True for v in ac) or (na_power and all(v in (True, None) for v in ac))):
                    unreliable_power.append({"round": i, "variant": n, "phase": phase, "ac_power": ac})
                flags = {f: bool(x.get(f)) for f in ("paging_suspected", "suspended_suspected", "on_battery_suspected")}
                if any(flags.values()):
                    excluded.append({"round": i, "variant": n, "phase": phase, **flags,
                                     "max_heartbeat_gap_s": x.get("max_heartbeat_gap_s"),
                                     "peak_committed_gib": round(x.get("peak_committed_bytes", 0) / GIB, 2),
                                     "available_at_start_gib": round(x.get("available_physical_bytes_at_start", 0) / GIB, 2)})
            vd = ph.get("verification_digests", {})
            digests += [vd.get("warm"), vd.get("uncached")]
    req["all_phases_completed"] = complete and len(rounds) == 3
    req["no_failed_or_aborted"] = not run.get("summary", {}).get("failed_or_aborted")
    req["round_verification_identical"] = run.get("summary", {}).get("verification") == [True, True, True]
    req["one_digest_across_all_rounds"] = len(digests) == 18 and all(digests) and len(set(digests)) == 1
    cm = run.get("component_memory", {})
    req["component_memory_all_revisions"] = all(isinstance(cm.get(n), dict) and cm[n].get("documents") == n_files
                                                and cm[n].get("component_bytes") for n in names)
    req["power_state_reliable"] = not unreliable_power
    cond = run.get("conditions", {})
    req["no_sleep_or_standby_events"] = cond.get("sleep_or_standby_events_during_workload") == []
    req["keep_awake_requested"] = cond.get("keep_awake_requested") is True
    harness_excluded = run.get("summary", {}).get("excluded_phases", [])
    req["exclusions_consistent_with_harness"] = len(harness_excluded) == len(excluded)

    if p is not None and p["candidate"].exists():          # the Markdown must be the harness's rendering of the JSON
        sys.path.insert(0, str(p["candidate"] / BENCH_REL))
        import stage4_benchmark as s4                         # noqa: E402
        md = data_path.with_suffix(".md")
        req["markdown_generated_from_json"] = md.exists() and md.read_text(encoding="utf-8") == s4.markdown(d)

    clean_n = {n: {phase: sum(1 for r in rounds if isinstance(r.get(n, {}).get(phase), dict)
                              and "seconds_to_ready_engine" in r[n][phase]
                              and not any(r[n][phase].get(f) for f in ("paging_suspected", "suspended_suspected",
                                                                       "on_battery_suspected")))
                   for phase in phases} for n in names}
    info.update(clean_rounds_per_revision_and_phase=clean_n, excluded_phases=excluded,
                unreliable_power_phases=unreliable_power, power_not_applicable=na_power,
                preflight_failed_checks=pre.get("failed_checks"), harness_exit_code=post.get("harness_exit_code"),
                ready_engine_s={n: {phase: [r.get(n, {}).get(phase, {}).get("seconds_to_ready_engine") for r in rounds]
                                    for phase in phases} for n in names})
    failed = [k for k, v in req.items() if not v]
    status = ("SMOKE_" if smoke else "") + ("FAIL" if failed else ("PASS_WITH_EXCLUSIONS" if excluded else "PASS"))
    out = {"validated_utc": utc(), "status": status, "mode": {"smoke": smoke, "files": n_files}, "failed_requirements": failed, "required": req, "info": info,
           "result_json_sha256": sha256_file(data_path),
           "note": "Validation of execution conditions and correctness only. Performance claims are not updated by "
                   "this package; the results require independent review before any report, PR or changelog uses them."}
    (results / "validation.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"validation: {status}" + (f" (failed: {failed})" if failed else "") +
          (f"; {len(excluded)} excluded phase(s), raw data kept" if excluded else ""), flush=True)
    return out


def cmd_validate(a) -> int:
    p = paths(a.workdir) if a.workdir else None
    val = validate(Path(a.results).resolve(), p)
    return 0 if not val["status"].endswith("FAIL") else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--workdir", required=True)
    s.add_argument("--source", choices=("bundle", "github"), default="bundle" if BUNDLE.exists() else "github",
                   help="default: the bundle when it is next to this script (the zip), otherwise GitHub (the repository copy)")
    s = sub.add_parser("preflight")
    s.add_argument("--workdir", required=True)
    s.add_argument("--results", default=None)
    s = sub.add_parser("run")
    s.add_argument("--workdir", required=True)
    s.add_argument("--results", default=None)
    s.add_argument("--smoke-files", type=int, default=None,
                   help="pipeline check with N files instead of 30,000 (memory requirement not enforced; output "
                        "stage4_1_benchmark_smoke.json; never a benchmark result)")
    s = sub.add_parser("validate")
    s.add_argument("--results", required=True)
    s.add_argument("--workdir", default=None)
    a = ap.parse_args()
    return {"setup": cmd_setup, "preflight": cmd_preflight, "run": cmd_run, "validate": cmd_validate}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
