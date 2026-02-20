"""
LLM client: provider-agnostic interface. Default implementation uses Ollama HTTP API.
Uses longer timeout and exponential backoff to handle slow/local Ollama instances.
"""
import json
import logging
import time
from typing import Any, Optional

import requests
from core.exceptions import LLMError

logger = logging.getLogger(__name__)

OLLAMA_RETRY_BACKOFF_BASE = 5
OLLAMA_RETRY_BACKOFF_MAX = 30


class LLMClient:
    """Calls LLM (Ollama by default), returns parsed JSON. Validate and post-process externally."""

    def __init__(self, base_url: str, default_model: str, timeout: int = 600, max_retries: int = 5):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> str:
        """Return raw response text from model."""
        model = model or self.default_model
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
        }
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "").strip()
            except requests.exceptions.ConnectionError as e:
                logger.error("Connection to Ollama failed (attempt %s/%s): %s",
                             attempt + 1, self.max_retries + 1, e)
                if attempt == self.max_retries:
                    raise LLMError(f"Ollama connection failed: {e}") from e
            except requests.exceptions.Timeout as e:
                logger.warning("Ollama request attempt %s/%s timed out (timeout=%ss): %s",
                               attempt + 1, self.max_retries + 1, self.timeout, e)
                if attempt == self.max_retries:
                    raise LLMError(f"Ollama request timed out: {e}") from e
            except requests.RequestException as e:
                logger.warning("Ollama request attempt %s/%s failed: %s",
                               attempt + 1, self.max_retries + 1, e)
                if attempt == self.max_retries:
                    raise LLMError(f"Ollama request failed: {e}") from e
            if attempt < self.max_retries:
                backoff = min(OLLAMA_RETRY_BACKOFF_BASE * (2 ** attempt), OLLAMA_RETRY_BACKOFF_MAX)
                logger.info("Retrying in %ss...", backoff)
                time.sleep(backoff)
        raise LLMError("Ollama request failed after retries")

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
    ) -> Any:
        """Call generate and parse response as JSON. Strips markdown code blocks if present."""
        raw = self.generate(system_prompt=system_prompt, user_prompt=user_prompt, model=model)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0].strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid JSON from LLM: {e}") from e
