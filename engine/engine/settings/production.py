"""
Production settings: DEBUG off, secrets and DB from env, security headers.
"""
from .base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

SECRET_KEY = env("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY.startswith("django-insecure"):
    raise ValueError("Production requires a non-default SECRET_KEY in environment")

DATABASES = {"default": env.db()}

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
