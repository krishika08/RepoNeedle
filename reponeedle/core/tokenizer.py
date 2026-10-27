"""
Code-aware tokenization and token estimation for repository retrieval.
"""

import re
from typing import List, Set

# Regex patterns for splitting snake_case, camelCase, and special code tokens
IDENTIFIER_SPLIT_REGEX = re.compile(r"([a-z0-9])([A-Z])|([A-Z]+)([A-Z][a-z])")
WORD_REGEX = re.compile(r"[A-Za-z0-9_]+")
NON_ALPHANUM_REGEX = re.compile(r"[^A-Za-z0-9_]+")


def split_identifier(name: str) -> List[str]:
    """
    Splits compound identifiers (camelCase, snake_case, kebab-case) into components.
    Example:
        'getHTTPResponse' -> ['get', 'HTTP', 'Response', 'http', 'response']
        'test_api_client_v2' -> ['test', 'api', 'client', 'v2']
    """
    if not name:
        return []
    
    parts: List[str] = []
    # Replace dots, slashes, dashes, colons with underscores
    cleaned = re.sub(r"[\.\/\-\\:]", "_", name)
    sub_tokens = [s for s in cleaned.split("_") if s]

    for token in sub_tokens:
        # CamelCase splitting
        split_camel = IDENTIFIER_SPLIT_REGEX.sub(
            lambda m: f"{m.group(1) or m.group(3)}_{m.group(2) or m.group(4)}",
            token,
        )
        for piece in split_camel.split("_"):
            piece_clean = piece.strip().lower()
            if piece_clean:
                parts.append(piece_clean)
        
        lower_token = token.lower()
        if lower_token not in parts and lower_token:
            parts.append(lower_token)

    return parts


def estimate_tokens(text: str) -> int:
    """
    Estimates token count for source code and documentation.
    Calibrated against standard OpenAI / Qwen / Llama BPE tokenizers for code.
    In code, 1 token is approximately 3.7 to 4.0 characters, but indentation
    and punctuation cause higher token density per character.
    """
    if not text:
        return 0
    
    # Fast heuristic:
    # 1. Whitespace tokens (words)
    # 2. Add extra tokens for common code punctuation and symbols
    words = text.split()
    char_len = len(text)
    # Average ~3.7 chars per code token
    char_estimate = int(char_len / 3.7) + 1
    word_estimate = int(len(words) * 1.3) + 1
    
    # Return smoothed combination bounded by non-zero
    est = max(1, (char_estimate + word_estimate) // 2)
    return est


class CodeTokenizer:
    """
    Tokenizer designed specifically for software repositories and code queries.
    """

    def __init__(self, stop_words: Set[str] = None):
        if stop_words is None:
            # Common programming language keywords that have low search discriminator value
            self.stop_words = {
                "the", "a", "an", "in", "on", "of", "to", "for", "with", "at",
                "by", "from", "and", "or", "is", "it", "this", "that", "be",
                "as", "if", "else", "then", "return", "self", "none", "true", "false",
            }
        else:
            self.stop_words = set(stop_words)

    def tokenize_path(self, path: str) -> List[str]:
        """
        Tokenizes a file path into directory names, base filename, and stem tokens.
        Example:
            'src/flask/app.py' -> ['src', 'flask', 'app', 'app.py']
        """
        if not path:
            return []
        
        parts: List[str] = []
        # Normalized forward slashes
        norm_path = path.replace("\\", "/")
        segments = norm_path.split("/")
        
        for idx, segment in enumerate(segments):
            if not segment:
                continue
            parts.append(segment.lower())
            # Split segment identifiers
            parts.extend(split_identifier(segment))

        return list(dict.fromkeys(parts))

    def tokenize_text(self, text: str, include_raw_identifiers: bool = True) -> List[str]:
        """
        Tokenizes general text, issues, docstrings, or code snippets into tokens.
        """
        if not text:
            return []

        tokens: List[str] = []
        # Extract alphanumeric words/identifiers
        raw_words = WORD_REGEX.findall(text)

        for word in raw_words:
            lower_word = word.lower()
            if include_raw_identifiers and lower_word not in self.stop_words:
                tokens.append(lower_word)
            
            # Sub-token pieces
            pieces = split_identifier(word)
            for p in pieces:
                if p not in self.stop_words and len(p) > 1:
                    tokens.append(p)

        return tokens

