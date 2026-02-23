import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

OUTPUT_DIR_NAME = "output"


def _save_report_pdfs_to_output(report):
    """Generate EN and FR PDFs for the report and save them to the output folder."""
    from reports.models import WeeklyReport

    if not isinstance(report, WeeklyReport):
        return []
    output_dir = Path(settings.BASE_DIR) / OUTPUT_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    week_range = f"{report.week_start}_{report.week_end}"
    paths = []
    for lang in ("en", "fr"):
        try:
            pdf_buffer = report.generate_pdf(lang=lang)
            filename = f"report_{week_range}_{timestamp}_{lang}.pdf"
            filepath = output_dir / filename
            filepath.write_bytes(pdf_buffer.getvalue())
            paths.append(str(filepath))
            logger.info("Saved PDF to output: %s (%s)", filename, lang)
        except Exception as e:
            logger.exception("Failed to save %s PDF to output: %s", lang, e)
    return paths


@shared_task
def generate_report(week_start: str = None, week_end: str = None, processing_run_id: int = None):
    """
    Generate weekly report for the given week.
    If no dates given, use the CURRENT week (Monday → Sunday) so signals created today are included.
    week_start/week_end as ISO date strings (YYYY-MM-DD).
    Also saves EN and FR PDFs to the output folder.
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

    # Save both EN and FR PDFs to output folder
    _save_report_pdfs_to_output(report)

    return {"report_id": report.pk, "week_start": str(start), "week_end": str(end)}
