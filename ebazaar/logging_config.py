LOGGING = {
    'version': 1,

    'disable_existing_loggers': False,

    'formatters': {
        
        # Used in production — outputs clean JSON
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
            # These fields appear in every single log line automatically
        },

        # Short format for simple messages
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

        # Writes errors to a separate file
        'file_errors': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/errors.log',
            'maxBytes': 1024 * 1024 * 5,
            'formatter': 'json',
            'level': 'ERROR',
        },

        # Sends email to admins for critical errors in production
        'mail_admins': {
            'class': 'django.utils.log.AdminEmailHandler',
            'level': 'CRITICAL',
            'filters': ['require_debug_false'],
            'formatter': 'verbose',
        },
    },
    'loggers': {

        # Your orders app
        'orders': {
            'handlers': ['console_json', 'file_errors'],
            'level': 'DEBUG',
            'propagate': False,
            # propagate=False means don't pass to root logger
            # prevents duplicate log entries
        },

        # Your accounts app
        'accounts': {
            'handlers': ['console_json', 'file_errors'],
            'level': 'DEBUG',
            'propagate': False,
        },

        # Your store app
        'store': {
            'handlers': ['console_json', 'file_errors'],
            'level': 'DEBUG',
            'propagate': False,
        },

        # Django's own request logging
        # This logs every HTTP request Django handles
        'django.request': {
            'handlers': ['console_json', 'file_errors', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },

        # Django's security logging (suspicious requests, etc.)
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