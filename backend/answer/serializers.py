from typing import ClassVar

from django.conf import settings
from rest_framework import serializers

from answer.answer_types import InlineValueRejectedError, handler_for

from .models import Document

BYTES_PER_MB = 1024 * 1024


class AnswerValueSerializer(serializers.Serializer):
    """The value half of a submitted response.

    It accepts any one of the inline answer columns. Which one is *correct*
    depends on the question, which this serializer does not know about, so
    ``validate_for_question`` is called by the submit flow once the question
    has been resolved.
    """

    answer_text = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    answer_number = serializers.DecimalField(
        required=False, allow_null=True, max_digits=10, decimal_places=2
    )
    answer_date = serializers.DateField(required=False, allow_null=True)
    answer_boolean = serializers.BooleanField(required=False, allow_null=True)

    def validate(self, attrs):
        if all(value is None for value in attrs.values()):
            msg = "At least one answer field must be provided."
            raise serializers.ValidationError(msg)
        return attrs


def validate_for_question(payload: dict, question) -> dict:
    """Narrow a validated payload to the one column the question expects.

    Returns the fields to write, so that answering a number question with
    ``answer_text`` does not silently store prose in the wrong column.
    """
    handler = handler_for(question.answer_type)

    try:
        value = handler.extract(payload)
    except InlineValueRejectedError as exc:
        raise serializers.ValidationError({"detail": str(exc)}) from exc

    if value in (None, "") and question.is_required:
        msg = {
            "detail": (
                f"Question {question.id} expects '{handler.value_field}' "
                f"for answer type '{question.answer_type}'."
            )
        }
        raise serializers.ValidationError(msg)

    return {handler.value_field: value}


class DocumentUploadSerializer(serializers.Serializer):
    """multipart/form-data body for ``POST /api/answer/upload/``."""

    onboarding_id = serializers.IntegerField(
        help_text="ID of the onboarding this document belongs to"
    )
    question_id = serializers.IntegerField(
        help_text="ID of the question this document answers (must be a file question)"
    )
    file = serializers.FileField(help_text="The document to upload")

    def validate_file(self, uploaded):
        max_mb = settings.MAX_UPLOAD_SIZE_MB
        if uploaded.size > max_mb * BYTES_PER_MB:
            msg = f"File too large (max {max_mb}MB)."
            raise serializers.ValidationError(msg)
        return uploaded


class DocumentSerializer(serializers.ModelSerializer):
    """A stored document, as returned by the list and upload endpoints."""

    file_url = serializers.SerializerMethodField()
    question_id = serializers.IntegerField(source="answer.question_id", read_only=True)
    onboarding_id = serializers.IntegerField(
        source="answer.onboarding_id", read_only=True
    )

    class Meta:
        model = Document
        fields: ClassVar[list[str]] = [
            "id",
            "answer",
            "question_id",
            "onboarding_id",
            "uploaded_file",
            "file_url",
            "is_approved",
            "rejection_reason",
            "uploaded_at",
        ]
        read_only_fields = fields

    def get_file_url(self, obj) -> str | None:
        return obj.uploaded_file.url if obj.uploaded_file else None
