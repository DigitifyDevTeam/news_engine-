"""
Report generation: aggregate signals for a week, synthesize via LLM, persist WeeklyReport.

Two-pass strategy for scalability:
  1. Try LLM synthesis with a compact prompt (truncated descriptions).
  2. On LLM failure, build an intelligent fallback that classifies raw signals
     into report sections by category instead of leaving them empty.
"""
import logging
from collections import defaultdict
from datetime import timedelta
from typing import List, Optional

from intelligence.models import Signal
from intelligence.llm_client import LLMClient
from intelligence.prompt_loader import load_prompt, render_prompt
from core.exceptions import LLMError

logger = logging.getLogger(__name__)

# Maps signal categories to report sections for the intelligent fallback.
_CATEGORY_TO_SECTION = {
    "saas_opportunities": "opportunities",
    "emerging_needs": "opportunities",
    "acquisition_channels": "opportunities",
    "new_tech": "tools_to_test",
    "automation_devops": "tools_to_test",
    "ai_applied": "tools_to_test",
    "ai_agents": "tools_to_test",
    "competitive_moves": "threats",
    "regulatory_changes": "threats",
    "pricing_pressure": "threats",
    "legal_risks": "threats",
    "pain_points": "project_ideas",
}

MAX_SIGNALS_IN_PROMPT = 150
MAX_DESC_LENGTH_IN_PROMPT = 300
MAX_PROMPT_CHARS = 40000


def _build_signals_text(signals) -> str:
    """Format signals for the prompt, keeping descriptions compact."""
    lines = []
    for s in signals[:MAX_SIGNALS_IN_PROMPT]:
        desc = (s.description or "")[:MAX_DESC_LENGTH_IN_PROMPT]
        lines.append(f"- [{s.category}] {s.title}: {desc}")
    text = "\n".join(lines)
    return text[:MAX_PROMPT_CHARS]


def _build_intelligent_fallback(signals, signal_count: int, source_count: int) -> dict:
    """
    Build report sections from raw signals by mapping their categories.
    Much better than leaving sections empty when LLM is unavailable.
    """
    buckets: dict[str, list] = defaultdict(list)
    key_signals = []

    for s in signals:
        section = _CATEGORY_TO_SECTION.get(s.category, "key_signals")
        desc = (s.description or "")[:250]
        entry = f"{s.title}: {desc}" + ("..." if len(s.description or "") > 250 else "")

        if section == "key_signals":
            key_signals.append(entry)
        else:
            buckets[section].append(entry)

    top_signals = sorted(signals, key=lambda s: s.relevance_score, reverse=True)
    key_signals_top = [
        f"{s.title}: {(s.description or '')[:250]}"
        for s in top_signals[:15]
    ]

    recommended_actions = []
    if buckets.get("opportunities"):
        recommended_actions.append("Explore the SaaS opportunities and acquisition channels identified this week.")
    if buckets.get("threats"):
        recommended_actions.append("Monitor the competitive moves and regulatory changes flagged this week.")
    if buckets.get("tools_to_test"):
        recommended_actions.append("Evaluate the new technologies and AI tools detected for productivity gains.")
    if buckets.get("project_ideas"):
        recommended_actions.append("Analyze the pain points identified to propose new service offerings.")
    if not recommended_actions:
        recommended_actions.append("Review the detected signals and prioritize next actions.")

    category_counts = defaultdict(int)
    for s in signals:
        category_counts[s.category] += 1

    kpis = {
        "signaux_total": signal_count,
        "sources": source_count,
    }
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1])[:5]:
        kpis[cat] = count

    summary = (
        f"Automated report based on {signal_count} signals from {source_count} sources. "
        f"LLM synthesis unavailable — sections below are built "
        f"directly from signals classified by category."
    )

    return {
        "executive_summary": summary,
        "signals_section": key_signals_top[:15],
        "opportunities": buckets.get("opportunities", [])[:10],
        "threats": buckets.get("threats", [])[:10],
        "tools_to_test": buckets.get("tools_to_test", [])[:10],
        "project_ideas": buckets.get("project_ideas", [])[:10],
        "recommended_actions": recommended_actions,
        "kpis": kpis,
    }


