"""Shared admin behaviour: a per-row Edit / Delete column.

Jazzmin hides the default object link when ``list_display_links`` is ``None``,
so the changelist needs its own affordance. The column is built per request so
it can respect the viewing user's permissions -- a reviewer with view-only
access is not offered buttons that would answer with a 403.
"""

from typing import ClassVar

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, format_html_join

EDIT_BUTTON = (
    '<a class="row-action row-action--edit" href="{}" title="Edit">'
    '<i class="fas fa-pen"></i><span>Edit</span></a>'
)
DELETE_BUTTON = (
    '<a class="row-action row-action--delete" href="{}" title="Delete" '
    "onclick=\"return confirm('Delete this item?');\">"
    '<i class="fas fa-trash"></i><span>Delete</span></a>'
)


class RowActionsAdmin(admin.ModelAdmin):
    """Adds a ``row_actions`` column to ``list_display``."""

    class Media:
        css: ClassVar[dict] = {"all": ("admin/css/row_actions.css",)}

    def get_list_display(self, request):
        """Swap the ``row_actions`` placeholder for a request-aware renderer."""
        list_display = super().get_list_display(request)
        if "row_actions" not in list_display:
            return list_display

        def row_actions(obj):
            return self._render_row_actions(request, obj)

        row_actions.__name__ = "row_actions"
        row_actions.short_description = "Actions"

        return tuple(
            row_actions if name == "row_actions" else name for name in list_display
        )

    def _render_row_actions(self, request, obj):
        app, model = obj._meta.app_label, obj._meta.model_name
        buttons = []

        if self.has_change_permission(request, obj):
            buttons.append(
                (EDIT_BUTTON, reverse(f"admin:{app}_{model}_change", args=[obj.pk]))
            )
        if self.has_delete_permission(request, obj):
            buttons.append(
                (DELETE_BUTTON, reverse(f"admin:{app}_{model}_delete", args=[obj.pk]))
            )

        if not buttons:
            return "-"

        return format_html(
            '<div class="row-actions-cell">{}</div>',
            format_html_join(
                "", "{}", ((format_html(template, url),) for template, url in buttons)
            ),
        )

    @admin.display(description="Actions")
    def row_actions(self, obj):  # noqa: ARG002
        """Placeholder so that ``list_display`` validation passes.

        ``get_list_display`` swaps this out for a request-bound closure before
        the changelist renders, because permission checks need the request.
        """
        return "-"
