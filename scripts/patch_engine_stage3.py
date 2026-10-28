"""
Patch reponeedle/engine.py for Stage 3 candidates.
"""

path = "reponeedle/engine.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update _fit()
fit_target = """        self.docs = clean_docs
        self.path_to_doc = deduped
        self.lexical_index.fit(clean_docs)"""

fit_replacement = """        self.docs = clean_docs
        self.path_to_doc = deduped

        # Polyglot symbol extraction if enabled and symbols missing
        if self.ablation_config.enable_polyglot_symbols:
            for d in clean_docs:
                if not d.symbols and not d.imports:
                    syms, imps = RepoGraph.extract_polyglot_symbols(d.content, d.path)
                    if syms or imps:
                        d.symbols = syms
                        d.imports = imps

        self.lexical_index.fit(clean_docs)"""

assert fit_target in code, "Could not find fit_target in engine.py"
code = code.replace(fit_target, fit_replacement, 1)

# 2. Update from_directory() symbol extraction
sym_target = """                # AST symbol extraction for Python
                symbols, imports = [], []
                if ext == ".py":
                    symbols, imports = RepoGraph.extract_python_ast(content, rel_path)"""

sym_replacement = """                # AST symbol extraction (Python or Polyglot)
                symbols, imports = [], []
                if ablation_config and ablation_config.enable_polyglot_symbols:
                    symbols, imports = RepoGraph.extract_polyglot_symbols(content, rel_path)
                elif ext == ".py":
                    symbols, imports = RepoGraph.extract_python_ast(content, rel_path)"""

assert sym_target in code, "Could not find sym_target in engine.py"
code = code.replace(sym_target, sym_replacement, 1)

# 3. Update retrieve() for graph diffusion and doc filtering
fuse_target = """        fused_scores = (
            weights["lexical"] * lex_scores +
            weights["semantic"] * sem_scores +
            weights["structural"] * struct_scores +
            weights["workflow_boost"] * workflow_boosts
        )
        fused_scores = np.maximum(0.0, fused_scores)"""

fuse_replacement = """        fused_scores = (
            weights["lexical"] * lex_scores +
            weights["semantic"] * sem_scores +
            weights["structural"] * struct_scores +
            weights["workflow_boost"] * workflow_boosts
        )
        fused_scores = np.maximum(0.0, fused_scores)

        # 4b. Relevance-Aware Graph Diffusion (Candidate D / E)
        if ablation.enable_graph_diffusion and len(self.repo_graph.graph) > 0:
            combined_hits = (lex_scores + sem_scores) if (ablation.enable_lexical and ablation.enable_semantic) else (lex_scores if ablation.enable_lexical else sem_scores)
            if len(combined_hits) > 0 and float(np.max(combined_hits)) > 0:
                top_seed_indices = np.argsort(combined_hits)[::-1][:5]
                diffused_boost = np.zeros(num_docs, dtype=np.float32)
                for s_idx in top_seed_indices:
                    seed_path = self.docs[s_idx].path
                    seed_val = float(combined_hits[s_idx])
                    if seed_val > 0 and seed_path in self.repo_graph.graph:
                        for neighbor in self.repo_graph.graph.neighbors(seed_path):
                            if neighbor in self.repo_graph.path_to_idx:
                                n_idx = self.repo_graph.path_to_idx[neighbor]
                                diffused_boost[n_idx] = max(diffused_boost[n_idx], float(seed_val * 0.25))
                fused_scores = fused_scores + 0.15 * diffused_boost

        # 4c. Documentation Distractor Filter (Candidate C / D / E)
        if ablation.enable_doc_filter:
            for idx, doc in enumerate(self.docs):
                p_lower = doc.path.lower()
                if any(seg in p_lower for seg in ["/doc/", "/docs/", "doc/", "docs/", "documentation/", "guide/", "tutorial/", ".github/"]) or p_lower.endswith((".md", ".rst", ".txt", ".adoc", ".html")):
                    fused_scores[idx] *= ablation.doc_filter_penalty"""

assert fuse_target in code, "Could not find fuse_target in engine.py"
code = code.replace(fuse_target, fuse_replacement, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print("Successfully patched reponeedle/engine.py")
