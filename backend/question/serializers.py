from typing import ClassVar

from rest_framework import serializers

from question.models import Question


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields: ClassVar[list[str]] = [
            "id",
            "question_text",
            "answer_type",
            "is_required",
        ]
