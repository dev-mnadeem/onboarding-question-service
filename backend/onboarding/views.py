"""HTTP for the onboarding domain.

Every view here is thin on purpose: resolve the object, hand off to
``submission``/``lifecycle``/``step_plan``, translate a domain exception into
a status code. The one rule these views own is ownership -- a participant may
only reach their own onboardings, and only a staff user may review.
"""

from typing import ClassVar

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from answer.models import Answer
from onboarding import lifecycle
from onboarding.models import Onboarding, OnboardingStep, StepQuestion
from onboarding.review_brief import build_review_brief
from onboarding.step_plan import build_step_plan, build_step_plans
from onboarding.submission import SubmissionError, submit_step, unlocked_step_number
from review_assistant import get_assistant

from .serializers import (
    OnboardingReviewSerializer,
    OnboardingSerializer,
    OnboardingStatusReadSerializer,
    OnboardingStepSerializer,
    ReviewSummarySerializer,
    StepSubmitSerializer,
)


def _visible_onboardings(user):
    """Staff see every onboarding. Everyone else sees only their own.

    Every lookup goes through this, so no endpoint can be turned into an
    object-id oracle by passing somebody else's onboarding id.
    """
    queryset = Onboarding.objects.select_related("created_for", "reviewed_by")
    if user.is_staff:
        return queryset
    return queryset.filter(created_for=user)


def _get_onboarding(user, onboarding_id):
    return get_object_or_404(_visible_onboardings(user), id=onboarding_id)


def _answers_by_question(onboarding, question_ids):
    """One query for every answer the serializer will ask for."""
    answers = Answer.objects.filter(
        onboarding=onboarding,
        user_id=onboarding.created_for_id,
        question_id__in=question_ids,
    ).prefetch_related("documents")
    return {answer.question_id: answer for answer in answers}


def _load_steps(plan):
    """Fetch the planned steps with their questions, ordered by the plan."""
    steps = OnboardingStep.objects.filter(id__in=plan.step_ids()).prefetch_related(
        Prefetch(
            "step_questions",
            queryset=StepQuestion.objects.select_related("question").order_by(
                "question_number"
            ),
        )
    )
    by_id = {step.id: step for step in steps}
    return [by_id[planned.step.id] for planned in plan if planned.step.id in by_id]


def _step_context(request, onboarding, plan, steps):
    question_ids = [
        step_question.question_id
        for step in steps
        for step_question in step.step_questions.all()
    ]
    return {
        "request": request,
        "step_numbers": {planned.step.id: planned.number for planned in plan},
        "answers_by_question": _answers_by_question(onboarding, question_ids),
    }


class UserOnboardingListAPIView(ListAPIView):
    """``GET /api/onboarding/user/`` -- the caller's own onboardings, paginated."""

    serializer_class = OnboardingSerializer
    permission_classes: ClassVar[list] = [IsAuthenticated]

    def get_queryset(self):
        return Onboarding.objects.filter(created_for=self.request.user).order_by(
            "-created_at"
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        page = getattr(self, "_page_for_context", None)
        context["step_plans"] = build_step_plans(page or [])
        return context

    def list(self, request, *args, **kwargs):  # noqa: ARG002
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        # Plans are built for the current page only, in two queries total,
        # rather than one plan per row.
        self._page_for_context = page if page is not None else list(queryset)
        serializer = self.get_serializer(self._page_for_context, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class OnboardingStepAPIView(APIView):
    """``GET /api/onboarding/<id>/step/<n>/`` -- one step, with saved answers."""

    permission_classes: ClassVar[list] = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: OnboardingStepSerializer()}, tags=["UserOnboarding"]
    )
    def get(self, request, onboarding_id, step_order):
        onboarding = _get_onboarding(request.user, onboarding_id)
        lifecycle.start(onboarding)

        plan = build_step_plan(onboarding)

        unlocked = unlocked_step_number(onboarding)
        if step_order > unlocked:
            msg = {
                "detail": f"Step {step_order} is locked. Complete step {unlocked} first."
            }
            raise ValidationError(msg)

        if plan.step_at(step_order) is None:
            raise ValidationError({"detail": f"Step {step_order} not found."})

        steps = _load_steps(plan)
        step = next(s for s in steps if s.id == plan.step_at(step_order).id)

        serializer = OnboardingStepSerializer(
            step, context=_step_context(request, onboarding, plan, [step])
        )
        return Response(serializer.data)


