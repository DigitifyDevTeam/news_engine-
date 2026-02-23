"""
Translate report body content from English to French using the project LLM.
Used when generating the French PDF so that all content (not just titles) is in French.
"""
import logging
from typing import Any, Dict, List, Optional

from core.exceptions import LLMError

logger = logging.getLogger(__name__)

SYSTEM_TRANSLATE = (
    "You are a professional translator. Translate the given English text into French. "
    "Preserve meaning, tone, and any proper nouns or brand names. "
    "Output only the translation, no explanations or quotes."
)

USER_SUMMARY = "Translate the following executive summary from English to French:\n\n{text}"

USER_LIST = (
    "Translate each of the following lines from English to French. "
    "Keep the same number of lines and the same order. "
    "Output only the translated lines, one per line, with no numbering or bullets:\n\n{lines}"
)


def _translate_text(llm, text: str, section: str) -> str:
    """Translate a single text block. On failure returns original."""
    if not (text and str(text).strip()):
        return text or ""
    try:
        out = llm.generate(
            system_prompt=SYSTEM_TRANSLATE,
            user_prompt=USER_SUMMARY.format(text=text.strip()[:8000]),
        )
        return (out or "").strip() or text
    except LLMError as e:
        logger.warning("Translation failed for %s: %s", section, e)
        return text


def _translate_list(llm, items: List[str], section: str, max_items: int = 15) -> List[str]:
    """Translate a list of strings. On failure returns original list."""
    if not items:
        return items
    items = [str(i).strip() for i in items[:max_items] if i]
    if not items:
        return items
    lines_text = "\n".join(items)
    try:
        out = llm.generate(
            system_prompt=SYSTEM_TRANSLATE,
            user_prompt=USER_LIST.format(lines=lines_text[:12000]),
        )
        if not out:
            return items
        translated = [line.strip() for line in out.strip().split("\n") if line.strip()]
        return translated[: len(items)] if len(translated) >= len(items) else items
    except LLMError as e:
        logger.warning("Translation failed for list %s: %s", section, e)
        return items


def translate_report_data_to_french(
    report_data: Dict[str, Any],
    llm=None,
) -> Dict[str, Any]:
    """
    Return a copy of report_data with all text content translated to French.
    Uses the project LLM; on translation failure for a section, keeps original English.
    """
    from django.conf import settings
    from intelligence.llm_client import LLMClient

    if llm is None:
        llm_config = getattr(settings, "LLM_CONFIG", {})
        llm = LLMClient(
            base_url=llm_config.get("base_url", "http://localhost:11434"),
            default_model=llm_config.get("default_model", "llama3"),
            timeout=llm_config.get("timeout", 360),
            max_retries=llm_config.get("max_retries", 3),
        )

    out = dict(report_data)

    summary = report_data.get("executive_summary", "")
    if isinstance(summary, list):
        summary = " ".join(summary) if summary else ""
    if summary:
        out["executive_summary"] = _translate_text(llm, summary, "executive_summary")

    for key, list_key in [
        ("signals_section", "signals_section"),
        ("opportunities", "opportunities"),
        ("threats", "threats"),
        ("tools_to_test", "tools_to_test"),
        ("project_ideas", "project_ideas"),
    ]:
        items = report_data.get(list_key) or []
        if isinstance(items, list) and items:
            max_n = 10 if list_key == "signals_section" or list_key == "tools_to_test" else 8
            out[list_key] = _translate_list(llm, items, list_key, max_items=max_n)

    return out
