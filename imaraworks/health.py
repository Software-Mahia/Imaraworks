"""Health checks for the hosting platform (part of #27)."""
from django.db import connection
from django.http import JsonResponse


def health(request):
    """Liveness: the process is up and can answer. The host uses this to decide whether to restart the app."""
    return JsonResponse({"status": "ok"})


def ready(request):
    """Readiness: the app can reach its database. The host uses this to decide whether to send traffic."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})