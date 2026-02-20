from django.db import models
from core.models import TimestampedModel

SOURCE_TYPE_WEB = "website"
SOURCE_TYPE_RSS = "rss"
SOURCE_TYPE_API = "api"
SOURCE_TYPE_CHOICES = [
    (SOURCE_TYPE_WEB, "Website"),
    (SOURCE_TYPE_RSS, "RSS"),
    (SOURCE_TYPE_API, "API"),
]

SCRAPE_PLAYWRIGHT = "playwright"
SCRAPE_TRAFILATURA = "trafilatura"
SCRAPE_RSS = "rss"
SCRAPE_STRATEGY_CHOICES = [
    (SCRAPE_PLAYWRIGHT, "Playwright"),
    (SCRAPE_TRAFILATURA, "Trafilatura"),
    (SCRAPE_RSS, "RSS"),
]


class Source(TimestampedModel):
    """Monitored website or feed."""

    name = models.CharField(max_length=255)
    url = models.URLField(unique=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES, default=SOURCE_TYPE_WEB)
    scrape_strategy = models.CharField(
        max_length=20, choices=SCRAPE_STRATEGY_CHOICES, default=SCRAPE_TRAFILATURA
    )
    frequency_minutes = models.PositiveIntegerField(
        default=360,
        help_text="Scrape interval in minutes (default 6h = 360)",
    )
    is_active = models.BooleanField(default=True)
    css_selector = models.TextField(blank=True, help_text="Optional CSS selector for article list")
    last_scraped_at = models.DateTimeField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
