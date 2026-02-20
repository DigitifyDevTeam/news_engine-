import logging
from celery import shared_task
from core.exceptions import ScrapingError

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(ScrapingError,), retry_backoff=True, max_retries=3)
def scrape_source(self, source_id: int):
    """Scrape a single source and create/update articles. Retries on ScrapingError."""
    from sources.models import Source
    from sources.services import ScrapingService

    try:
        source = Source.objects.get(pk=source_id)
    except Source.DoesNotExist:
        logger.warning("scrape_source: Source %s not found", source_id)
        return {"source_id": source_id, "articles": 0, "error": "source_not_found"}

    if not source.is_active:
        return {"source_id": source_id, "articles": 0, "skipped": "inactive"}

    try:
        service = ScrapingService()
        articles = service.scrape_source(source)
        return {"source_id": source_id, "articles": len(articles)}
    except ScrapingError as e:
        logger.exception("scrape_source failed for %s: %s", source_id, e)
        raise
