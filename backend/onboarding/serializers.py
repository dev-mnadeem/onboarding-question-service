from typing import ClassVar

from rest_framework import serializers

from answer.answer_types import handler_for, inline_value_fields
from answer.serializers import AnswerValueSerializer
from backend.enums import OnboardingStatus
from onboarding.models import Onboarding, OnboardingStep, StepQuestion
from question.serializers import QuestionSerializer


class StepQuestionSerializer(serializers.ModelSerializer):
    """A question inside a step, with the current user's answer attached.

    The answer comes from ``context["answers_by_question"]``, a map the view
    builds in one query. Looking it up per question here would be an N+1 the
    moment a step has more than a couple of questions.
    """

    question = QuestionSerializer(read_only=True)
    user_answer = serializers.SerializerMethodField()

    class Meta:
        model = StepQuestion
        fields: ClassVar[list[str]] = [
            "id",
            "question_number",
            "question",
            "user_answer",
        ]

    def get_user_answer(self, obj):
        answer = self.context.get("answers_by_question", {}).get(obj.question_id)
        if answer is None:
            return None

        handler = handler_for(obj.question.answer_type)
        if handler.value_field is None:
            documents = list(answer.documents.all())
            return {
                "documents": [
                    {
                        "id": doc.id,
                        "name": doc.uploaded_file.name,
                        "approved": doc.is_approved,
                    }
                    for doc in documents
                ]
            }

        payload = {
            field: getattr(answer, field)
            for field in inline_value_fields()
            if getattr(answer, field) is not None
        }
        if "answer_number" in payload:
            payload["answer_number"] = str(payload["answer_number"])
        if "answer_date" in payload:
            payload["answer_date"] = payload["answer_date"].isoformat()
        return payload or None


class OnboardingStepSerializer(serializers.ModelSerializer):
    step_questions = StepQuestionSerializer(many=True, read_only=True)
    step_number = serializers.SerializerMethodField()

    class Meta:
        model = OnboardingStep
        fields: ClassVar[list[str]] = [
            "id",
            "title",
            "step_number",
            "step_questions",
        ]

    def get_step_number(self, obj):
        """The position of this step in *this* onboarding's plan."""
        return self.context.get("step_numbers", {}).get(obj.id, obj.display_order)


class OnboardingSerializer(serializers.ModelSerializer):
    total_steps = serializers.SerializerMethodField()
    is_editable = serializers.SerializerMethodField()

    class Meta:
        model = Onboarding
        fields: ClassVar[list[str]] = [
            "id",
            "onboarding_title",
            "onboarding_for",
            "status",
            "created_at",
            "total_steps",
            "completed_steps",
            "is_editable",
            "review_reason",
            "reviewed_at",
        ]

    def get_total_steps(self, obj) -> int:
        plan = self.context.get("step_plans", {}).get(obj.id)
        return len(plan) if plan else 0

    def get_is_editable(self, obj) -> bool:
        from onboarding.lifecycle import is_editable

        return is_editable(obj)


class StepResponseItemSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    answer = AnswerValueSerializer()


class StepSubmitSerializer(serializers.Serializer):
    onboarding_id = serializers.IntegerField()
    step_id = serializers.IntegerField()
    responses = StepResponseItemSerializer(many=True, allow_empty=False)

    def validate_responses(self, responses):
        question_ids = [item["question_id"] for item in responses]
        if len(question_ids) != len(set(question_ids)):
            msg = "Each question may appear once per submission."
            raise serializers.ValidationError(msg)
        return responses


class OnboardingReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[OnboardingStatus.APPROVED, OnboardingStatus.REJECTED]
    )
    review_reason = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def validate(self, data):
        if (
            data["status"] == OnboardingStatus.REJECTED
            and not (data.get("review_reason") or "").strip()
        ):
            msg = {"review_reason": "Write a reason for the rejection"}
            raise serializers.ValidationError(msg)
        return data


class OnboardingStatusReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Onboarding
        fields: ClassVar[list[str]] = [
            "id",
            "status",
            "completed_steps",
            "review_reason",
            "reviewed_at",
        ]


class ReviewFindingSerializer(serializers.Serializer):
    severity = serializers.CharField()
    message = serializers.CharField()


class ReviewSummarySerializer(serializers.Serializer):
    """Documents the review-assistant response for the generated schema."""

    recommendation = serializers.CharField()
    headline = serializers.CharField()
    provider = serializers.CharField()
    findings = ReviewFindingSerializer(many=True)
