import time
import math
import numpy as np
from reponeedle.models import FileDoc, Query
from reponeedle.core.lexical import BM25Index
from reponeedle.core.semantic import SubwordSemanticIndex

# Create 200 docs
docs = [
    FileDoc(
        path=f"pkg/sub_{i % 15}/module_{i}.py",
        content=f"""
class Service_{i}:
    def __init__(self):
        self.val = {i}
    def process_data(self, query):
        from pkg.sub_{(i + 1) % 15}.module_{(i + 1) % 200} import Service_{(i + 1) % 200}
        return self.val * 2
""",
        symbols=[f"Service_{i}", "process_data"],
        imports=[f"pkg.sub_{(i + 1) % 15}.module_{(i + 1) % 200}"],
        line_count=8,
        token_count=45,
    )
    for i in range(200)
]

# Baseline fit
t0 = time.perf_counter()
bm = BM25Index().fit(docs)
t_fresh_bm = (time.perf_counter() - t0) * 1000.0

t0 = time.perf_counter()
sem = SubwordSemanticIndex().fit(docs)
t_fresh_sem = (time.perf_counter() - t0) * 1000.0

print(f"Fresh BM25 fit: {t_fresh_bm:.2f} ms")
print(f"Fresh Semantic fit: {t_fresh_sem:.2f} ms")
print(f"Total Fresh Build: {t_fresh_bm + t_fresh_sem:.2f} ms")

# Cache per-doc representations
bm_cache = {d.path: (bm.doc_term_freqs[idx], bm.doc_lengths[idx]) for idx, d in enumerate(docs)}
sem_cache = {}
for d in docs:
    text = f"{d.path} {' '.join(d.symbols)} {d.content[:8000]}"
    feats = sem._extract_features(text)
    counts = {}
    for f in feats:
        counts[f] = counts.get(f, 0) + 1
    sem_cache[d.path] = counts

# Simulate updating 1 doc
updated_docs = list(docs)
updated_doc = FileDoc(
    path="pkg/sub_0/module_0.py",
    content="class Service_0:\n    def process_data(self, query):\n        return 9999\n",
    symbols=["Service_0", "process_data"],
    imports=[],
    line_count=4,
    token_count=20,
)
updated_docs[0] = updated_doc

# Incremental update using cache
t0 = time.perf_counter()

# 1. Update cache ONLY for modified doc
t_doc = bm.tokenizer.tokenize_path(updated_doc.path)
s_doc = [t for s in updated_doc.symbols for t in bm.tokenizer.tokenize_text(s)]
b_doc = bm.tokenizer.tokenize_text(updated_doc.content)
cnts = {}
for t in t_doc: cnts[t] = cnts.get(t, 0.0) + bm.path_weight
for t in s_doc: cnts[t] = cnts.get(t, 0.0) + bm.symbol_weight
for t in b_doc: cnts[t] = cnts.get(t, 0.0) + bm.body_weight
eff_len = max(1.0, float(len(b_doc) + len(t_doc)))
bm_cache[updated_doc.path] = (cnts, eff_len)

# 2. Reassemble BM25 index from cached term counts
bm_inc = BM25Index()
bm_inc.docs = updated_docs
bm_inc.num_docs = len(updated_docs)
bm_inc.doc_paths = [d.path for d in updated_docs]
bm_inc.doc_frequencies = {}
bm_inc.doc_term_freqs = []
doc_lens = []
for d in updated_docs:
    c, l = bm_cache[d.path]
    bm_inc.doc_term_freqs.append(c)
    doc_lens.append(l)
    for term in c.keys():
        bm_inc.doc_frequencies[term] = bm_inc.doc_frequencies.get(term, 0) + 1

bm_inc.doc_lengths = np.array(doc_lens, dtype=np.float32)
bm_inc.avg_doc_len = float(np.mean(bm_inc.doc_lengths))
inverted = {}
for doc_idx, term_counts in enumerate(bm_inc.doc_term_freqs):
    for term, tf in term_counts.items():
        if term not in inverted:
            inverted[term] = []
        inverted[term].append((doc_idx, tf))
bm_inc.inverted_index = inverted
bm_inc.doc_len_norms = bm_inc.k1 * (1.0 - bm_inc.b + bm_inc.b * (bm_inc.doc_lengths / bm_inc.avg_doc_len))
bm_inc.idf = {
    t: max(0.0, math.log((bm_inc.num_docs - df + 0.5) / (df + 0.5) + 1.0))
    for t, df in bm_inc.doc_frequencies.items()
}

t_inc_bm = (time.perf_counter() - t0) * 1000.0
print(f"Incremental BM25 update: {t_inc_bm:.2f} ms (vs fresh: {t_fresh_bm:.2f} ms)")

# Verify BM25 score identity against fresh fit
bm_fresh = BM25Index().fit(updated_docs)
s_inc = bm_inc.score("process_data Service_0")
s_fr = bm_fresh.score("process_data Service_0")
diff = np.max(np.abs(s_inc - s_fr))
print(f"BM25 Max absolute difference: {diff:.10f}")
assert diff < 1e-6
print("BM25 Index consistency: 100% PERFECT MATCH!")

