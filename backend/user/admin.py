from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.html import format_html
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

from backend.admin_mixins import RowActionsAdmin

from .forms import CustomUserChangeForm, CustomUserCreationForm
from .models import User

# Permissions are decided by User.role, and JWT blacklisting is automatic, so
# these three models are noise in the admin. Unregistering them here works
# because `user` is an installed app -- Django only autodiscovers `<app>.admin`.
for model in (Group, BlacklistedToken, OutstandingToken):
    admin.site.unregister(model)


@admin.register(User)
class UserAdmin(BaseUserAdmin, RowActionsAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    fieldsets = (
        ("User Info", {"fields": ("email", "username", "first_name", "last_name")}),
        (
            "Role",
            {
                "fields": ("role", "is_active"),
                "description": (
                    "Saving a user with the Admin role also grants Django "
                    "staff and superuser access."
                ),
            },
        ),
    )
    add_fieldsets = (
        (
            "Create User",
            {
                "classes": ("wide",),
                "fields": ("email", "username", "role", "password1", "password2"),
            },
        ),
    )

    list_display = ("email", "username", "role", "is_active", "row_actions")
    list_display_links = None
    list_filter = ("role", "is_active")
    search_fields = ("email", "username")
    ordering = ("email",)

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue)

        if settings.ENVIRONMENT == "development" and obj.is_onboardable:
            url = reverse("onboarding_email_preview", args=[obj.id])
            messages.info(
                request,
                format_html(
                    'Invite email sent. <a href="{}" target="_blank">Preview it</a>.',
                    url,
                ),
            )

        return response
