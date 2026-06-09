"""Authentication endpoints, plus a development-only email preview."""

from typing import ClassVar

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from user.emails import build_invite
from user.models import User

from .serializers import CurrentUserSerializer, LoginSerializer, LogoutSerializer


class LoginAPIView(APIView):
    """``POST /api/user/login/`` -- exchange email and password for JWTs."""

    permission_classes: ClassVar[list[type]] = [AllowAny]
    authentication_classes: ClassVar[list[type]] = []

    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={200: LoginSerializer},
        tags=["user"],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class CurrentUserAPIView(APIView):
    """``GET /api/user/me/`` -- the authenticated user."""

    permission_classes: ClassVar[list] = [IsAuthenticated]

    @swagger_auto_schema(responses={200: CurrentUserSerializer}, tags=["user"])
    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class LogoutAPIView(APIView):
    """``POST /api/user/logout/`` -- blacklist a refresh token."""

    permission_classes: ClassVar[list] = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=LogoutSerializer,
        responses={200: "Logged out successfully"},
        tags=["user"],
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Logged out successfully"}, status=status.HTTP_200_OK
        )


@staff_member_required
def onboarding_email_preview(request, user_id: int):
    """Render the invite email in the browser instead of reading a console log."""
    if settings.ENVIRONMENT != "development":
        return HttpResponseForbidden("Email preview is only available in development.")

    user = get_object_or_404(User, id=user_id)
    subject, message = build_invite(user)

    return render(
        request,
        "user/onboarding_email_preview.html",
        {
            "user": user,
            "subject": subject,
            "message": message,
            "invite_url": f"{settings.FRONTEND_URL}/login",
            "from_email": settings.DEFAULT_FROM_EMAIL,
            "to_email": user.email,
        },
    )
