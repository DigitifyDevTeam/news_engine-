"""
Shared Django settings for the engine project.
Environment-specific overrides live in development.py and production.py.
"""
from pathlib import Path

import environ
from celery.schedules import crontab

# Build paths: BASE_DIR = engine/ (project root containing manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
    DATABASE_URL=(str, ""),
    REDIS_URL=(str, "redis://localhost:6379/0"),
    OLLAMA_BASE_URL=(str, "http://localhost:11434"),
    LLM_DEFAULT_MODEL=(str, "llama3.1:8b"),
    OLLAMA_TIMEOUT=(int, 600),
    OLLAMA_MAX_RETRIES=(int, 5),
)

# SECURITY: default only for dev; production must set SECRET_KEY via env
SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-in-production")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "django_filters",
    # Local
    "core",
    "sources",
    "articles",
    "pipeline",
    "intelligence",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "engine.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "engine.wsgi.application"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery
CELERY_BROKER_URL = env("REDIS_URL")
CELERY_RESULT_BACKEND = env("REDIS_URL")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "scraping-every-6h": {
        "task": "pipeline.tasks.run_scraping_pipeline",
        "schedule": 3600 * 6,  # every 6 hours (in seconds)
    },
    "extraction-every-6h": {
        "task": "pipeline.tasks.run_extraction_pipeline",
        "schedule": 3600 * 6,
    },
    "weekly-report-monday": {
        "task": "pipeline.tasks.run_report_generation",
        "schedule": crontab(hour=7, minute=0, day_of_week=1),  # Monday 07:00
    },
}

# LLM (Ollama; default model: Llama 3.1 8B local)
# Longer timeout and retries avoid "Read timed out" / connection refused under load
LLM_CONFIG = {
    "provider": "ollama",
    "base_url": env("OLLAMA_BASE_URL"),
    "default_model": env("LLM_DEFAULT_MODEL"),
    "timeout": env("OLLAMA_TIMEOUT"),
    "max_retries": env("OLLAMA_MAX_RETRIES"),
}

# DRF
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
}

# Prompts directory (versioned YAML templates)
PROMPTS_DIR = BASE_DIR / "prompts"

# Logging: structured logs to console and file (file only if LOG_DIR set)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "sources": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "articles": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "intelligence": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "reports": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "pipeline": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
