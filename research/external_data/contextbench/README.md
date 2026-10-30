# ContextBench Dataset Intake & Integrity Layer

**Location**: `research/external_data/contextbench/`  
**Target Dataset**: `Contextbench/ContextBench` (Official EuniAI Benchmark)  
**Status**: Intake Layer Ready / Automated Acquisition Blocked by Network Isolation  

---

## 1. Source Identity & Authoritative Endpoints

Only the official ContextBench artifacts from EuniAI are authorized for independent evaluation:

- **Hugging Face Hub**: `https://huggingface.co/datasets/Contextbench/ContextBench`
- **Official GitHub Repository**: `https://github.com/EuniAI/ContextBench`
- **Official Benchmark Documentation**: `https://euniai.github.io/ContextBench/`

> [!WARNING]
> **Strict Prohibition on Unofficial Mirrors**:
> The `Schwerli/ContextBench` dataset has a differing row count and schema and is **STRICTLY PROHIBITED** from being substituted for the official benchmark. Any evaluation utilizing unofficial, truncated, or synthetic substitutes will be rejected as invalid.

---

## 2. Dataset Configurations & Expected File Placement

Place downloaded dataset artifacts in this directory (`research/external_data/contextbench/`):

1. **Full Dataset Configuration (`default`)**:
   - **Target File**: `full.parquet` (or `full.jsonl`)
   - **Row Count**: Exactly **1,136 tasks**
   - **Repository Coverage**: Exactly **66 repositories**
   - **Language Coverage**: Exactly **8 programming languages** (Python, Java, JavaScript, TypeScript, Go, C++, C, Rust)

2. **Verified Subset Configuration (`contextbench_verified`)**:
   - **Target File**: `contextbench_verified.parquet` (or `contextbench_verified.jsonl`)
   - **Row Count**: Exactly **500 tasks**

---

## 3. Recommended Out-of-Sandbox Acquisition Script

In an external Python environment with network access enabled, run:

```python
from datasets import load_dataset
from pathlib import Path

out_dir = Path("research/external_data/contextbench")
out_dir.mkdir(parents=True, exist_ok=True)

# 1. Download official full dataset (1,136 tasks)
print("Downloading official Contextbench/ContextBench default (full)...")
full_ds = load_dataset("Contextbench/ContextBench", "default")
full_path = out_dir / "full.parquet"
full_ds["train"].to_parquet(str(full_path))
print(f"Saved full dataset: {full_path} ({len(full_ds['train'])} rows)")

# 2. Download official verified subset (500 tasks)
print("Downloading official Contextbench/ContextBench contextbench_verified...")
ver_ds = load_dataset("Contextbench/ContextBench", "contextbench_verified")
ver_path = out_dir / "contextbench_verified.parquet"
ver_ds["train"].to_parquet(str(ver_path))
print(f"Saved verified dataset: {ver_path} ({len(ver_ds['train'])} rows)")
```

---

## 4. Verification Gate

After copying the files to this directory, run the deterministic validator:

```bash
python research/external_data/contextbench/validate_contextbench.py
```

The script will fail closed if:
- Files are missing (Exit Code 2).
- Checksum does not match recorded SHA-256 (Exit Code 3).
- Schema is malformed or required columns are missing (Exit Code 4).
- Row counts differ from 1,136 or 500 (Exit Code 4).
- Duplicate `instance_id` values or empty gold contexts are detected (Exit Code 4).
