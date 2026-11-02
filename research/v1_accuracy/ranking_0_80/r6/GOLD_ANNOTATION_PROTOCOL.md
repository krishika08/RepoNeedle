# RepoNeedle — Phase R6: Gold Annotation Protocol & Quality Standards

**Milestone**: Mission 0.80+ (Ranking Intelligence Research Programme)  
**Phase**: R6 — Independent Benchmark & Generalization Research  
**Author**: Benchmark Architect & Software Intelligence Engineer  
**Date**: November 2, 2026  
**Status**: Formal Annotation Quality Protocol  

---

## 1. Objective & Annotation Philosophy

In benchmark evaluation, the fidelity of gold annotations directly determines the scientific validity of reported ranking metrics. Over-inclusive annotations artificially inflate recall scores, while under-inclusive annotations penalize rankers for retrieving essential context files.

The Phase R6 annotation protocol establishes **evaluator-only ground truth** anchored in authentic software engineering tasks:
- **No Synthetic Shortcuts**: Tasks are derived directly from closed pull requests, bug fix commits, and real engineering issues.
- **Multi-Role Target Grounding**: Realistic software engineering tasks frequently require retrieving both the modified implementation module and its associated regression test suite or interface manifest.
- **Air-Gapped Isolation**: Annotations are quarantined in evaluation metadata and cannot be queried by the retrieval engine.

---

## 2. Multi-Role Annotation Taxonomy

For each query instance, ground truth files are categorized into primary functional roles:

| Role Category | Definition | Inclusion Standard |
| :--- | :--- | :--- |
| **`PRIMARY_IMPLEMENTATION`** | The core source file containing the logic defect, feature implementation, or requested function. | The file explicitly modified in the patch or containing the symbol requested in the prompt. |
| **`REGRESSION_TEST`** | Test suite verifying the bug fix, reproducing the failure, or asserting feature contract. | Unit or integration test files added or modified in the resolving commit. |
| **`INTERFACE_CONFIG`** | Module manifest, API declaration, or schema configuration. | Build files (`Cargo.toml`, `setup.py`, `package.json`) or API export definitions changed in the task. |
| **`DOWNSTREAM_RIPPLE`** | Secondary modules modified to adapt to API changes or deprecations. | Files modified due to cross-module signature changes. |

---

## 3. Disagreement Adjudication & Ambiguity Management

To eliminate single-annotator bias, candidate task definitions undergo a two-pass review protocol:
1. **Pass 1 (Primary Diff Extraction)**: The primary annotator parses the Git commit patch, recording all modified non-binary source files.
2. **Pass 2 (Independent Relevance Filter)**: A secondary reviewer inspects the issue description and verifies whether each modified file is truly discoverable from the issue statement alone, or represents incidental maintenance (e.g. changelog bump, copyright year update, formatting noise).
3. **Adjudication Rules**:
   - Incidental files (`CHANGELOG.md`, `README.md` reformatting, version strings in unrelated files) are **excluded** from gold sets.
   - Core implementation files are **mandatory**.
   - Test files are marked with role `REGRESSION_TEST` and included if the prompt asks for testing or bug reproduction.
   - Ambiguous auxiliary files are assigned an annotation confidence score ($c < 1.0$) and evaluated in sensitivity analyses.

---

## 4. Evaluator Quarantine Verification

Every query record stores gold targets under the quarantined key `_evaluator_gold`:
```json
"_evaluator_gold": {
  "gold_files": [
    "django/db/models/query.py",
    "tests/queries/test_bitwise_ops.py"
  ],
  "gold_roles": {
    "django/db/models/query.py": "PRIMARY_IMPLEMENTATION",
    "tests/queries/test_bitwise_ops.py": "REGRESSION_TEST"
  },
  "annotation_confidence": 1.0
}
```

At runtime, the ranking engine:
- Never inspects `_evaluator_gold`.
- Has zero visibility into the length of `gold_files`.
- Does not use task classification labels (`task_type`).
- Formulates its ranking strictly through observable candidate metadata and query text.