def _build_markdown(report) -> str:
    """Assemble full report as markdown."""
    sections = [
        "# Résumé exécutif\n\n" + (report.executive_summary or ""),
        "\n## Signaux clés\n\n" + "\n".join(f"- {x}" for x in (report.signals_section or [])),
        "\n## Opportunités\n\n" + "\n".join(f"- {x}" for x in (report.opportunities or [])),
        "\n## Menaces et risques\n\n" + "\n".join(f"- {x}" for x in (report.threats or [])),
        "\n## Outils / technologies à tester\n\n" + "\n".join(f"- {x}" for x in (report.tools_to_test or [])),
        "\n## Idées de projets ou d'offres\n\n" + "\n".join(f"- {x}" for x in (report.project_ideas or [])),
        "\n## Actions recommandées\n\n" + "\n".join(f"- {x}" for x in (report.recommended_actions or [])),
        "\n## KPIs et statistiques\n\n" + str(report.kpis or {}),
    ]
    return "\n".join(sections)


class ReportGenerationService:
    """Generates WeeklyReport from signals in a date range."""

    def __init__(self, llm_client: LLMClient = None):
        from django.conf import settings
        llm_config = getattr(settings, "LLM_CONFIG", {})
        self.llm = llm_client or LLMClient(
            base_url=llm_config.get("base_url", "http://localhost:11434"),
            default_model=llm_config.get("default_model", "llama3"),
            timeout=llm_config.get("timeout", 360),
            max_retries=llm_config.get("max_retries", 3),
        )

    def generate_report(
        self,
        week_start,
        week_end=None,
        processing_run=None,
    ):
        """
        Aggregate signals for the week, call LLM for synthesis, create/update WeeklyReport.
        week_start/week_end are date objects. Returns the WeeklyReport instance.
        """
        from reports.models import WeeklyReport, REPORT_STATUS_GENERATED
        from pipeline.models import ProcessingRun as ProcessingRunModel

        if week_end is None:
            week_end = week_start + timedelta(days=6)

        signals = list(Signal.objects.filter(
            created_at__date__gte=week_start,
            created_at__date__lte=week_end,
        ).select_related("article", "article__source").order_by("-relevance_score")[:300])

        if not signals:
            logger.info("No signals in %s–%s, falling back to all signals", week_start, week_end)
            signals = list(Signal.objects.all().select_related(
                "article", "article__source"
            ).order_by("-relevance_score")[:300])

        signal_count = len(signals)
        source_count = len({
            s.article.source_id for s in signals
            if s.article and s.article.source_id
        })

        report, created = WeeklyReport.objects.update_or_create(
            week_start=week_start,
            week_end=week_end,
            defaults={
                "status": REPORT_STATUS_GENERATED,
                "signal_count": signal_count,
                "source_count": source_count,
                "processing_run": processing_run,
            },
        )

        if signal_count == 0:
            report.executive_summary = "Aucun signal cette semaine."
            report.full_markdown = _build_markdown(report)
            report.save()
            return report

        prompt_data = load_prompt("report_synthesis", 1)
        if not prompt_data:
            logger.error("report_synthesis prompt not found")
            return report

        system_prompt = prompt_data.get("system_prompt", "")
        user_template = prompt_data.get("user_prompt_template", "")
        model = prompt_data.get("model")
        signals_text = _build_signals_text(signals)

        try:
            user_prompt = render_prompt(user_template, {
                "week_start": week_start,
                "week_end": week_end,
                "signal_count": signal_count,
                "signals_text": signals_text,
            })
            raw = self.llm.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
            )
        except LLMError as e:
            logger.warning("Report synthesis LLM failed (%s), using intelligent fallback", e)
            raw = None

        if isinstance(raw, dict):
            report.executive_summary = raw.get("executive_summary", "") or ""
            report.signals_section = raw.get("key_signals") if isinstance(raw.get("key_signals"), list) else []
            report.opportunities = raw.get("opportunities") if isinstance(raw.get("opportunities"), list) else []
            report.threats = raw.get("threats") if isinstance(raw.get("threats"), list) else []
            report.tools_to_test = raw.get("tools_to_test") if isinstance(raw.get("tools_to_test"), list) else []
            report.project_ideas = raw.get("project_ideas") if isinstance(raw.get("project_ideas"), list) else []
            report.recommended_actions = raw.get("recommended_actions") if isinstance(raw.get("recommended_actions"), list) else []
            report.kpis = raw.get("kpis") if isinstance(raw.get("kpis"), dict) else {}
        else:
            fallback = _build_intelligent_fallback(signals, signal_count, source_count)
            report.executive_summary = fallback["executive_summary"]
            report.signals_section = fallback["signals_section"]
            report.opportunities = fallback["opportunities"]
            report.threats = fallback["threats"]
            report.tools_to_test = fallback["tools_to_test"]
            report.project_ideas = fallback["project_ideas"]
            report.recommended_actions = fallback["recommended_actions"]
            report.kpis = fallback["kpis"]

        report.full_markdown = _build_markdown(report)
        report.save()
        return report
