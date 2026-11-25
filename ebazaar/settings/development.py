from .base import * # import everything from base first# import everything from base first

# Core
DEBUG = True


ALLOWED_HOSTS = os.getenv("ALLOWED_HOST", "").split(",")

# CORS
CORS_ALLOW_CREDENTIALS = True   # ← allows cookies to be sent cross-origin
                                # Without this, browser blocks all cookies
# In development, allow local frontend
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite default port
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]

# Email
# In development, print emails to terminal instead of sending them
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# # Debug Toolbar 
# INSTALLED_APPS += ['debug_toolbar']
# MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
INTERNAL_IPS = ['127.0.0.1']


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'unknowntruthworld@gmail.com'
EMAIL_HOST_PASSWORD = 'vswnfnoanqptdwfd'
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

RAZORPAY_KEY_ID = "rzp_test_RFkcQRp1dw5x2B"
# RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
RAZORPAY_KEY_SECRET = "h95ptg0ydWUdM0a5lgMyGw8d"
# RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
RAZORPAY_WEBHOOK_SECRET = "myrazorpaywebhooksecret123"

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]
