import os
from pathlib import Path

# BASE_DIR should already be defined at the top of your settings file
# Force the creation of the logs directory right here before the LOGGING dict runs!
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console_json': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file_errors': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/errors.log',
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 3,
            'formatter': 'json',
            'level': 'ERROR',
        },
        'mail_admins': {
            'class': 'django.utils.log.AdminEmailHandler',
            'level': 'CRITICAL',
            'filters': ['require_debug_false'],
            'formatter': 'simple',  # ✅ FIXED: Switched from 'verbose' to 'simple'
        },
    },
    'loggers': {
        'orders': {
            'handlers': ['console_json', 'file_errors'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'accounts': {
            'handlers': ['console_json', 'file_errors'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'store': {
            'handlers': ['console_json', 'file_errors'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console_json', 'file_errors', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console_json', 'file_errors'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console_json'],
        'level': 'WARNING',
    },
}