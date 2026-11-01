import json
import glob
import os
from collections import defaultdict

def fast_check():
    base = "external/agent-retrieval-bench/data/corpus"
    repos = set()
    for d in glob.glob(f"{base}/*/*"):
        if os.path.isdir(d):
            repos.add(d)

    repo_to_ext = defaultdict(lambda: defaultdict(int))
    for rdir in sorted(repos):
        repo_name = os.path.basename(rdir).replace("__", "/")
        chunk_files = glob.glob(f"{rdir}/*.chunks.jsonl")
        if not chunk_files:
            continue
        # Read at most 1 chunk file
        with open(chunk_files[0], "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i > 200:
                    break
                rec = json.loads(line)
                p = rec.get("path", "")
                ext = os.path.splitext(p)[1].lower()
                if ext:
                    repo_to_ext[repo_name][ext] += 1

    print("=== Language Classification of All 25 Repositories ===")
    py_repos = []
    non_py_repos = []

    for repo, exts in sorted(repo_to_ext.items()):
        # Determine dominant language
        top_ext = sorted(exts.items(), key=lambda x: -x[1])[0][0]
        if top_ext == ".py":
            lang = "Python"
            py_repos.append(repo)
        elif top_ext == ".go":
            lang = "Go"
            non_py_repos.append((repo, "Go"))
        elif top_ext == ".rs":
            lang = "Rust"
            non_py_repos.append((repo, "Rust"))
        elif top_ext in (".ts", ".tsx"):
            lang = "TypeScript"
            non_py_repos.append((repo, "TypeScript"))
        elif top_ext in (".js", ".jsx", ".mjs"):
            lang = "JavaScript"
            non_py_repos.append((repo, "JavaScript"))
        elif top_ext == ".java":
            lang = "Java"
            non_py_repos.append((repo, "Java"))
        else:
            lang = f"Other ({top_ext})"
            non_py_repos.append((repo, lang))
        print(f"  {repo:<30}: Dominant = {top_ext} -> Classified as {lang} ({dict(exts)})")

    print(f"\nTotal Repositories: {len(repo_to_ext)}")
    print(f"Python Repositories ({len(py_repos)}): {py_repos}")
    print(f"Non-Python Repositories ({len(non_py_repos)}): {non_py_repos}")

if __name__ == "__main__":
    fast_check()

