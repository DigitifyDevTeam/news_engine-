import logging
from datetime import date, timedelta
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def generate_report(week_start: str = None, week_end: str = None, processing_run_id: int = None):
    """
    Generate weekly report for the given week.
    If no dates given, use the CURRENT week (Monday → Sunday) so signals created today are included.
    week_start/week_end as ISO date strings (YYYY-MM-DD).
    """
    from reports.models import WeeklyReport
    from reports.services import ReportGenerationService
    from pipeline.models import ProcessingRun

    today = date.today()
    if week_start:
        start = date.fromisoformat(week_start)
    else:
        start = today - timedelta(days=today.weekday())
    if week_end:
        end = date.fromisoformat(week_end)
    else:
        end = start + timedelta(days=6)

    run = None
    if processing_run_id:
        try:
            run = ProcessingRun.objects.get(pk=processing_run_id)
        except ProcessingRun.DoesNotExist:
            pass

    service = ReportGenerationService()
    report = service.generate_report(week_start=start, week_end=end, processing_run=run)

    if run:
        run.config["report_id"] = report.pk
        run.save(update_fields=["config", "updated_at"])

    return {"report_id": report.pk, "week_start": str(start), "week_end": str(end)}
