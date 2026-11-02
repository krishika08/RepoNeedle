import gzip
import json

with gzip.open('research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz', 'rt', encoding='utf-8') as f:
    queries = [json.loads(line) for line in f]

for ttype in ['trace2code', 'comment2context', 'edit2ripple']:
    matching = [q for q in queries if q.get('track') == ttype or ttype in q.get('track', '')]
    print(f"\n==================== TASK TYPE: {ttype} (Total: {len(matching)}) ====================")
    for q in matching[:2]:
        print(f"\nQuery ID: {q['query_id']} | Repo: {q['repo']}")
        print(f"Query text snippet: {repr(q['query_text'][:180])}")
        print(f"Gold: {q['gold_files']}")
        top3 = [(c['path'], c['m1_rank'], c.get('scores', {}).get('exact_symbol', 0.0), c.get('scores', {}).get('field_bm25', 0.0)) for c in q['candidates'][:3]]
        print(f"Top 3 candidates (path, rank, exact_symbol, field_bm25): {top3}")

