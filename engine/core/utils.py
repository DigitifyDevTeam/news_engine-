"""
Shared utilities (e.g. text normalization). Domain-specific helpers live in app services.
"""
import re
import unicodedata


def normalize_text(text: str) -> str:
    """Normalize whitespace and strip. Use for cleaning scraped text before storage."""
    if not text or not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
