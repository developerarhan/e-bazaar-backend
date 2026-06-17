from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


def health_check(request):
    """
    Endpoint: GET /health/

    Docker uses this to check if the container is healthy.
    Returns 200 if everything is working.
    Returns 503 if something is broken.
    """
    checks = {}
    healthy = True

    # Check database
    try:
        connection.ensure_connection()
        checks['database'] = 'healthy'
    except Exception as e:
        checks['database'] = f'unhealthy: {str(e)}'
        healthy = False
        logger.error("Database health check failed", extra={"error": str(e)})

    # Check Redis
    try:
        cache.set('health_check_ping', 'pong', timeout=10)
        result = cache.get('health_check_ping')
        if result == 'pong':
            checks['redis'] = 'healthy'
        else:
            checks['redis'] = 'unhealthy: unexpected response'
            healthy = False
    except Exception as e:
        checks['redis'] = f'unhealthy: {str(e)}'
        healthy = False
        logger.error("Redis health check failed", extra={"error": str(e)})

    return JsonResponse(
        {
            'status': 'healthy' if healthy else 'unhealthy',
            'checks': checks,
        },
        status=200 if healthy else 503
    )