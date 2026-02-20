"""
Pipeline orchestration: full run, scraping run, extraction run, report run.
Ensures all articles from all sources are scraped, chunked, then processed for signals.
"""
import logging

from celery import group, shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

# Timeouts (seconds) when waiting for task groups; scraping many sources can be slow.
SCRAPE_GROUP_TIMEOUT = 3600
CHUNK_GROUP_TIMEOUT = 1800
EXTRACT_GROUP_TIMEOUT = 7200


@shared_task
def run_scraping_pipeline(processing_run_id: int = None):
    """Scrape ALL active sources, wait for completion, then chunk ALL new (pending) articles."""
    from articles.models import Article
    from articles.tasks import chunk_article
    from pipeline.models import ProcessingRun
    from sources.models import Source
    from sources.tasks import scrape_source

    run = None
    if processing_run_id:
        try:
            run = ProcessingRun.objects.get(pk=processing_run_id)
        except ProcessingRun.DoesNotExist:
            pass

    source_ids = list(Source.objects.filter(is_active=True).values_list("id", flat=True))
    if not source_ids:
        return {"scraped": 0, "chunked": 0}

    # Run scrape for every source and WAIT for all to finish so new articles exist in DB.
    scrape_job = group(scrape_source.s(sid) for sid in source_ids)
    scrape_result = scrape_job.apply_async()
    scrape_result.get(timeout=SCRAPE_GROUP_TIMEOUT)

    # Now all scraped articles are in DB with STATUS_PENDING; chunk all of them.
    pending_ids = list(
        Article.objects.filter(processing_status=Article.STATUS_PENDING).values_list("id", flat=True)
    )
    if pending_ids:
        logger.info("Chunking %d pending articles (from all sources)", len(pending_ids))
        chunk_job = group(chunk_article.s(aid) for aid in pending_ids)
        chunk_result = chunk_job.apply_async()
        chunk_result.get(timeout=CHUNK_GROUP_TIMEOUT)

    return {"sources": len(source_ids), "pending_articles": len(pending_ids)}


@shared_task
def run_extraction_pipeline(processing_run_id: int = None):
    """Chunk any remaining pending articles, wait, then extract signals from ALL articles with chunks."""
    from articles.models import Article
    from articles.tasks import chunk_article
    from intelligence.models import Signal
    from intelligence.tasks import extract_signals_for_article
    from pipeline.models import ProcessingRun

    if processing_run_id:
        try:
            run = ProcessingRun.objects.get(pk=processing_run_id)
        except ProcessingRun.DoesNotExist:
            run = None
    else:
        run = ProcessingRun.objects.create(
            run_type=ProcessingRun.RUN_TYPE_EXTRACT,
            status=ProcessingRun.RUN_STATUS_RUNNING,
            started_at=timezone.now(),
        )

    # Chunk any pending articles and WAIT so they become STATUS_CHUNKED before we query.
    pending_ids = list(
        Article.objects.filter(processing_status=Article.STATUS_PENDING).values_list("id", flat=True)
    )
    if pending_ids:
        logger.info("Chunking %d pending articles before extraction", len(pending_ids))
        chunk_job = group(chunk_article.s(aid) for aid in pending_ids)
        chunk_result = chunk_job.apply_async()
        chunk_result.get(timeout=CHUNK_GROUP_TIMEOUT)

    # Get articles that still need extraction (STATUS_CHUNKED).
    chunked_ids = list(
        Article.objects.filter(processing_status=Article.STATUS_CHUNKED).values_list("id", flat=True)
    )

    # If no new articles to extract, reset previously-extracted articles that have chunks
    # so we can re-extract with fresh signals.
    if not chunked_ids:
        extracted_with_chunks = list(
            Article.objects.filter(
                processing_status=Article.STATUS_EXTRACTED,
                chunks__isnull=False,
            ).distinct().values_list("id", flat=True)
        )
        if extracted_with_chunks:
            logger.info("Re-extracting %d already-extracted articles (clearing old signals)", len(extracted_with_chunks))
            Signal.objects.filter(article_id__in=extracted_with_chunks).delete()
            Article.objects.filter(id__in=extracted_with_chunks).update(
                processing_status=Article.STATUS_CHUNKED
            )
            chunked_ids = extracted_with_chunks

    if run:
        run.progress_phase = "extraction"
        run.progress_total = len(chunked_ids)
        run.progress_current = 0
        run.save(update_fields=["progress_phase", "progress_total", "progress_current"])

    if chunked_ids:
        logger.info("Extracting signals from %d articles", len(chunked_ids))
        extract_job = group(
            extract_signals_for_article.s(aid, run.id if run else None) for aid in chunked_ids
        )
        extract_result = extract_job.apply_async()
        extract_result.get(timeout=EXTRACT_GROUP_TIMEOUT)

    return {"processing_run_id": run.id if run else None, "articles": len(chunked_ids)}


@shared_task
def run_report_generation(processing_run_id: int = None):
    """Generate weekly report for last week. Runs synchronously."""
    from reports.tasks import generate_report
    return generate_report(processing_run_id=processing_run_id)


@shared_task(bind=True)
def run_full_pipeline(self, run_id: int = None):
    """
    Pipeline using stored articles only (no scraping).
    Chunks any pending articles, extracts signals from all chunked articles, then generates the weekly PDF report.
    If run_id is provided (e.g. from API), use that run; otherwise create one.
    """
    from pipeline.models import ProcessingRun

    if run_id:
        run = ProcessingRun.objects.get(pk=run_id)
        run.status = ProcessingRun.RUN_STATUS_RUNNING
        run.started_at = timezone.now()
        run.progress_phase = "extraction"
        run.progress_total = 0
        run.progress_current = 0
        run.save(update_fields=["status", "started_at", "progress_phase", "progress_total", "progress_current"])
    else:
        run = ProcessingRun.objects.create(
            run_type=ProcessingRun.RUN_TYPE_FULL,
            status=ProcessingRun.RUN_STATUS_RUNNING,
            started_at=timezone.now(),
            progress_phase="extraction",
        )

    try:
        # 1) Use stored articles: chunk any still pending, then extract signals from all chunked.
        run_extraction_pipeline(run.id)
        run.refresh_from_db()
        # 2) Report phase for UI
        run.progress_phase = "report"
        run.save(update_fields=["progress_phase"])
        # 3) Generate weekly report and PDF.
        result = run_report_generation(run.id)
        run.refresh_from_db()
        run.status = ProcessingRun.RUN_STATUS_COMPLETED
        run.progress_phase = "completed"
        run.progress_current = run.progress_total
    except Exception as e:
        run.status = ProcessingRun.RUN_STATUS_FAILED
        run.error_log.append(str(e))
        logger.exception("Full pipeline failed: %s", e)
    finally:
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at", "error_log", "progress_phase", "progress_current", "config", "updated_at"])

    return {"processing_run_id": run.id, "status": run.status}
