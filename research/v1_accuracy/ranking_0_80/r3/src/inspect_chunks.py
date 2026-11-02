import json

p = 'external/agent-retrieval-bench/data/corpus/v2_code2test/clap-rs__clap/68b5ff900bae8ee1a0e328c1a2301a7985e4f1c6.chunks.jsonl'
with open(p, 'r', encoding='utf-8') as f:
    count = 0
    for line in f:
        c = json.loads(line)
        if c.get('symbols') or c.get('symbol'):
            print(f"Path: {c['path']}")
            print(f"  Symbol: {c.get('symbol')}")
            print(f"  Symbols: {c.get('symbols')}")
            print(f"  Kind: {c.get('kind')}")
            print(f"  Text preview: {repr(c.get('text', '')[:60])}")
            count += 1
            if count >= 5:
                break

