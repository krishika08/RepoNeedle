import json
import glob

def main():
    splits_by_repo = {}
    for mf in glob.glob('external/agent-retrieval-bench/data/corpus/*/corpus_manifest.jsonl'):
        with open(mf, 'r', encoding='utf-8') as f:
            for line in f:
                rec = json.loads(line)
                repo = rec.get('repo')
                split = rec.get('split_id') or rec.get('commit')
                if repo:
                    if repo not in splits_by_repo:
                        splits_by_repo[repo] = set()
                    splits_by_repo[repo].add(split)
    
    print(f"Total distinct repos across corpus manifests: {len(splits_by_repo)}")
    for repo, splits in sorted(splits_by_repo.items()):
        print(f"  {repo}: {len(splits)} splits")

if __name__ == '__main__':
    main()

