"""Admin for the onboarding models, plus the reviewer's own two screens.

The changelist and the review queue both need a step count per row. That
count is derived, not stored, so it is computed for the visible page in two
queries by ``build_step_plans`` and hung on the objects, rather than being
recomputed per row.
"""

from django.contrib import admin, messages
from django.contrib.admin.views.main import ChangeList
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path

from answer.answer_types import handler_for
from answer.models import Answer
from backend.admin_mixins import RowActionsAdmin
from backend.enums import OnboardingStatus
from onboarding import lifecycle
from onboarding.review_brief import build_review_brief
from onboarding.step_plan import build_step_plan, build_step_plans
from review_assistant import get_assistant

from .models import Onboarding, OnboardingStep, StepQuestion

REVIEW_QUEUE_PAGE_SIZE = 25


class OnboardingChangeList(ChangeList):
    """Attaches a step plan to every row on the current page."""

    def get_results(self, request):
        super().get_results(request)
        self.result_list = list(self.result_list)
        plans = build_step_plans(self.result_list)
        for onboarding in self.result_list:
            onboarding.step_plan = plans[onboarding.id]


@admin.register(Onboarding)
class OnboardingAdmin(RowActionsAdmin):
    exclude = ("review_reason", "reviewed_at", "reviewed_by")

    list_display = (
        "id",
        "onboarding_title",
        "created_for",
        "onboarding_for",
        "status",
        "progress",
        "created_at",
        "completed_at",
        "row_actions",
    )
    readonly_fields = ("status", "completed_steps", "created_at", "completed_at")
    list_filter = ("status", "onboarding_for")
    search_fields = ("onboarding_title", "created_for__email")
    list_display_links = None
    list_select_related = ("created_for",)

    def get_changelist(self, request, **kwargs):  # noqa: ARG002
        return OnboardingChangeList

    @admin.display(description="Progress")
    def progress(self, obj):
        total = len(obj.step_plan) if hasattr(obj, "step_plan") else 0
        return f"{obj.completed_steps} / {total}"

    def get_urls(self):
        custom = [
            path(
                "review-onboardings/",
                self.admin_site.admin_view(self.review_onboardings_list),
                name="review_onboardings_list",
            ),
            path(
                "review-onboarding/<int:onboarding_id>/",
                self.admin_site.admin_view(self.review_onboarding_detail),
                name="review_onboarding_detail",
            ),
        ]
        return custom + super().get_urls()

    def review_onboardings_list(self, request):
        """The review queue: what is waiting, newest first."""
        status_filter = request.GET.get("status", OnboardingStatus.IN_REVIEW)

        queryset = Onboarding.objects.select_related("created_for", "reviewed_by")
        if status_filter != "all":
            queryset = queryset.filter(status=status_filter)

        page = Paginator(queryset, REVIEW_QUEUE_PAGE_SIZE).get_page(
            request.GET.get("page")
        )
        plans = build_step_plans(page.object_list)
        for onboarding in page.object_list:
            onboarding.step_plan = plans[onboarding.id]

        context = {
            **self.admin_site.each_context(request),
            "title": "Review queue",
            "page_obj": page,
            "status_filter": status_filter,
            "status_choices": OnboardingStatus.choices,
            "waiting_count": Onboarding.objects.filter(
                status=OnboardingStatus.IN_REVIEW
            ).count(),
        }
        return render(request, "onboarding/review_list.html", context)

    def review_onboarding_detail(self, request, onboarding_id):
        onboarding = get_object_or_404(
            Onboarding.objects.select_related("created_for", "reviewed_by"),
            id=onboarding_id,
        )

        if request.method == "POST":
            return self._handle_review(request, onboarding)

        context = {
            **self.admin_site.each_context(request),
            "title": f"Onboarding - {onboarding.created_for.email}",
            "onboarding": onboarding,
            "steps_data": self._steps_with_answers(onboarding),
            "summary": get_assistant().summarise(build_review_brief(onboarding)),
            "can_review": onboarding.status in lifecycle.REVIEWABLE_STATES,
            "review_status_choices": (
                (OnboardingStatus.APPROVED, "Approve"),
                (OnboardingStatus.REJECTED, "Reject"),
            ),
        }
        return render(request, "onboarding/review_detail.html", context)

    def _handle_review(self, request, onboarding):
        if not self.has_change_permission(request, onboarding):
            messages.error(request, "You do not have permission to review this.")
            return redirect(request.path)

        try:
            lifecycle.review(
                onboarding,
                request.POST.get("status", ""),
                reason=request.POST.get("reason"),
                reviewer=request.user,
            )
        except (lifecycle.IllegalTransitionError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Onboarding marked '{onboarding.status}'.")

        return redirect(request.path)

    def _steps_with_answers(self, onboarding):
        """Each planned step with its questions and the participant's answers."""
        plan = build_step_plan(onboarding)

        steps = OnboardingStep.objects.filter(id__in=plan.step_ids()).prefetch_related(
            Prefetch(
                "step_questions",
                queryset=StepQuestion.objects.select_related("question").order_by(
                    "question_number"
                ),
            )
        )
        steps_by_id = {step.id: step for step in steps}

        answers = {
            answer.question_id: answer
            for answer in Answer.objects.filter(
                onboarding=onboarding, user_id=onboarding.created_for_id
            ).prefetch_related("documents")
        }

        return [
            {
                "title": planned.step.title,
                "order": planned.number,
                "questions": [
                    self._question_row(step_question, answers)
                    for step_question in steps_by_id[
                        planned.step.id
                    ].step_questions.all()
                ],
            }
            for planned in plan
            if planned.step.id in steps_by_id
        ]

    @staticmethod
    def _question_row(step_question, answers):
        question = step_question.question
        answer = answers.get(question.id)
        handler = handler_for(question.answer_type)

        return {
            "order": step_question.question_number,
            "question_text": question.question_text,
            "answer_type": question.answer_type,
            "is_required": question.is_required,
            # Rendering is the handler's job, so the template does not have to
            # know which answer_* column a question type uses.
            "value": handler.display(answer) if answer else "",
            "documents": list(answer.documents.all()) if answer else [],
        }


@admin.register(OnboardingStep)
class OnboardingStepAdmin(RowActionsAdmin):
    list_display = (
        "id",
        "title",
        "onboarding_for",
        "display_order",
        "question_count",
        "row_actions",
    )
    list_filter = ("onboarding_for", "services")
    search_fields = ("title",)
    ordering = ("display_order",)
    filter_horizontal = ("services",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(num_questions=Count("step_questions", distinct=True))
            .prefetch_related("services")
        )

    @admin.display(description="Questions", ordering="num_questions")
    def question_count(self, obj):
        return obj.num_questions


@admin.register(StepQuestion)
class StepQuestionAdmin(RowActionsAdmin):
    list_display = ("id", "step", "question", "question_number", "row_actions")
    list_select_related = ("step", "question")
    list_filter = ("step",)
    readonly_fields = ("question_number",)
