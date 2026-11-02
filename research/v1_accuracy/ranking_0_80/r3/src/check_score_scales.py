import gzip
import json
import numpy as np

exact_symbol_vals = []
bm25_vals = []
subword_vals = []

with gzip.open('research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl.gz', 'rt', encoding='utf-8') as f:
    for line in f:
        q = json.loads(line)
        for c in q['candidates']:
            sc = c.get('scores', {})
            if 'exact_symbol' in sc:
                exact_symbol_vals.append(sc['exact_symbol'])
            if 'field_bm25' in sc:
                bm25_vals.append(sc['field_bm25'])
            if 'subwords' in sc:
                subword_vals.append(sc['subwords'])

print(f"Exact symbol: median = {np.median(exact_symbol_vals):.2f}, mean = {np.mean(exact_symbol_vals):.2f}, max = {np.max(exact_symbol_vals):.2f}")
print(f"Field BM25:   median = {np.median(bm25_vals):.2f}, mean = {np.mean(bm25_vals):.2f}, max = {np.max(bm25_vals):.2f}")
print(f"Subwords:     median = {np.median(subword_vals):.2f}, mean = {np.mean(subword_vals):.2f}, max = {np.max(subword_vals):.2f}")

