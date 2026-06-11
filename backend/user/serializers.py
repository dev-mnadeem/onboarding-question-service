from typing import ClassVar

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from user.models import User


class LoginSerializer(serializers.Serializer):
    """Validates credentials and mints a token pair."""

    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, data):
        user = authenticate(
            request=self.context.get("request"),
            username=data["email"],
            password=data["password"],
        )
        if not user:
            msg = "Invalid email or password"
            raise serializers.ValidationError(msg)

        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "role": user.role,
            "user_id": user.id,
        }


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields: ClassVar[list[str]] = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_staff",
        ]


class LogoutSerializer(serializers.Serializer):
    """Blacklists the supplied refresh token."""

    refresh = serializers.CharField()

    def validate(self, attrs):
        self.token = RefreshToken(attrs["refresh"])
        return attrs

    def save(self, **kwargs):  # noqa: ARG002
        self.token.blacklist()
