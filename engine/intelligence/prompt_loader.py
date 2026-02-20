"""
Load versioned prompt templates from YAML files.
"""
import logging
from pathlib import Path
from typing import Any, Optional

import yaml
from django.conf import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = getattr(settings, "PROMPTS_DIR", None) or (Path(settings.BASE_DIR) / "prompts")


def load_prompt(name: str, version: Optional[int] = None) -> Optional[dict]:
    """
    Load a prompt template by name and optional version.
    Looks for {name}_v{version}.yaml or {name}_v1.yaml etc.
    """
    if not PROMPTS_DIR or not PROMPTS_DIR.exists():
        logger.warning("Prompts dir not found: %s", PROMPTS_DIR)
        return None

    if version is not None:
        path = PROMPTS_DIR / f"{name}_v{version}.yaml"
    else:
        # Find latest version
        candidates = list(PROMPTS_DIR.glob(f"{name}_v*.yaml"))
        if not candidates:
            return None
        path = max(candidates, key=lambda p: int(p.stem.split("_v")[-1]))

    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def render_prompt(template: str, variables: dict[str, Any]) -> str:
    """Simple {key} substitution for prompt templates."""
    out = template
    for k, v in variables.items():
        out = out.replace("{" + k + "}", str(v))
    return out
