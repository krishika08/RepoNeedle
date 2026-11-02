import re
from typing import Dict, List, Set, Tuple

CAMEL_CASE_REGEX = re.compile(r"([a-z0-9])([A-Z])")
SNAKE_CASE_REGEX = re.compile(r"[_\-/\\]")
BACKTICK_REGEX = re.compile(r"`([^`]+)`")
QUALIFIED_REGEX = re.compile(r"\b[A-Za-z0-9_]+(?:::[A-Za-z0-9_]+|\.[A-Za-z0-9_]+)+\b")
DEF_KEYWORDS = {"def", "class", "function", "fn", "struct", "trait", "interface", "type", "enum"}
REF_KEYWORDS = {"call", "caller", "callers", "usages", "references", "invocations", "ripple", "anchor_diff"}
TRACE_KEYWORDS = {"traceback", "stack trace", "fail", "failed", "panic", "error", "exception", "build failed", "test failed"}

def split_identifier(name: str) -> List[str]:
    s1 = CAMEL_CASE_REGEX.sub(r"\1 \2", name)
    parts = SNAKE_CASE_REGEX.split(s1)
    return [p.strip().lower() for p in parts if p.strip()]

def extract_query_symbols(query_text: str) -> Dict[str, any]:
    backticked = BACKTICK_REGEX.findall(query_text)
    qualified = QUALIFIED_REGEX.findall(query_text)
    
    # Extract candidate identifiers (length >= 3)
    raw_idents = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", query_text)
    # Filter common stop words
    stopwords = {"and", "for", "with", "the", "this", "that", "from", "import", "true", "false", "none", "null", "file", "line"}
    idents = [w for w in raw_idents if w.lower() not in stopwords]
    
    # Subwords
    subwords = set()
    for ident in idents + qualified + backticked:
        for sw in split_identifier(ident):
            if len(sw) >= 3 and sw not in stopwords:
                subwords.add(sw)
                
    q_lower = query_text.lower()
    
    # Intent detection
    is_def = any(kw in q_lower for kw in ["where is", "defined in", "definition", "implementing", "declaration"]) or any(re.search(rf"\b{kw}\s+[A-Za-z_]", q_lower) for kw in DEF_KEYWORDS)
    is_ref = any(kw in q_lower for kw in ["caller", "callers", "call site", "usages", "references", "used in", "invoked"]) or "anchor_diff" in query_text
    is_trace = any(kw in q_lower for kw in ["traceback", "stack trace", "build failed", "panic:", "exception:", "failure_excerpt"])
    
    intent = "general"
    if is_trace:
        intent = "implementation_seeking"
    elif is_def:
        intent = "definition_seeking"
    elif is_ref:
        intent = "reference_seeking"
        
    return {
        "backticked": backticked,
        "qualified": qualified,
        "identifiers": idents[:15],
        "subwords": list(subwords)[:20],
        "intent": intent,
    }

if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "r2", "src"))
    from split import load_data
    train_data, val_data, _ = load_data()
    for idx in [0, 5, 10, 20, 35, 50, 75]:
        sample = train_data[idx]
        extracted = extract_query_symbols(sample["query_text"])
        print(f"\nQuery {sample['query_id']} ({sample['task_type']}) | Intent: {extracted['intent']}")
        print(f"  Qualified: {extracted['qualified'][:3]}")
        print(f"  Backticked: {extracted['backticked'][:3]}")
        print(f"  Top idents: {extracted['identifiers'][:5]}")
        print(f"  Gold files: {sample['gold_files']}")
