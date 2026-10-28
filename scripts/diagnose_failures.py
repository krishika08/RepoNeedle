import json
from collections import defaultdict

with open('reports/full_arb_validation/PER_SAMPLE_RESULTS.jsonl', 'r', encoding='utf-8') as f:
    records = [json.loads(line) for line in f]

task_stats = defaultdict(lambda: {'total': 0, 'rn_mrr': [], 'rm_mrr': [], 'bm_mrr': [], 'rn_r20': [], 'rm_r20': [], 'rn_beats_rm': 0, 'rm_beats_rn': 0, 'rn_beats_bm': 0, 'bm_beats_rn': 0})
repo_stats = defaultdict(lambda: {'total': 0, 'rn_mrr': [], 'rm_mrr': [], 'bm_mrr': [], 'rn_r20': [], 'rm_r20': []})

for r in records:
    t = r['task_type']
    repo = r['repo']
    rn = r['reponeedle']['mrr']
    rm = r['repomap']['mrr']
    bm = r['bm25']['mrr']
    
    task_stats[t]['total'] += 1
    task_stats[t]['rn_mrr'].append(rn)
    task_stats[t]['rm_mrr'].append(rm)
    task_stats[t]['bm_mrr'].append(bm)
    task_stats[t]['rn_r20'].append(r['reponeedle']['recall@20'])
    task_stats[t]['rm_r20'].append(r['repomap']['recall@20'])
    
    if rn > rm:
        task_stats[t]['rn_beats_rm'] += 1
    elif rm > rn:
        task_stats[t]['rm_beats_rn'] += 1
        
    if rn > bm:
        task_stats[t]['rn_beats_bm'] += 1
    elif bm > rn:
        task_stats[t]['bm_beats_rn'] += 1
        
    repo_stats[repo]['total'] += 1
    repo_stats[repo]['rn_mrr'].append(rn)
    repo_stats[repo]['rm_mrr'].append(rm)
    repo_stats[repo]['bm_mrr'].append(bm)
    repo_stats[repo]['rn_r20'].append(r['reponeedle']['recall@20'])
    repo_stats[repo]['rm_r20'].append(r['repomap']['recall@20'])

print("=== TASK LEVEL MRR & HEAD-TO-HEAD ===")
for t, s in task_stats.items():
    tot = s['total']
    rn_m = sum(s['rn_mrr'])/tot
    rm_m = sum(s['rm_mrr'])/tot
    bm_m = sum(s['bm_mrr'])/tot
    rn_r = sum(s['rn_r20'])/tot
    rm_r = sum(s['rm_r20'])/tot
    print(f"{t:16s} N={tot:3d} | RN MRR: {rn_m:.4f} | RM MRR: {rm_m:.4f} | BM MRR: {bm_m:.4f} || RN R@20: {rn_r:.4f} | RM R@20: {rm_r:.4f} || vs RM: +{s['rn_beats_rm']}/-{s['rm_beats_rn']} | vs BM: +{s['rn_beats_bm']}/-{s['bm_beats_rn']}")

print("\n=== REPOSITORY LEVEL ANALYSIS (TOP REPOS) ===")
sorted_repos = sorted(repo_stats.items(), key=lambda x: x[1]['total'], reverse=True)
for repo, s in sorted_repos:
    tot = s['total']
    rn_m = sum(s['rn_mrr'])/tot
    rm_m = sum(s['rm_mrr'])/tot
    bm_m = sum(s['bm_mrr'])/tot
    rn_r = sum(s['rn_r20'])/tot
    rm_r = sum(s['rm_r20'])/tot
    print(f"{repo:25s} N={tot:3d} | RN MRR: {rn_m:.4f} | RM MRR: {rm_m:.4f} | BM MRR: {bm_m:.4f} | RN R@20: {rn_r:.4f} | RM R@20: {rm_r:.4f}")

