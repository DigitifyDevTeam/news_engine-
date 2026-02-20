from django.db import models
from core.models import TimestampedModel

RUN_TYPE_SCRAPE = "scrape"
RUN_TYPE_EXTRACT = "extract"
RUN_TYPE_REPORT = "report"
RUN_TYPE_FULL = "full"
RUN_TYPE_CHOICES = [
    (RUN_TYPE_SCRAPE, "Scrape"),
    (RUN_TYPE_EXTRACT, "Extract"),
    (RUN_TYPE_REPORT, "Report"),
    (RUN_TYPE_FULL, "Full"),
]

RUN_STATUS_PENDING = "pending"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_CHOICES = [
    (RUN_STATUS_PENDING, "Pending"),
    (RUN_STATUS_RUNNING, "Running"),
    (RUN_STATUS_COMPLETED, "Completed"),
    (RUN_STATUS_FAILED, "Failed"),
]


class ProcessingRun(TimestampedModel):
    """Tracks each scraping + analysis execution."""

    RUN_TYPE_SCRAPE = RUN_TYPE_SCRAPE
    RUN_TYPE_EXTRACT = RUN_TYPE_EXTRACT
    RUN_TYPE_REPORT = RUN_TYPE_REPORT
    RUN_TYPE_FULL = RUN_TYPE_FULL
    RUN_STATUS_PENDING = RUN_STATUS_PENDING
    RUN_STATUS_RUNNING = RUN_STATUS_RUNNING
    RUN_STATUS_COMPLETED = RUN_STATUS_COMPLETED
    RUN_STATUS_FAILED = RUN_STATUS_FAILED

    run_type = models.CharField(max_length=20, choices=RUN_TYPE_CHOICES)
    status = models.CharField(
        max_length=20, choices=RUN_STATUS_CHOICES, default=RUN_STATUS_PENDING
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    articles_scraped = models.PositiveIntegerField(default=0)
    signals_extracted = models.PositiveIntegerField(default=0)
    error_log = models.JSONField(default=list, blank=True)
    config = models.JSONField(default=dict, blank=True)
    # Progress for UI: phase name, total steps, current step (e.g. articles processed)
    progress_phase = models.CharField(max_length=32, default="", blank=True)
    progress_total = models.PositiveIntegerField(default=0)
    progress_current = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.run_type} #{self.pk} ({self.status})"
