import json

p = 'external/agent-retrieval-bench/data/corpus/v2_code2test/clap-rs__clap/68b5ff900bae8ee1a0e328c1a2301a7985e4f1c6.chunks.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    for line in f:
        c = json.loads(line)
        path = c['path']
        if path.endswith('.rs') and c.get('symbol'):
            print(f"Path: {path} | Symbol: {c.get('symbol')} | Kind: {c.get('kind')}")
            break
