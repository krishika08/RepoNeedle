import sys
import os
r2_src = os.path.abspath("research/v1_accuracy/ranking_0_80/r2/src")
sys.path.insert(0, r2_src)
from split import load_data

train, val, held = load_data()
print(f"Loaded: train={len(train)}, val={len(val)}, held={len(held)}")
item0 = train[0]
print(f"Sample query_id: {item0['query_id']}")
print(f"Sample repo: {item0['repo']}")
print(f"Sample task_type: {item0['task_type']}")
print(f"Sample query_text: {item0['query_text'][:100]}")
print(f"Sample gold_files: {item0['gold_files']}")
print(f"Sample candidates count: {len(item0['candidates'])}")
print(f"Sample cand 0 keys: {item0['candidates'][0].keys()}")
print(f"Sample cand 0: {item0['candidates'][0]}")

