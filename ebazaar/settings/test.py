from .base import *

DEBUG = False
SECRET_KEY = 'test-secret-key-not-for-production'

ALLOWED_HOSTS = ['*']

# Database
# Use a separate test database
# pytest-django creates and destroys it automatically
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ebazaar_test',
        'USER': 'ebazaar_user',
        'PASSWORD': 'ebazaar_pass',
        'HOST': 'db',
        'PORT': '5432',
        'TEST': {
            'NAME': 'ebazaar_test',
        }
    }
}

# Cache
# Use dummy cache in tests — no Redis needed
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Celery
# Run tasks synchronously in tests
# No Redis/broker needed
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Email
# Capture emails in memory — don't actually send
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEFAULT_FROM_EMAIL = 'test@ebazaar.com'

# Passwords
# Faster hashing in tests (MD5 instead of bcrypt)
# NEVER use this in production
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Media
MEDIA_ROOT = '/tmp/ebazaar_test_media/'

# Razorpay
RAZORPAY_KEY_ID = 'rzp_test_fake_key'
RAZORPAY_KEY_SECRET = 'fake_secret'
RAZORPAY_WEBHOOK_SECRET = 'fake_webhook_secret'

# Frontend
FRONTEND_URL = 'http://localhost:5173'