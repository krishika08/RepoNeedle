import json

def main():
    with open('external/agent-retrieval-bench/data/repo_manifest.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            print(f"{r.get('repo')}: {r.get('language')}")

if __name__ == '__main__':
    main()

