import json
import glob
import os
from collections import defaultdict

def check_repo_file_types():
    base = "external/agent-retrieval-bench/data/corpus"
    ext_by_repo = defaultdict(lambda: defaultdict(int))
    for chunk_file in glob.glob(f"{base}/*/*/*.chunks.jsonl"):
        repo_name = chunk_file.replace("\\", "/").split("/")[-2].replace("__", "/")
        try:
            with open(chunk_file, "r", encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    path = rec.get("path", "")
                    ext = os.path.splitext(path)[1].lower()
                    if ext:
                        ext_by_repo[repo_name][ext] += 1
        except Exception:
            pass

    print(f"=== File Extensions across {len(ext_by_repo)} Repositories ===")
    for repo, exts in sorted(ext_by_repo.items()):
        top_exts = sorted(exts.items(), key=lambda x: -x[1])[:3]
        top_str = ", ".join([f"{e}:{c}" for e, c in top_exts])
        print(f"  {repo:<30}: {top_str}")

if __name__ == "__main__":
    check_repo_file_types()

