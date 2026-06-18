from .base import *
from urllib.parse import urlsplit, urlunsplit

# ─── Core ──────────────────────────────────────────────────────────
DEBUG = False

ALLOWED_HOSTS = [get_env("ALLOWED_HOST")]

# ─── Logging — extend, don't replace ────────────────────────────────
# LOGGING is already fully built by base.py (imported from
# ebazaar.logging_config). We only ADD mail_admins here —
# never reassign LOGGING entirely, or you lose everything
# base.py configured (JSON formatter, rotating file handler,
# per-app loggers, etc.)
LOGGING['loggers']['orders']['handlers'].append('mail_admins')
LOGGING['loggers']['django.request']['handlers'].append('mail_admins')


# ─── Database — Neon ────────────────────────────────────────────────
import dj_database_url

DATABASE_URL = get_env("DATABASE_URL", required=True)

DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True,   # Neon requires SSL
    )
}


# ─── CORS / CSRF ─────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [get_env("FRONTEND_URL")]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [get_env("FRONTEND_URL")]


# ─── Security headers ────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'


# ─── Cookies — cross-domain (Vercel ↔ Render) ───────────────────────
# Frontend (vercel.app) and backend (onrender.com) are DIFFERENT
# domains. SameSite=Lax (the base.py default) BLOCKS cookies on
# cross-site requests — login would silently fail to persist.
# SameSite=None allows cross-site cookies, but REQUIRES Secure=True
# (cookie only sent over HTTPS) — which Render gives you by default.
AUTH_COOKIE_SECURE = True
AUTH_COOKIE_SAMESITE = "None"


# ─── Email — Brevo SMTP ───────────────────────────────────────────────
# 🚀 Switch backend engine from SMTP to Anymail HTTP API
EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
ANYMAIL = {
    "BREVO_API_KEY": get_env("BREVO_API_KEY"),
}
DEFAULT_FROM_EMAIL = get_env("DEFAULT_FROM_EMAIL", default="noreply@ebazaar.com")


# ─── JWT — tighter in production ─────────────────────────────────────
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ─── Celery / Redis — Render's shared Redis instance ─────────────────
# Render's REDIS_URL typically has NO trailing db number
# (e.g. "rediss://red-xxxxx:6379"). We append db numbers safely
# regardless of whatever shape the URL actually has.

REDIS_URL = get_env("REDIS_URL")


def _redis_url_with_db(base_url, db_number):
    """Returns base_url with its path replaced by /<db_number>."""
    parts = urlsplit(base_url)
    return urlunsplit((
        parts.scheme, parts.netloc, f"/{db_number}",
        parts.query, parts.fragment
    ))


CELERY_BROKER_URL = _redis_url_with_db(REDIS_URL, 0)
CELERY_RESULT_BACKEND = _redis_url_with_db(REDIS_URL, 1)

# Cache uses db 2 — separate from Celery's db 0/1
CACHES['default']['LOCATION'] = _redis_url_with_db(REDIS_URL, 2)

# Render's Redis uses TLS (rediss://) — configure SSL for Celery
if REDIS_URL.startswith('rediss://'):
    CELERY_BROKER_USE_SSL = {'ssl_cert_reqs': 'CERT_NONE'}
    CELERY_REDIS_BACKEND_USE_SSL = {'ssl_cert_reqs': 'CERT_NONE'}
    CACHES['default']['OPTIONS']['CONNECTION_POOL_KWARGS'] = {'ssl_cert_reqs': None}
