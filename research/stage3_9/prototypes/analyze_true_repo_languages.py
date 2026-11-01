import json
import glob
import os
from collections import defaultdict

CODE_EXTS = {
    ".py": "Python",
    ".go": "Go",
    ".rs": "Rust",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".java": "Java",
}

def analyze_true_repo_languages():
    base = "external/agent-retrieval-bench/data/corpus"
    repos = set()
    for d in glob.glob(f"{base}/*/*"):
        if os.path.isdir(d):
            repos.add(d)

    repo_code_counts = defaultdict(lambda: defaultdict(int))
    for rdir in sorted(repos):
        repo_name = os.path.basename(rdir).replace("__", "/")
        chunk_files = glob.glob(f"{rdir}/*.chunks.jsonl")
        if not chunk_files:
            continue
        # Sample first chunk file to count code extensions
        with open(chunk_files[0], "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                p = rec.get("path", "")
                ext = os.path.splitext(p)[1].lower()
                if ext in CODE_EXTS:
                    lang = CODE_EXTS[ext]
                    repo_code_counts[repo_name][lang] += 1

    print("=== True Programming Language per Repository (Source Code Chunks) ===")
    by_lang = defaultdict(list)
    for repo, counts in sorted(repo_code_counts.items()):
        if not counts:
            print(f"  {repo:<30}: NO CODE CHUNKS IN FIRST SAMPLE")
            continue
        primary_lang = sorted(counts.items(), key=lambda x: -x[1])[0][0]
        by_lang[primary_lang].append(repo)
        print(f"  {repo:<30}: Primary = {primary_lang:<12} (counts: {dict(counts)})")

    print(f"\nTotal Repositories with Code: {len(repo_code_counts)}")
    for lang, rlist in sorted(by_lang.items()):
        print(f"\n{lang} ({len(rlist)} repos):")
        for r in rlist:
            print(f"  - {r}")

if __name__ == "__main__":
    analyze_true_repo_languages()

