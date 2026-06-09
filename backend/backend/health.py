from django.db import connection
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def healthz(_request):
    """Liveness plus a real database round-trip.

    Container orchestrators need an endpoint that fails when the database is
    unreachable, not one that only proves the Python process is alive.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return Response(
            {"status": "unhealthy", "database": "unreachable", "detail": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response({"status": "ok", "database": "ok"})
