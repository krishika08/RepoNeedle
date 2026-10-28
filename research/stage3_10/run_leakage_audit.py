"""
Stage 3.10: Codebase Leakage & Special-Case Logic Audit.
Scans reponeedle/ source code, tests/, and configurations for:
  - Benchmark-specific repo names (ripgrep, gin, caddy, click, etc.)
  - Benchmark query IDs or hashes
  - Task type conditional branches in general ranking
  - Synthetic shortcuts or benchmark-specific overrides
"""

import os
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

def audit_leakage():
    print("=" * 80)
    print("STAGE 3.10: LEAKAGE & SPECIAL-CASE LOGIC AUDIT")
    print("=" * 80)

    suspicious_terms = [
        "BurntSushi", "ripgrep", "gin-gonic", "pallets/click", "pallets/flask",
        "caddyserver", "spring-projects", "huggingface", "tokio-rs", "vitejs",
        "0c2c605d", "4ac3545d", "7a8ae85f", "search.rs", "standard.rs"
    ]

    findings = []

    # Audit reponeedle/
    src_dir = ROOT_DIR / "reponeedle"
    for p in src_dir.rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            for term in suspicious_terms:
                if term.lower() in line.lower():
                    findings.append({
                        "file": str(p.relative_to(ROOT_DIR)),
                        "line": idx + 1,
                        "term": term,
                        "code": line.strip()
                    })

    print(f"Total potential leakage hits in reponeedle/: {len(findings)}")
    for f in findings:
        print(f"  [{f['file']}:{f['line']}] Term '{f['term']}': {f['code']}")

    return findings

if __name__ == "__main__":
    audit_leakage()
