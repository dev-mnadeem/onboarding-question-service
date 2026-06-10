from django.db import models

from question.models import Question
from user.models import User


class Answer(models.Model):
    """One participant's response to one question, within one onboarding.

    The value lives in whichever ``answer_*`` column matches the question's
    ``answer_type``; ``answer.answer_types`` owns that mapping. File answers
    carry no inline value at all -- they are the related ``Document`` rows.
    """

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="answers"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_answers"
    )
    onboarding = models.ForeignKey(
        "onboarding.Onboarding",
        on_delete=models.CASCADE,
        related_name="answers",
        null=True,
        blank=True,
        help_text="The onboarding instance this answer belongs to",
    )
    answer_text = models.TextField(null=True, blank=True)
    answer_number = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    answer_date = models.DateField(null=True, blank=True)
    answer_boolean = models.BooleanField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("user", "question", "onboarding"),
                name="unique_answer_per_question_per_onboarding",
            ),
        )
        indexes = (
            # The review screen loads every answer of one onboarding at once.
            models.Index(fields=("onboarding", "question"), name="answer_onboarding_q"),
        )
        ordering = ("question_id",)

    def __str__(self):
        return f"Answer to Q{self.question_id} by {self.user.email}"


class Document(models.Model):
    """A file uploaded against a ``file`` question, plus its review state."""

    answer = models.ForeignKey(
        Answer, on_delete=models.CASCADE, related_name="documents"
    )
    uploaded_file = models.FileField(upload_to="documents")

    is_approved = models.BooleanField(default=False)

    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_documents",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = (models.Index(fields=("is_approved",), name="document_is_approved"),)
        ordering = ("-uploaded_at",)

    def __str__(self):
        return f"Document {self.pk} for answer {self.answer_id}"
