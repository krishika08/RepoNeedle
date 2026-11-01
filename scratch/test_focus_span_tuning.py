import json
import re
import ast
import sys
from pathlib import Path

STOPWORDS = {
    "the", "a", "an", "in", "on", "of", "to", "for", "with", "at", "by", "from",
    "and", "or", "is", "it", "this", "that", "be", "as", "if", "else", "then",
    "return", "self", "none", "true", "false", "func", "function", "test", "testing",
    "error", "err", "context", "ctx", "code", "file", "data", "value", "type", "struct",
    "package", "import", "class", "def", "async", "public", "private", "string", "int",
}

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[^A-Za-z0-9_\s]", re.UNICODE)
def count_exact_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(text))

def filter_terms(query_text: str) -> set[str]:
    raw_words = re.findall(r"[A-Za-z0-9_]+", query_text.lower())
    return {w for w in raw_words if len(w) >= 4 and w not in STOPWORDS}

def extract_compact_focus_span(content: str, path: str, terms: set[str], cap_lines: int = 65) -> tuple[str, int]:
    lines = content.splitlines()
    if len(lines) <= 45:
        return content, count_exact_tokens(content)

    # 1. Imports
    import_lines = []
    for idx, l in enumerate(lines[:35], 1):
        s = l.strip()
        if s.startswith(("import ", "from ", "package ", "use ")):
            import_lines.append(l)

    # 2. Match lines
    matched = []
    for idx, l in enumerate(lines, 1):
        s_lower = l.lower()
        if any(t in s_lower for t in terms):
            matched.append(idx)

    if not matched:
        # Fallback to outline
        outline = [l for l in lines if l.strip().startswith((
            "class ", "def ", "async def ", "func ", "pub fn ", "fn ", "impl ", "struct ",
            "interface ", "type ", "export ", "public ", "private "
        ))]
        rendered = "\n".join(import_lines + outline[:cap_lines])
        return rendered, count_exact_tokens(rendered)

    # Group matches into clusters
    selected_idx = set()
    for m in matched[:15]:
        for k in range(max(1, m - 2), min(len(lines) + 1, m + 4)):
            selected_idx.add(k)
            if len(selected_idx) >= cap_lines:
                break
        if len(selected_idx) >= cap_lines:
            break

    res = import_lines + ["// ... [context gap] ..."]
    last = 0
    for l_idx in sorted(selected_idx):
        if last > 0 and l_idx > last + 1:
            res.append("    // ... [elided implementation] ...")
        res.append(lines[l_idx - 1])
        last = l_idx

    rendered = "\n".join(res)
    return rendered, count_exact_tokens(rendered)

# Test on Q3
ARB_DIR = Path("external/agent-retrieval-bench")
manifest_path = ARB_DIR / "data" / "corpus" / "v2_selective_mixed" / "corpus_manifest.jsonl"
manifest = {}
for line in open(manifest_path, encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        manifest[(r["repo"], r["base_commit"])] = ARB_DIR / r["chunks_path"]

with open("research/v1_accuracy/m2_structural_ranking/frozen_m1_candidates.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        q = json.loads(line)
        if q["query_id"] == "0265037c6c534b98289fe815":
            break

cpath = manifest[(q["repo"], q["commit"])]
file_chunks = {}
with open(cpath, "r", encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        if c.get("kind") == "file":
            file_chunks[c["path"]] = c.get("text", "")

terms = filter_terms(q["query_text"])
print("Filtered terms for Q3:", terms)

text1 = file_chunks[q["candidates"][0]["path"]]
span1, tok1 = extract_compact_focus_span(text1, q["candidates"][0]["path"], terms)
print(f"Candidate 1 ({q['candidates'][0]['path']}) raw tokens={count_exact_tokens(text1)}, compact span tokens={tok1}")

