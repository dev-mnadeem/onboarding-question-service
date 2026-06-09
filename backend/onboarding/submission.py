"""Saving one step's worth of answers, and what that does to the onboarding.

The rules enforced here -- you may only submit the step you have unlocked,
only questions that belong to that step, and only while the onboarding is
editable -- used to be spread through the view that happened to need them.
They are the domain, so they live apart from HTTP and raise their own
exceptions, which ``onboarding.views`` translates into responses.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from answer.models import Answer
from answer.serializers import validate_for_question
from onboarding import lifecycle
from onboarding.models import StepQuestion
from onboarding.step_plan import build_step_plan


class SubmissionError(Exception):
    """Base class for a refused submission."""


class OnboardingLockedError(SubmissionError):
    def __init__(self, status: str) -> None:
        super().__init__(f"This onboarding is '{status}' and can no longer be edited.")


class StepNotInPlanError(SubmissionError):
    def __init__(self, step_id: int) -> None:
        super().__init__(f"Step {step_id} is not part of this onboarding.")


class StepLockedError(SubmissionError):
    def __init__(self, requested: int, unlocked: int) -> None:
        super().__init__(f"Step {requested} is locked. Complete step {unlocked} first.")


class QuestionsNotInStepError(SubmissionError):
    def __init__(self, question_ids: list[int]) -> None:
        self.question_ids = sorted(question_ids)
        super().__init__(f"Questions {self.question_ids} do not belong to this step.")


@dataclass(frozen=True)
class SubmissionResult:
    onboarding_id: int
    step_number: int
    total_steps: int
    completed_steps: int
    status: str
    submitted_for_review: bool


def unlocked_step_number(onboarding) -> int:
    """The highest step the participant is allowed to open or submit."""
    return onboarding.completed_steps + 1


@transaction.atomic
def submit_step(onboarding, step, responses) -> SubmissionResult:
    """Persist one step's answers and advance the onboarding."""
    if not lifecycle.is_editable(onboarding):
        raise OnboardingLockedError(onboarding.status)

    plan = build_step_plan(onboarding)
    step_number = plan.number_for(step.id)
    if step_number is None:
        raise StepNotInPlanError(step.id)

    unlocked = unlocked_step_number(onboarding)
    if step_number > unlocked:
        raise StepLockedError(step_number, unlocked)

    question_ids = [item["question_id"] for item in responses]
    step_questions = {
        step_question.question_id: step_question
        for step_question in StepQuestion.objects.filter(
            step=step, question_id__in=question_ids
        ).select_related("question")
    }

    unknown = set(question_ids) - set(step_questions)
    if unknown:
        raise QuestionsNotInStepError(list(unknown))

    # Answering anything puts the onboarding in progress: a first submission
    # starts it, and a submission after a rejection reopens it. Both are
    # no-ops if it is already in progress.
    lifecycle.start(onboarding)
    lifecycle.reopen_for_edit(onboarding)

    for item in responses:
        question = step_questions[item["question_id"]].question
        Answer.objects.update_or_create(
            user=onboarding.created_for,
            question=question,
            onboarding=onboarding,
            defaults=validate_for_question(item["answer"], question),
        )

    # completed_steps is a high-water mark: revisiting step 1 of 5 after
    # finishing step 4 must not undo the progress.
    if onboarding.completed_steps < step_number:
        onboarding.completed_steps = step_number
        onboarding.save(update_fields=["completed_steps"])

    total_steps = len(plan)
    submitted = bool(
        total_steps and onboarding.completed_steps >= total_steps
    ) and lifecycle.submit_for_review(onboarding)

    return SubmissionResult(
        onboarding_id=onboarding.id,
        step_number=step_number,
        total_steps=total_steps,
        completed_steps=onboarding.completed_steps,
        status=onboarding.status,
        submitted_for_review=submitted,
    )
