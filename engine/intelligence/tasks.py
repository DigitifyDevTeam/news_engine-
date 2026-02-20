import logging
from celery import shared_task
from django.db.models import F

logger = logging.getLogger(__name__)


@shared_task
def extract_signals_for_article(article_id: int, processing_run_id: int = None):
    """Extract signals from an article's chunks via LLM and create Signal records."""
    from articles.models import Article
    from pipeline.models import ProcessingRun
    from intelligence.services import SignalExtractionService

    try:
        article = Article.objects.get(pk=article_id)
    except Article.DoesNotExist:
        logger.warning("extract_signals_for_article: Article %s not found", article_id)
        return {"article_id": article_id, "signals": 0, "error": "not_found"}

    run = None
    if processing_run_id:
        try:
            run = ProcessingRun.objects.get(pk=processing_run_id)
        except ProcessingRun.DoesNotExist:
            pass

    if article.processing_status != Article.STATUS_CHUNKED:
        return {"article_id": article_id, "signals": 0, "error": "article_not_chunked"}

    service = SignalExtractionService()
    signals = service.extract_for_article(article, processing_run=run)
    if run:
        ProcessingRun.objects.filter(pk=run.pk).update(progress_current=F("progress_current") + 1)
    return {"article_id": article_id, "signals": len(signals), "processing_run_id": (run.pk if run else None)}
