from typing import ClassVar

from django.contrib import admin
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html

from answer.answer_types import handler_for
from backend.admin_mixins import RowActionsAdmin

from .models import Answer, Document


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    readonly_fields = ("uploaded_at", "reviewed_at", "reviewed_by", "file_link")
    fields = (
        "uploaded_file",
        "file_link",
        "is_approved",
        "rejection_reason",
        "uploaded_at",
        "reviewed_at",
    )

    @admin.display(description="Open")
    def file_link(self, obj):
        if not obj.uploaded_file:
            return "-"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            obj.uploaded_file.url,
            obj.uploaded_file.name,
        )


@admin.register(Answer)
class AnswerAdmin(RowActionsAdmin):
    inlines: ClassVar[list] = [DocumentInline]

    list_display = (
        "id",
        "question",
        "user",
        "onboarding",
        "value",
        "document_count",
        "created_at",
        "row_actions",
    )
    fields = (
        "question",
        "user",
        "onboarding",
        "answer_text",
        "answer_number",
        "answer_date",
        "answer_boolean",
        "created_at",
        "updated_at",
    )
    search_fields = ("user__email", "question__question_text")
    list_filter = ("question__answer_type", "onboarding__status")
    readonly_fields = ("created_at", "updated_at")
    list_display_links = None

    def get_queryset(self, request):
        # Without these the changelist issues four extra queries per row.
        return (
            super()
            .get_queryset(request)
            .select_related("question", "user", "onboarding")
            .annotate(num_documents=Count("documents"))
        )

    @admin.display(description="Answer")
    def value(self, obj):
        return handler_for(obj.question.answer_type).display(obj) or "—"

    @admin.display(description="Files", ordering="num_documents")
    def document_count(self, obj):
        return obj.num_documents


@admin.register(Document)
class DocumentAdmin(RowActionsAdmin):
    list_display = (
        "id",
        "user_email",
        "question_text",
        "onboarding_title",
        "file_link",
        "approval_status",
        "uploaded_at",
        "row_actions",
    )
    list_filter = ("is_approved", "uploaded_at")
    search_fields = ("answer__user__email", "answer__question__question_text")
    readonly_fields = ("uploaded_at", "reviewed_at", "reviewed_by", "file_link")
    list_display_links = None
    actions: ClassVar[list[str]] = ["approve_documents", "reject_documents"]

    fieldsets = (
        (
            "Document",
            {"fields": ("answer", "uploaded_file", "file_link", "uploaded_at")},
        ),
        (
            "Review",
            {
                "fields": (
                    "is_approved",
                    "rejection_reason",
                    "reviewed_by",
                    "reviewed_at",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "answer",
                "answer__user",
                "answer__question",
                "answer__onboarding",
            )
        )

    @admin.display(description="User", ordering="answer__user__email")
    def user_email(self, obj):
        return obj.answer.user.email

    @admin.display(description="Question")
    def question_text(self, obj):
        text = obj.answer.question.question_text
        return f"{text[:50]}..." if len(text) > 50 else text

    @admin.display(description="Onboarding")
    def onboarding_title(self, obj):
        return obj.answer.onboarding.onboarding_title if obj.answer.onboarding else "—"

    @admin.display(description="File")
    def file_link(self, obj):
        if not obj.uploaded_file:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            obj.uploaded_file.url,
            obj.uploaded_file.name,
        )

    @admin.display(description="Status")
    def approval_status(self, obj):
        if obj.is_approved:
            return format_html(
                '<span class="rv-pill rv-pill--approved">Approved</span>'
            )
        if obj.rejection_reason:
            return format_html(
                '<span class="rv-pill rv-pill--rejected">Rejected</span>'
            )
        return format_html('<span class="rv-pill rv-pill--pending">Pending</span>')

    @admin.action(description="Approve selected documents")
    def approve_documents(self, request, queryset):
        updated = queryset.update(
            is_approved=True,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
            rejection_reason=None,
        )
        self.message_user(request, f"{updated} document(s) approved.")

    @admin.action(description="Reject selected documents")
    def reject_documents(self, request, queryset):
        updated = queryset.update(
            is_approved=False, reviewed_by=request.user, reviewed_at=timezone.now()
        )
        self.message_user(
            request,
            f"{updated} document(s) rejected. Add a reason on each one.",
        )
