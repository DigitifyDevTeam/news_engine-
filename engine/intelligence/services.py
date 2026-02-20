"""
Signal extraction: send chunks to LLM, validate output, create Signal records.
"""
import logging
from typing import List

from django.utils import timezone

from core.exceptions import LLMError
from intelligence.models import Signal, SIGNAL_CATEGORIES
from intelligence.llm_client import LLMClient
from intelligence.prompt_loader import load_prompt, render_prompt

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {c[0] for c in SIGNAL_CATEGORIES}


def _validate_and_normalize_signal(item: dict) -> dict:
    """Ensure category is valid, scores in [0,1], required keys present."""
    category = (item.get("category") or "").strip().lower().replace(" ", "_")
    if category not in VALID_CATEGORIES:
        category = "new_tech"  # fallback
    relevance = float(item.get("relevance_score", 0.5))
    confidence = float(item.get("confidence", 0.5))
    relevance = max(0.0, min(1.0, relevance))
    confidence = max(0.0, min(1.0, confidence))
    return {
        "category": category,
        "title": (item.get("title") or "Untitled")[:512],
        "description": (item.get("description") or "")[:10000],
        "relevance_score": relevance,
        "confidence": confidence,
        "entities": item.get("entities") if isinstance(item.get("entities"), list) else [],
    }


class SignalExtractionService:
    """Extracts signals from article chunks via LLM and persists Signal records."""

    def __init__(self, llm_client: LLMClient = None):
        from django.conf import settings
        llm_config = getattr(settings, "LLM_CONFIG", {})
        self.llm = llm_client or LLMClient(
            base_url=llm_config.get("base_url", "http://localhost:11434"),
            default_model=llm_config.get("default_model", "llama3"),
            timeout=llm_config.get("timeout", 120),
            max_retries=llm_config.get("max_retries", 2),
        )

    def extract_for_article(self, article, processing_run=None):
        """
        For each chunk of the article, call LLM with signal_extraction prompt,
        parse JSON, validate, create Signal records. Returns list of Signal instances.
        """
        from pipeline.models import ProcessingRun as ProcessingRunModel
        from articles.models import Article as ArticleModel

        if processing_run is None:
            processing_run = ProcessingRunModel.objects.create(
                run_type=ProcessingRunModel.RUN_TYPE_EXTRACT,
                status=ProcessingRunModel.RUN_STATUS_RUNNING,
                started_at=timezone.now(),
            )

        prompt_data = load_prompt("signal_extraction", 1)
        if not prompt_data:
            logger.error("signal_extraction prompt not found")
            processing_run.status = ProcessingRunModel.RUN_STATUS_FAILED
            processing_run.error_log.append("Prompt signal_extraction_v1 not found")
            processing_run.completed_at = timezone.now()
            processing_run.save()
            return []

        system_prompt = prompt_data.get("system_prompt", "")
        user_template = prompt_data.get("user_prompt_template", "")
        model = prompt_data.get("model")

        signals_created: List[Signal] = []
        chunks = list(article.chunks.all().order_by("index"))

        for chunk in chunks:
            try:
                user_prompt = render_prompt(user_template, {
                    "source_name": article.source.name,
                    "chunk_text": chunk.text[:12000],
                })
                raw_output = self.llm.generate_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                )
            except LLMError as e:
                logger.warning("LLM error for article %s chunk %s: %s", article.pk, chunk.index, e)
                processing_run.error_log.append({"chunk": chunk.index, "error": str(e)})
                continue

            if not isinstance(raw_output, list):
                raw_output = [raw_output] if isinstance(raw_output, dict) else []

            for item in raw_output:
                if not isinstance(item, dict):
                    continue
                try:
                    validated = _validate_and_normalize_signal(item)
                    sig = Signal.objects.create(
                        article=article,
                        chunk=chunk,
                        processing_run=processing_run,
                        category=validated["category"],
                        title=validated["title"],
                        description=validated["description"],
                        relevance_score=validated["relevance_score"],
                        confidence=validated["confidence"],
                        entities=validated["entities"],
                        raw_llm_output=item,
                    )
                    signals_created.append(sig)
                except Exception as e:
                    logger.warning("Signal create failed for item %s: %s", item, e)

        article.processing_status = ArticleModel.STATUS_EXTRACTED
        article.save(update_fields=["processing_status", "updated_at"])

        # Only update signal count; run lifecycle is managed by the pipeline orchestrator.
        processing_run.signals_extracted = processing_run.signals.count()
        processing_run.save(update_fields=["signals_extracted", "updated_at"])

        return signals_created
