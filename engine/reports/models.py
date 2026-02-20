from django.db import models
from core.models import TimestampedModel

REPORT_STATUS_DRAFT = "draft"
REPORT_STATUS_GENERATED = "generated"
REPORT_STATUS_REVIEWED = "reviewed"
REPORT_STATUS_PUBLISHED = "published"
REPORT_STATUS_CHOICES = [
    (REPORT_STATUS_DRAFT, "Draft"),
    (REPORT_STATUS_GENERATED, "Generated"),
    (REPORT_STATUS_REVIEWED, "Reviewed"),
    (REPORT_STATUS_PUBLISHED, "Published"),
]


class WeeklyReport(TimestampedModel):
    """Aggregated strategic weekly output."""

    week_start = models.DateField()
    week_end = models.DateField()
    status = models.CharField(
        max_length=20, choices=REPORT_STATUS_CHOICES, default=REPORT_STATUS_DRAFT
    )
    executive_summary = models.TextField(blank=True)
    signals_section = models.JSONField(default=list, blank=True)
    opportunities = models.JSONField(default=list, blank=True)
    threats = models.JSONField(default=list, blank=True)
    tools_to_test = models.JSONField(default=list, blank=True)
    project_ideas = models.JSONField(default=list, blank=True)
    recommended_actions = models.JSONField(default=list, blank=True)
    kpis = models.JSONField(default=dict, blank=True)
    full_markdown = models.TextField(blank=True)
    signal_count = models.PositiveIntegerField(default=0)
    source_count = models.PositiveIntegerField(default=0)
    processing_run = models.ForeignKey(
        "pipeline.ProcessingRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weekly_reports",
    )

    class Meta:
        ordering = ["-week_start"]
        unique_together = [["week_start", "week_end"]]

    def __str__(self):
        return f"Weekly report {self.week_start} – {self.week_end}"

    def generate_pdf(self, lang: str = "en"):
        """Generate PDF report for this weekly report in the given language."""
        from .pdf_generator import ReportPDFGenerator

        report_data = {
            'week_start': self.week_start.strftime('%d/%m/%Y'),
            'week_end': self.week_end.strftime('%d/%m/%Y'),
            'signal_count': self.signal_count,
            'source_count': self.source_count,
            'executive_summary': self.executive_summary,
            'signals_section': self.signals_section,
            'opportunities': self.opportunities,
            'threats': self.threats,
            'tools_to_test': self.tools_to_test,
            'project_ideas': self.project_ideas,
            'kpis': self.kpis,
        }

        generator = ReportPDFGenerator(lang=lang)
        return generator.generate_pdf(report_data)
