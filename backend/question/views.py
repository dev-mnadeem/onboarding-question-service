"""Read-only access to the question bank, for staff tooling."""

from typing import ClassVar

from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from question.models import Question
from question.serializers import QuestionSerializer


class QuestionListAPIView(ListAPIView):
    """``GET /api/question/`` -- the question bank, filterable by answer type.

    Participants receive their questions embedded in a step, so this is for
    the people who build questionnaires rather than fill them in.
    """

    serializer_class = QuestionSerializer
    permission_classes: ClassVar[list] = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        queryset = Question.objects.all()
        answer_type = self.request.query_params.get("answer_type")
        if answer_type:
            queryset = queryset.filter(answer_type=answer_type)
        return queryset.order_by("id")
