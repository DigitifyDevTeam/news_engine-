"""
Domain and service-layer exceptions.
"""


class NewsEngineError(Exception):
    """Base exception for the news engine domain."""


class ScrapingError(NewsEngineError):
    """Raised when scraping a source fails."""


class LLMError(NewsEngineError):
    """Raised when an LLM call fails or returns invalid output."""


class ValidationError(NewsEngineError):
    """Raised when business validation fails (e.g. signal schema)."""
