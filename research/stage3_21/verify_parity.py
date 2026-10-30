import csv
import hashlib
from collections import defaultdict
import numpy as np

def run_parity_audit():
    s14_path = 'research/stage3_14/PER_QUERY_RESULTS.csv'
    s18_path = 'research/stage3_18/CANDIDATE_QUERY_LEVEL_RESULTS.csv'
    s19_path = 'research/stage3_19/PER_QUERY_RESULTS.csv'
    s20_path = 'research/stage3_20/PRODUCTION_PER_QUERY_RESULTS.csv'

    with open(s14_path, encoding='utf-8') as f:
        s14 = {r['query_id']: r for r in csv.DictReader(f)}
    with open(s18_path, encoding='utf-8') as f:
        s18 = {r['query_id']: r for r in csv.DictReader(f)}
    with open(s19_path, encoding='utf-8') as f:
        s19 = {r['query_id']: r for r in csv.DictReader(f)}
    with open(s20_path, encoding='utf-8') as f:
        s20 = {r['query_id']: r for r in csv.DictReader(f)}

    assert len(s14) == 345
    assert len(s18) == 345
    assert len(s19) == 345
    assert len(s20) == 345

    out_records = []
    res_mrr_all = []
    prod_mrr_all = []
    query_hashes = []

    mismatches = 0

    for qid in s20:
        r14 = s14[qid]
        r19 = s19[qid]
        r20 = s20[qid]

        mrr_res_14 = float(r14['ARM-101-BASE_mrr'])
        mrr_res_19 = float(r19['ARM-101-BASE_mrr'])
        mrr_prod = float(r20['ARM-101-PROD_mrr'])

        assert mrr_res_14 == mrr_res_19, f"Discrepancy between Stage 14 and 19 on {qid}"

        delta = abs(mrr_res_19 - mrr_prod)
        if delta > 0.0:
            mismatches += 1

        res_mrr_all.append(mrr_res_19)
        prod_mrr_all.append(mrr_prod)

        # Deterministic per-query fingerprint
        # Based on query ID, repo, task, gold count, and MRR
        q_str = f"{qid}:{r20['repository']}:{r20['task_type']}:{r20['language']}:{mrr_prod:.6f}"
        q_hash = hashlib.sha256(q_str.encode('utf-8')).hexdigest()
        query_hashes.append(q_hash)

        out_records.append({
            'query_id': qid,
            'repository': r20['repository'],
            'base_commit': r20['base_commit'],
            'task_type': r20['task_type'],
            'language': r20['language'],
            'research_mrr': f"{mrr_res_19:.6f}",
            'production_mrr': f"{mrr_prod:.6f}",
            'delta_mrr': f"{delta:.10f}",
            'exact_match': "YES" if delta == 0.0 else "NO",
            'query_ranking_hash': q_hash[:16],
        })

    # Overall deterministic run fingerprint
    run_fingerprint = hashlib.sha256(";".join(query_hashes).encode('utf-8')).hexdigest()

    mean_res = sum(res_mrr_all) / len(res_mrr_all)
    mean_prod = sum(prod_mrr_all) / len(prod_mrr_all)
    aggregate_delta = abs(mean_res - mean_prod)

    # Export ARM101_PER_QUERY_PARITY.csv
    out_csv = 'research/stage3_21/ARM101_PER_QUERY_PARITY.csv'
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(out_records[0].keys()))
        writer.writeheader()
        writer.writerows(out_records)

    print(f"Total Queries Audited:      {len(out_records)}")
    print(f"Exact Matches (Delta == 0): {len(out_records) - mismatches} / {len(out_records)}")
    print(f"Mean Research MRR:          {mean_res:.10f}")
    print(f"Mean Production MRR:        {mean_prod:.10f}")
    print(f"Aggregate Delta:            {aggregate_delta:.10f}")
    print(f"Overall Run Fingerprint:    {run_fingerprint}")

if __name__ == '__main__':
    run_parity_audit()
