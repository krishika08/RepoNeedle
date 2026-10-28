with open('reponeedle/engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_str = "return cls(docs=docs, budget_config=budget_config)"
new_str = "return cls(docs=docs, budget_config=budget_config, ablation_config=ablation_config)"

old_def = "def from_documents(\n        cls,\n        docs: List[FileDoc],\n        budget_config: Optional[BudgetConfig] = None,\n    ) -> \"RepoNeedleEngine\":"
new_def = "def from_documents(\n        cls,\n        docs: List[FileDoc],\n        budget_config: Optional[BudgetConfig] = None,\n        ablation_config: Optional[AblationConfig] = None,\n    ) -> \"RepoNeedleEngine\":"

# Normalize CRLF/LF
c_normalized = content.replace('\r\n', '\n')
if old_def in c_normalized:
    c_normalized = c_normalized.replace(old_def, new_def)
    c_normalized = c_normalized.replace(old_str, new_str)
    with open('reponeedle/engine.py', 'w', encoding='utf-8') as f:
        f.write(c_normalized)
    print("Engine successfully patched.")
else:
    print("Target definition not found.")

