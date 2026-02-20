import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def chunk_article(article_id: int):
    """Chunk an article's raw_text into ContentChunk records."""
    from articles.models import Article
    from articles.services import ChunkingService

    try:
        article = Article.objects.get(pk=article_id)
    except Article.DoesNotExist:
        logger.warning("chunk_article: Article %s not found", article_id)
        return {"article_id": article_id, "chunks": 0, "error": "not_found"}

    service = ChunkingService()
    chunks = service.chunk_article(article)
    return {"article_id": article_id, "chunks": len(chunks)}
