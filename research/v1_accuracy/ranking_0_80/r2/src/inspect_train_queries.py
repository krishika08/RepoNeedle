"""
Inspect training queries to design features for SFS, TIP, and SMS.
"""
import json
import re
from split import load_data

def inspect_train():
    train_data, val_data, held_out_data = load_data()
    print(f"Loaded {len(train_data)} training queries.")
    
    # Check sample queries across tracks
    by_track = {}
    for q in train_data:
        tr = q["task_type"]
        if tr not in by_track:
            by_track[tr] = []
        by_track[tr].append(q)
        
    print("\nTrack counts in Train:")
    for tr, qlist in by_track.items():
        print(f"  {tr}: {len(qlist)}")
        
    # Inspect first 2 queries of each track
    for tr, qlist in by_track.items():
        print(f"\n==================== SAMPLES FOR {tr} ====================")
        for q in qlist[:2]:
            print(f"Query ID: {q['query_id']} | Repo: {q['repo']}")
            qtext = q["query_text"]
            print(f"Raw query text (length {len(qtext)}): {qtext[:250]}...")
            
            # Check JSON parseable
            try:
                parsed = json.loads(qtext)
                print("  Successfully parsed as JSON. Keys:", list(parsed.keys()))
                for k, v in parsed.items():
                    if isinstance(v, str):
                        print(f"    {k}: {repr(v[:80])}")
                    elif isinstance(v, (int, float, bool, list)):
                        print(f"    {k}: {repr(v)[:80]}")
            except Exception as e:
                print("  Not JSON. String starts with:", repr(qtext[:100]))
                
            print("  Gold files:", q["gold_files"])

if __name__ == "__main__":
    inspect_train()

