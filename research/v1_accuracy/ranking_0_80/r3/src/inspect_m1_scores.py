import gzip
import json

with gzip.open('research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz', 'rt', encoding='utf-8') as f:
    for i in range(5):
        q = json.loads(f.readline())
        print(f"=== Query {i+1}: {q['query_id']} ({q['repo']}) ===")
        print(f"Query text: {repr(q['query_text'][:120])}")
        print(f"Gold files: {q['gold_files']}")
        for c in q['candidates'][:3]:
            print(f"  Rank {c['m1_rank']}: {c['path'][:40]} | Score: {c['m1_score']:.4f} | Scores: {c.get('scores')}")

