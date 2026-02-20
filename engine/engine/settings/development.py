"""
Development settings: DEBUG on, SQLite fallback, console email.
No Redis required: Celery tasks run in-process (eager).
"""
from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# Use SQLite if DATABASE_URL not set (e.g. first run without Docker)
if not env("DATABASE_URL", default=""):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {"default": env.db()}

# Run Celery tasks synchronously in development — no Redis or worker needed.
# .delay() runs the task in the same process and returns immediately.
CELERY_TASK_ALWAYS_EAGER = True
