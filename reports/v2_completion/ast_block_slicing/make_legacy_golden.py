"""
Regenerates tests/fixtures/block_slicing/legacy_golden.json from the *baseline* CUD-Pack implementation.

    python reports/v2_completion/ast_block_slicing/make_legacy_golden.py [git-ref]

The packer module is read from git at ``git-ref`` (default: 0c0effe, the main commit this milestone starts from)
and loaded under a private name, so the golden file records what the default ("legacy") focus-span path produced
before AST block slicing existed. tests/test_block_slicing_packing.py compares the current default against it.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from block_slicing_support import GOLDEN, legacy_snapshot  # noqa: E402

BASELINE = "0c0effebef28545f0c5c876f817a34f997781054"


def load_baseline_packer(ref: str):
    source = subprocess.run(["git", "show", f"{ref}:reponeedle/core/packer.py"], cwd=ROOT, check=True,
                            capture_output=True).stdout.decode("utf-8")
    spec = importlib.util.spec_from_loader("_baseline_packer", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, f"{ref}:reponeedle/core/packer.py", "exec"), module.__dict__)
    return module


def main() -> None:
    ref = sys.argv[1] if len(sys.argv) > 1 else BASELINE
    snapshot = legacy_snapshot(load_baseline_packer(ref))
    snapshot = {"baseline": ref, **snapshot}
    GOLDEN.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {GOLDEN.relative_to(ROOT)}: {len(snapshot['focus_spans'])} spans, "
          f"{len(snapshot['skeletons'])} skeletons, {len(snapshot['packs'])} packs from {ref[:7]}")


if __name__ == "__main__":
    main()
