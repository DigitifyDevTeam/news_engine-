"""
Chunking service: split article text into LLM-friendly chunks with token counting.
"""
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Default target size for chunks (tokens). LLaMA/Mistral context-friendly.
DEFAULT_CHUNK_SIZE = 1500
DEFAULT_OVERLAP = 150


def get_token_count(text: str, model: str = "cl100k_base") -> int:
    """Return token count for text using tiktoken."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding(model)
        return len(enc.encode(text))
    except Exception as e:
        logger.warning("tiktoken fallback to word estimate: %s", e)
        return len(text.split()) * 2  # rough heuristic


def split_into_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> List[Tuple[str, int]]:
    """
    Split text into overlapping chunks. Returns list of (chunk_text, token_count).
    Uses sentence boundaries where possible to avoid mid-sentence cuts.
    """
    if not text or not text.strip():
        return []

    tokens_approx = get_token_count(text)
    if tokens_approx <= chunk_size:
        return [(text.strip(), tokens_approx)]

    # Split by paragraphs first, then by sentences if needed
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[Tuple[str, int]] = []
    current: List[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = get_token_count(para)
        if current_tokens + para_tokens > chunk_size and current:
            chunk_text = "\n\n".join(current)
            chunks.append((chunk_text, get_token_count(chunk_text)))
            # Overlap: keep last N tokens worth of text
            overlap_target = overlap
            overlap_so_far = 0
            new_current = []
            for p in reversed(current):
                pt = get_token_count(p)
                if overlap_so_far + pt <= overlap_target:
                    new_current.insert(0, p)
                    overlap_so_far += pt
                else:
                    break
            current = new_current
            current_tokens = sum(get_token_count(p) for p in current)
        current.append(para)
        current_tokens += para_tokens

    if current:
        chunk_text = "\n\n".join(current)
        chunks.append((chunk_text, get_token_count(chunk_text)))

    return chunks


class ChunkingService:
    """Creates ContentChunk records for an article from its raw_text."""

    def chunk_article(self, article, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP):
        """
        Replace existing chunks for the article with new chunks from article.raw_text.
        Updates article.processing_status to STATUS_CHUNKED.
        """
        from articles.models import Article, ContentChunk

        if not article.raw_text:
            article.processing_status = Article.STATUS_FAILED
            article.save(update_fields=["processing_status", "updated_at"])
            return []

        chunks_data = split_into_chunks(article.raw_text, chunk_size=chunk_size, overlap=overlap)
        ContentChunk.objects.filter(article=article).delete()

        for index, (text, token_count) in enumerate(chunks_data):
            ContentChunk.objects.create(
                article=article,
                index=index,
                text=text,
                token_count=token_count,
            )

        article.processing_status = Article.STATUS_CHUNKED
        article.save(update_fields=["processing_status", "updated_at"])
        return list(article.chunks.all())
