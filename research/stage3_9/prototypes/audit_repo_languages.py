import json
import os
import glob

def audit_repo_manifest():
    print("=== 1. external/agent-retrieval-bench/data/repo_manifest.jsonl ===")
    manifest_repos = {}
    with open("external/agent-retrieval-bench/data/repo_manifest.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            manifest_repos[r.get("repo")] = r.get("language")
            print(f"  {r.get('repo')}: language = {r.get('language')}")

    print(f"\nTotal in repo_manifest.jsonl: {len(manifest_repos)}")
    py_in_manifest = sum(1 for l in manifest_repos.values() if l == "Python")
    print(f"Python repos in repo_manifest.jsonl: {py_in_manifest}")

    print("\n=== 2. Corpus Manifests Across All Tasks ===")
    corpus_repos = {}
    for mf in glob.glob("external/agent-retrieval-bench/data/corpus/*/corpus_manifest.jsonl"):
        task = mf.replace("\\", "/").split("/")[-2]
        with open(mf, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                repo = rec.get("repo")
                if repo:
                    if repo not in corpus_repos:
                        corpus_repos[repo] = set()
                    corpus_repos[repo].add(task)

    print(f"Total distinct repos across corpus manifests: {len(corpus_repos)}")
    for repo, tasks in sorted(corpus_repos.items()):
        print(f"  {repo:<30} -> tasks: {sorted(list(tasks))}")

    # Check languages from benchmark queries
    print("\n=== 3. Benchmark Queries Language Distribution ===")
    queries_by_repo = {}
    query_files = glob.glob("external/agent-retrieval-bench/data/benchmark/*/*.jsonl")
    for qf in query_files:
        if "manifest" in qf:
            continue
        try:
            with open(qf, "r", encoding="utf-8") as f:
                for line in f:
                    q = json.loads(line)
                    repo = q.get("repo")
                    if repo:
                        queries_by_repo[repo] = queries_by_repo.get(repo, 0) + 1
        except Exception:
            pass

    print(f"Queries count across {len(queries_by_repo)} repos:")
    for repo, cnt in sorted(queries_by_repo.items()):
        lang = manifest_repos.get(repo, "Unknown (not in repo_manifest)")
        print(f"  {repo:<30} (lang: {lang:<12}): {cnt} queries")

if __name__ == "__main__":
    audit_repo_manifest()

