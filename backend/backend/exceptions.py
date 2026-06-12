import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """Give every API error the same JSON envelope.

    DRF already renders its own exceptions. Anything else would otherwise
    escape as an HTML 500 page, which is useless to an API client, so it is
    logged here and returned as JSON instead.
    """
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, Http404):
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, PermissionDenied):
        return Response(
            {"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN
        )

    logger.error("Unhandled error in %s", context.get("view"), exc_info=exc)
    return Response(
        {"detail": "Internal server error."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
