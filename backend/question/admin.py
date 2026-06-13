from django.contrib import admin

from backend.admin_mixins import RowActionsAdmin

from .models import Question


@admin.register(Question)
class QuestionAdmin(RowActionsAdmin):
    list_display = ("id", "question_text", "answer_type", "is_required", "row_actions")
    list_filter = ("answer_type", "is_required")
    search_fields = ("question_text",)
    list_display_links = None
