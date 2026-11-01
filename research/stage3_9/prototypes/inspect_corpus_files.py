import json

with open("external/agent-retrieval-bench/data/corpus/v2_code2test/gin-gonic__gin/28e57f58b184b2305ace192e02496bb89f6fd8cb.chunks.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        obj = json.loads(line)
        if obj.get('path', '').endswith('.go'):
            print(f"Path: {obj.get('path')}, symbol: {obj.get('symbol')}, lines: {obj.get('start_line')}-{obj.get('end_line')}")
            print(f"Snippet:\n{obj.get('text')[:200]}\n---")
            break
