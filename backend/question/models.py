from django.db import models

from backend.enums import AnswerType


class Question(models.Model):
    """A single prompt. ``answer_type`` picks the handler in ``answer.answer_types``."""

    question_text = models.TextField()
    answer_type = models.CharField(max_length=20, choices=AnswerType.choices)
    is_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return self.question_text
