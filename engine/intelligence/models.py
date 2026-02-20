from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimestampedModel

SIGNAL_CATEGORIES = [
    ("emerging_needs", "Emerging customer needs"),
    ("pain_points", "Recurring business pain points"),
    ("saas_opportunities", "SaaS or packaged services opportunities"),
    ("competitive_moves", "Competitive movements"),
    ("regulatory_changes", "Regulatory or legal changes"),
    ("pricing_pressure", "Pricing pressure and commoditization"),
    ("acquisition_channels", "New acquisition channels"),
    ("new_tech", "New frameworks, CMS, AI tools"),
    ("automation_devops", "Automation, CI/CD, performance, security"),
    ("ai_applied", "AI applied to dev, SEO, design, PM"),
    ("ai_agents", "AI agents, copilots, RPA"),
    ("legal_risks", "Legal and technical risks"),
]


class Signal(TimestampedModel):
    """Structured intelligence extracted from content."""

    article = models.ForeignKey(
        "articles.Article", on_delete=models.CASCADE, related_name="signals"
    )
    chunk = models.ForeignKey(
        "articles.ContentChunk", on_delete=models.SET_NULL, null=True, blank=True, related_name="signals"
    )
    processing_run = models.ForeignKey(
        "pipeline.ProcessingRun", on_delete=models.SET_NULL, null=True, blank=True, related_name="signals"
    )
    category = models.CharField(max_length=32, choices=SIGNAL_CATEGORIES)
    title = models.CharField(max_length=512)
    description = models.TextField()
    relevance_score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    confidence = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    entities = models.JSONField(default=list, blank=True)
    raw_llm_output = models.JSONField(default=dict)
    is_validated = models.BooleanField(default=False)

    class Meta:
        ordering = ["-relevance_score", "-created_at"]

    def __str__(self):
        return f"{self.category}: {self.title[:50]}"


class SimpleNote(TimestampedModel):
    """Simple text notes without article association for quick insights."""

    title = models.CharField(max_length=512)
    content = models.TextField()
    category = models.CharField(max_length=32, choices=SIGNAL_CATEGORIES, blank=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.title[:50]}"


class PromptTemplate(TimestampedModel):
    """
    User-defined prompt templates, e.g. for signal extraction.
    This lets analysts manage complex instructions without touching code.
    """

    name = models.CharField(max_length=128, unique=True)
    purpose = models.CharField(max_length=128, blank=True)
    body = models.TextField(help_text="Full prompt text sent to the LLM.")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
