from django.contrib import admin

from backend.admin_mixins import RowActionsAdmin

from .models import Service


@admin.register(Service)
class ServiceAdmin(RowActionsAdmin):
    list_display = (
        "id",
        "title",
        "description",
        "is_active",
        "created_at",
        "row_actions",
    )
    list_filter = ("is_active",)
    search_fields = ("title",)
    list_display_links = None
