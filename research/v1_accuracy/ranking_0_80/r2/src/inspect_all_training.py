"""
Exhaustive inspection of Training queries: JSON keys, seed extraction, intent classification.
"""
import json
import re
from split import load_data
from collections import Counter

def inspect_all_training():
    train_data, val_data, held_out_data = load_data()
    print(f"Auditing all {len(train_data)} training queries...")
    
    key_counter = Counter()
    non_json = 0
    seeds_found = 0
    test_signals = Counter()
    
    for q in train_data:
        text = q["query_text"]
        try:
            d = json.loads(text)
            for k in d.keys():
                key_counter[k] += 1
        except Exception:
            non_json += 1
            
        # Check seed extraction patterns
        # 1. From JSON keys
        # 2. From diff headers: +++ b/..., --- a/...
        seeds = set()
        # regex for json keys
        for pattern in [
            r'"(?:changed_file|given_file|anchor_file|file_path|filename|path)":\s*"([^"]+)"',
            r'"implementation_files":\s*\["([^"]+)"\]'
        ]:
            for m in re.finditer(pattern, text):
                seeds.add(m.group(1))
        # diff headers
        for m in re.finditer(r'\+\+\+ b/(\S+)', text):
            seeds.add(m.group(1))
        for m in re.finditer(r'--- a/(\S+)', text):
            seeds.add(m.group(1))
            
        if seeds:
            seeds_found += 1
            
        # Check test intent signals
        text_lower = text.lower()
        if "test" in text_lower or "tests" in text_lower:
            test_signals["test_term"] += 1
        if "go test" in text_lower or "pytest" in text_lower or "cargo test" in text_lower or "npm test" in text_lower:
            test_signals["test_command"] += 1
        if "pr_body" in text_lower or "pr_title" in text_lower:
            test_signals["pr_metadata"] += 1
        if "diff" in text_lower or "diff_hunk" in text_lower:
            test_signals["diff_metadata"] += 1
        if "failure_excerpt" in text_lower or "traceback" in text_lower or "stack" in text_lower:
            test_signals["stack_trace"] += 1

    print("\nJSON key frequencies in Train:")
    for k, cnt in key_counter.most_common():
        print(f"  {k:<28}: {cnt}/{len(train_data)}")
        
    print(f"\nNon-JSON queries: {non_json}")
    print(f"Queries with extracted seeds: {seeds_found}/{len(train_data)} ({seeds_found/len(train_data)*100:.1f}%)")
    print(f"Test signals distribution in Train:")
    for s, cnt in test_signals.items():
        print(f"  {s:<25}: {cnt}/{len(train_data)}")

if __name__ == "__main__":
    inspect_all_training()

