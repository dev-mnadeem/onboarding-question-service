"""Turns one onboarding into the plain-data brief a review assistant reads.

This is the only place that knows both the ORM and the assistant's data
shapes. Keeping it here means ``review_assistant`` stays free of Django
models and can be unit-tested without a database.
"""

from __future__ import annotations

from django.db.models import Count, Q

from answer.answer_types import handler_for
from answer.models import Answer
from onboarding.models import StepQuestion
from onboarding.step_plan import build_step_plan
from review_assistant import AnswerRecord, ReviewBrief


def build_review_brief(onboarding) -> ReviewBrief:
    """Collect every question in the plan and the participant's answer to it.

    Five queries whatever the number of steps or questions: three to build
    the plan, one for the step questions, and one for the answers with their
    document counts aggregated in SQL.
    """
    plan = build_step_plan(onboarding)

    step_questions = (
        StepQuestion.objects.filter(step_id__in=plan.step_ids())
        .select_related("question")
        .order_by("step_id", "question_number")
    )
    by_step: dict[int, list[StepQuestion]] = {}
    for step_question in step_questions:
        by_step.setdefault(step_question.step_id, []).append(step_question)

    answers = {
        answer.question_id: answer
        for answer in Answer.objects.filter(
            onboarding=onboarding, user_id=onboarding.created_for_id
        ).annotate(
            document_total=Count("documents", distinct=True),
            document_approved=Count(
                "documents", filter=Q(documents__is_approved=True), distinct=True
            ),
        )
    }

    records: list[AnswerRecord] = []
    for planned in plan:
        for step_question in by_step.get(planned.step.id, []):
            question = step_question.question
            answer = answers.get(question.id)
            handler = handler_for(question.answer_type)

            records.append(
                AnswerRecord(
                    step_title=planned.step.title,
                    step_number=planned.number,
                    question_number=step_question.question_number,
                    question_text=question.question_text,
                    answer_type=question.answer_type,
                    is_required=question.is_required,
                    is_answered=bool(answer) and _is_answered(handler, answer),
                    display_value=handler.display(answer) if answer else "",
                    document_count=getattr(answer, "document_total", 0)
                    if answer
                    else 0,
                    approved_document_count=(
                        getattr(answer, "document_approved", 0) if answer else 0
                    ),
                )
            )

    return ReviewBrief(
        onboarding_id=onboarding.id,
        title=onboarding.onboarding_title,
        participant_role=onboarding.onboarding_for,
        total_steps=len(plan),
        completed_steps=onboarding.completed_steps,
        answers=tuple(records),
    )


def _is_answered(handler, answer) -> bool:
    """Use the annotated counts for file answers instead of another query."""
    if handler.value_field is None:
        return getattr(answer, "document_total", 0) > 0
    return handler.is_answered(answer)
