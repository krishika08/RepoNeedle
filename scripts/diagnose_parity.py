import json

base_records = {json.loads(l)['sample_id']: json.loads(l) for l in open('reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl', encoding='utf-8') if l.strip()}
ab_records = {json.loads(l)['sample_id']: json.loads(l) for l in open('research/stage2_results/checkpoint_ablations.jsonl', encoding='utf-8') if l.strip()}

count = 0
for sid, ab in ab_records.items():
    b = base_records.get(sid)
    if not b:
        continue
    diff = ab['evaluations']['EXP-001']['mrr'] - b['reponeedle']['mrr']
    if abs(diff) > 0.3:
        print(f"Sample {sid} ({ab['repo']} - {ab['task_type']}):")
        print("  Stage 1 reponeedle MRR:", b['reponeedle']['mrr'])
        print("  Stage 2 EXP-001 MRR:   ", ab['evaluations']['EXP-001']['mrr'])
        print("  Stage 1 top files:", b['reponeedle']['top_files'][:3])
        print("  Stage 2 top files:", ab['evaluations']['EXP-001']['top_files'][:3])
        print("  Gold files:       ", ab['gold_files'])
        count += 1
        if count >= 3:
            break

