from django.db import models
from django.db.models import Max

from backend.enums import OnboardingStatus, UserRole
from question.models import Question
from services.models import Service
from user.models import User


class Onboarding(models.Model):
    """One participant working through one questionnaire.

    The step list is not stored here -- it is derived from ``OnboardingStep``
    by ``onboarding.step_plan``, because steps are shared templates that can
    be added after an onboarding has started. ``completed_steps`` is a
    high-water mark in that derived list, never a row count.
    """

    onboarding_for = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.STAFF,
    )
    created_for = models.ForeignKey(User, on_delete=models.CASCADE)
    onboarding_title = models.CharField(max_length=255)
    services = models.ManyToManyField(
        Service,
        blank=True,
        related_name="onboardings",
        help_text="Services this onboarding is for",
    )
    completed_steps = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_onboardings",
        help_text="Who made the approve/reject decision",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = (
            # The review queue is "everything waiting, newest first".
            models.Index(
                fields=("status", "-created_at"), name="onboarding_status_new"
            ),
            # The participant's own list.
            models.Index(
                fields=("created_for", "-created_at"), name="onboarding_owner_new"
            ),
        )

    def __str__(self):
        return f"{self.id} - {self.onboarding_title}"


class OnboardingStep(models.Model):
    """A reusable group of questions, targeted at a role and/or services.

    Leaving both targets blank makes the step apply to every onboarding.
    """

    onboarding_for = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        null=True,
        blank=True,
        help_text="Leave blank to show this step to all roles",
    )
    services = models.ManyToManyField(
        Service,
        blank=True,
        related_name="onboarding_steps",
        help_text="Leave blank to show this step for all services within the selected role",
    )
    title = models.CharField(max_length=255)
    display_order = models.PositiveIntegerField(
        default=0, help_text="Order for display in admin (lower number appears first)"
    )

    class Meta:
        ordering = ("display_order", "id")

    def __str__(self):
        role_text = self.onboarding_for or "All Roles"
        services_text = (
            ", ".join(s.title for s in self.services.all()) or "All Services"
        )
        return f"{self.title} ({role_text} - {services_text})"

    def save(self, *args, **kwargs):
        if not self.display_order and not self.pk:
            last_order = (
                OnboardingStep.objects.aggregate(Max("display_order"))[
                    "display_order__max"
                ]
                or 0
            )
            self.display_order = last_order + 1
        super().save(*args, **kwargs)


class StepQuestion(models.Model):
    """A question's position inside a step."""

    step = models.ForeignKey(
        OnboardingStep, on_delete=models.CASCADE, related_name="step_questions"
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    question_number = models.PositiveIntegerField(editable=False)

    class Meta:
        ordering = ("question_number",)
        constraints = (
            models.UniqueConstraint(
                fields=("step", "question_number"),
                name="unique_question_number_in_step",
            ),
            models.UniqueConstraint(
                fields=("step", "question"), name="unique_question_in_step"
            ),
        )

    def __str__(self):
        return f"Step {self.step.display_order} - Question {self.question_number}"

    def save(self, *args, **kwargs):
        if not self.question_number:
            last = (
                StepQuestion.objects.filter(step=self.step).aggregate(
                    Max("question_number")
                )["question_number__max"]
                or 0
            )
            self.question_number = last + 1
        super().save(*args, **kwargs)
