"""File answers: upload one, list the caller's own."""

import logging
from typing import ClassVar

from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from answer.answer_types import handler_for
from onboarding import lifecycle
from onboarding.models import Onboarding, StepQuestion
from onboarding.step_plan import build_step_plan
from question.models import Question

from .models import Answer, Document
from .serializers import DocumentSerializer, DocumentUploadSerializer

logger = logging.getLogger(__name__)


class UploadDocumentAPIView(APIView):
    """``POST /api/answer/upload/`` -- attach a file to a file question.

    Membership is checked against the onboarding's computed step plan, not
    against the step's role. Two different onboardings for the same role can
    contain different steps once services are involved, so a role match is
    both too permissive (a question from another service's step) and too
    strict (a step marked "all roles" matches no role at all).
    """

    permission_classes: ClassVar[list] = [IsAuthenticated]
    parser_classes: ClassVar[list] = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        request_body=DocumentUploadSerializer,
        responses={201: DocumentSerializer()},
        tags=["Answers"],
    )
    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        onboarding = get_object_or_404(
            Onboarding, id=data["onboarding_id"], created_for=request.user
        )
        if not lifecycle.is_editable(onboarding):
            msg = {
                "detail": f"This onboarding is '{onboarding.status}' and is closed to uploads."
            }
            raise ValidationError(msg)

        question = get_object_or_404(Question, id=data["question_id"])
        if handler_for(question.answer_type).accepts_inline_value:
            msg = {
                "detail": (
                    f"Question {question.id} is a '{question.answer_type}' question "
                    f"and does not accept file uploads."
                )
            }
            raise ValidationError(msg)

        plan = build_step_plan(onboarding)
        if not StepQuestion.objects.filter(
            step_id__in=plan.step_ids(), question_id=question.id
        ).exists():
            msg = {"detail": f"Question {question.id} is not part of this onboarding."}
            raise ValidationError(msg)

        lifecycle.reopen_for_edit(onboarding)

        answer, _ = Answer.objects.get_or_create(
            user=request.user, question=question, onboarding=onboarding
        )
        document = Document.objects.create(answer=answer, uploaded_file=data["file"])

        logger.info(
            "Stored document %s for answer %s (onboarding %s)",
            document.id,
            answer.id,
            onboarding.id,
        )
        return Response(
            DocumentSerializer(document).data, status=status.HTTP_201_CREATED
        )


class ListDocumentsAPIView(ListAPIView):
    """``GET /api/answer/documents/`` -- the caller's uploads, paginated.

    Optional ``onboarding_id`` and ``question_id`` query parameters narrow the
    list.
    """

    serializer_class = DocumentSerializer
    permission_classes: ClassVar[list] = [IsAuthenticated]

    def get_queryset(self):
        queryset = Document.objects.filter(
            answer__user=self.request.user
        ).select_related("answer", "answer__question", "answer__onboarding")

        onboarding_id = self.request.query_params.get("onboarding_id")
        if onboarding_id:
            queryset = queryset.filter(answer__onboarding_id=onboarding_id)

        question_id = self.request.query_params.get("question_id")
        if question_id:
            queryset = queryset.filter(answer__question_id=question_id)

        return queryset.order_by("-uploaded_at")
