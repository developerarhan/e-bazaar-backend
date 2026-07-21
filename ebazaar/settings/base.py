# ebazaar/settings/base.py

from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()  # loads .env for local development; no-op on Render
               # (Render injects env vars directly, .env file won't exist there)

from ebazaar.logging_config import LOGGING   # noqa: E402 — needs load_dotenv() first if LOGGING reads env vars

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def get_env(key, default=None, required=True):
    """
    Reads an environment variable.
    Crashes immediately if a required variable is missing.
    Better to crash at startup than silently fail mid-request.
    """
    value = os.environ.get(key, default)
    if required and value is None:
        raise ValueError(
            f"Required environment variable '{key}' is not set. "
            f"Check your .env file or deployment config."
        )
    return value


# ─── Security ──────────────────────────────────────────────────────
# No hardcoded fallback — every environment (dev, prod, test)
# MUST set SECRET_KEY explicitly via .env or platform env vars.
SECRET_KEY = get_env("SECRET_KEY")

DEBUG = False  # safe default — environments that need True set it explicitly


# ─── Applications ────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'social_django',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_celery_results',
    'django_celery_beat',

    # Project's apps
    'accounts',
    'store',
    'orders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'ebazaar.middleware.RequestIDMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ebazaar.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

WSGI_APPLICATION = 'ebazaar.wsgi.application'


# ─── Database ──────────────────────────────────────────────────────
# Default fallback is SQLite — only used if DATABASE_URL is unset.
# development.py / production.py override this with environment-
# specific connection details (Docker Postgres / Neon).
import dj_database_url

DATABASE_URL = get_env(
    "DATABASE_URL",
    default="sqlite:///" + str(BASE_DIR / "db.sqlite3"),
    required=False,
)

DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# ─── Auth ──────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},

    # Custom validators
    {'NAME': 'accounts.validators.NumberValidator'},
    {'NAME': 'accounts.validators.UppercaseValidator'},
    {'NAME': 'accounts.validators.LowercaseValidator'},
    {'NAME': 'accounts.validators.SpecialCharacterValidator'},
    {'NAME': 'accounts.validators.NoWhitespaceValidator'},
]


# ─── Internationalization ──────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ─── Static & Media ─────────────────────────────────────────────────
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# ─── DRF ─────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
}


# ─── JWT (default — production.py tightens this) ────────────────────
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ─── Razorpay ──────────────────────────────────────────────────────
# required=False here — local dev/test environments shouldn't be
# forced to have real Razorpay keys just to run `manage.py shell`.
# production.py can tighten this to required=True if you want
# Render to crash loudly on a missing key (recommended).
RAZORPAY_KEY_ID = get_env("RAZORPAY_KEY_ID", required=False)
RAZORPAY_KEY_SECRET = get_env("RAZORPAY_KEY_SECRET", required=False)
RAZORPAY_WEBHOOK_SECRET = get_env("RAZORPAY_WEBHOOK_SECRET", required=False)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ─── Google OAuth ────────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'social_core.backends.google.GoogleOAuth2',
    'django.contrib.auth.backends.ModelBackend',
]

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = get_env('GOOGLE_CLIENT_ID', required=False)
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = get_env('GOOGLE_CLIENT_SECRET', required=False)

SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
]

SOCIAL_AUTH_GOOGLE_OAUTH2_EXTRA_DATA = [
    'name',
    'picture',
    'email',
]

SOCIAL_AUTH_USER_MODEL = 'accounts.User'
SOCIAL_AUTH_LOGIN_REDIRECT_URL = '/'
SOCIAL_AUTH_NEW_USER_REDIRECT_URL = '/'

GOOGLE_REDIRECT_URI = get_env(
    'GOOGLE_REDIRECT_URI',
    default='http://localhost:5173/oauth/google/callback',
    required=False,
)


# ─── Auth Cookies ────────────────────────────────────────────────────
AUTH_COOKIE = "access_token"
AUTH_COOKIE_REFRESH = "refresh_token"
AUTH_COOKIE_MAX_AGE = 60 * 15
AUTH_COOKIE_REFRESH_MAX_AGE = 60 * 60 * 24 * 7
AUTH_COOKIE_SECURE = False              # production.py sets True
AUTH_COOKIE_HTTP_ONLY = True
AUTH_COOKIE_PATH = "/"
AUTH_COOKIE_REFRESH_PATH = "/api/accounts/refresh/"
AUTH_COOKIE_SAMESITE = "Lax"            # production.py sets "None" — see why below


# ─── Celery defaults ─────────────────────────────────────────────────
# These are DEFAULTS — production.py overrides BROKER_URL/RESULT_BACKEND
# with the Render Redis connection string.
CELERY_BROKER_URL = get_env(
    "CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0", required=False
)
CELERY_RESULT_BACKEND = get_env(
    "CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/1", required=False
)

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_RESULT_EXPIRES = 3600
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_ACKS_LATE = True

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'expire-pending-orders': {
        'task': 'orders.expire_pending_orders',
        'schedule': crontab(minute='*/15'),
    },
    'cleanup-expired-tokens': {
        'task': 'accounts.cleanup_expired_tokens',
        'schedule': crontab(hour=2, minute=0),
    },
}


# ─── Cache ─────────────────────────────────────────────────────────
# Defaults to the same Redis used for Celery broker (db 1 is taken
# by CELERY_RESULT_BACKEND above — use db 2 for cache to avoid clashing)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": get_env(
            "CACHE_URL", default="redis://127.0.0.1:6379/2", required=False
        ),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "IGNORE_EXCEPTIONS": True,
        }
    }
}


# ─── Frontend / Misc
FRONTEND_URL = get_env("FRONTEND_URL", default="http://localhost:5173", required=False)

PASSWORD_RESET_TIMEOUT = 3600

# AI
GROQ_API_KEY = get_env("GROQ_API_KEY", required=False)
GROQ_MODEL = "llama3-8b-8192"
REVIEW_SUMMARY_CACHE_TTL = 60 * 60 * 6 
