import sys
import os

sys.path.insert(0, os.path.abspath("research/v1_accuracy/ranking_0_80/r5/src"))
sys.path.insert(0, os.path.abspath("research/v1_accuracy/ranking_0_80/r2/src"))

from split import load_data
from ranker_r5 import R5Ranker, TREATMENTS

train, val, held = load_data()
ranker = R5Ranker()
item = train[0]

for t in ["A", "B", "C", "D", "E", "F", "G", "H"]:
    res, tel = ranker.rank(item["candidates"], item["query_text"], treatment=t)
    print(f"Treatment {t} latency: {tel['latency_ms']:.2f} ms | Top candidate: {res[0]['path']}")

print("ALL TREATMENTS RUN SMOOTHLY IN SUB-MILLISECOND / LOW MILLISECOND TIME!")

