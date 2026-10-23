"""Health checks for the hosting platform (part of #27)."""
import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)


@require_safe
@never_cache
def health(request):
    """Liveness: the process is up and can answer. The host uses this to decide whether to restart the app."""
    return JsonResponse({"status": "ok"})


@require_safe
@never_cache
def ready(request):
    """Readiness: the app can reach its database. The host uses this to decide whether to send traffic."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        # Say why in the log: a wrong DATABASE_URL or a rotated password would otherwise be invisible.
        logger.exception("Readiness check failed: database unreachable")
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})