class OnboardingAllStepsAPIView(APIView):
    """``GET /api/onboarding/<id>/steps/`` -- the whole plan in one response."""

    permission_classes: ClassVar[list] = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: OnboardingStepSerializer(many=True)}, tags=["UserOnboarding"]
    )
    def get(self, request, onboarding_id):
        onboarding = _get_onboarding(request.user, onboarding_id)
        lifecycle.start(onboarding)

        plan = build_step_plan(onboarding)
        steps = _load_steps(plan)

        serializer = OnboardingStepSerializer(
            steps, many=True, context=_step_context(request, onboarding, plan, steps)
        )
        return Response(serializer.data)


class UserOnboardingStepSubmitAPIView(APIView):
    """``POST /api/onboarding/user/answer/`` -- save one step's answers."""

    permission_classes: ClassVar[list] = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=StepSubmitSerializer,
        responses={201: "Saved"},
        tags=["UserOnboarding"],
        operation_description="Validates and saves the answers for one step.",
    )
    def post(self, request):
        serializer = StepSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        onboarding = get_object_or_404(
            Onboarding, id=data["onboarding_id"], created_for=request.user
        )
        step = get_object_or_404(OnboardingStep, id=data["step_id"])

        try:
            result = submit_step(onboarding, step, data["responses"])
        except SubmissionError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(
            {
                "onboarding_id": result.onboarding_id,
                "step_number": result.step_number,
                "total_steps": result.total_steps,
                "completed_steps": result.completed_steps,
                "status": result.status,
                "submitted_for_review": result.submitted_for_review,
            },
            status=status.HTTP_201_CREATED,
        )


class OnboardingStatusAPIView(APIView):
    """``GET /api/onboarding/<id>/status/`` -- progress and any review reason."""

    permission_classes: ClassVar[list] = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: OnboardingStatusReadSerializer()}, tags=["UserOnboarding"]
    )
    def get(self, request, onboarding_id):
        onboarding = _get_onboarding(request.user, onboarding_id)
        return Response(OnboardingStatusReadSerializer(onboarding).data)


class OnboardingReviewAPIView(APIView):
    """``PATCH /api/onboarding/<id>/review/`` -- a reviewer's decision."""

    permission_classes: ClassVar[list] = [IsAuthenticated, IsAdminUser]

    @swagger_auto_schema(
        request_body=OnboardingReviewSerializer,
        responses={200: OnboardingStatusReadSerializer()},
        tags=["Review"],
    )
    def patch(self, request, onboarding_id):
        serializer = OnboardingReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        onboarding = get_object_or_404(Onboarding, id=onboarding_id)

        try:
            lifecycle.review(
                onboarding,
                serializer.validated_data["status"],
                reason=serializer.validated_data.get("review_reason"),
                reviewer=request.user,
            )
        except (lifecycle.IllegalTransitionError, ValueError) as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(OnboardingStatusReadSerializer(onboarding).data)


class OnboardingReviewSummaryAPIView(APIView):
    """``GET /api/onboarding/<id>/review-summary/`` -- the assistant's read.

    Deterministic by default: with no provider configured this is the rule
    engine, so the endpoint answers the same way on every checkout.
    """

    permission_classes: ClassVar[list] = [IsAuthenticated, IsAdminUser]

    @swagger_auto_schema(responses={200: ReviewSummarySerializer()}, tags=["Review"])
    def get(self, _request, onboarding_id):
        onboarding = get_object_or_404(
            Onboarding.objects.select_related("created_for"), id=onboarding_id
        )
        summary = get_assistant().summarise(build_review_brief(onboarding))
        return Response(summary.as_dict())
