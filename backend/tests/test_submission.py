from django.test import TestCase

from answer.models import Answer
from backend.enums import AnswerType, OnboardingStatus, UserRole
from onboarding import submission
from tests.factories import (
    make_onboarding,
    make_question,
    make_step,
    make_user,
)


class SubmitStepTests(TestCase):
    def setUp(self):
        self.name = make_question("Your name?", AnswerType.TEXT)
        self.hours = make_question("Hours per week?", AnswerType.NUMBER)
        self.step_one = make_step(
            "Identity", questions=[self.name, self.hours], order=1
        )
        self.step_two = make_step(
            "Extras", questions=[make_question("Notes?")], order=2
        )
        self.onboarding = make_onboarding(role=UserRole.PARTICIPANT)

    def _responses(self):
        return [
            {"question_id": self.name.id, "answer": {"answer_text": "Ada Lovelace"}},
            {"question_id": self.hours.id, "answer": {"answer_number": "37.50"}},
        ]

    def test_answers_are_written_to_the_column_the_question_expects(self):
        submission.submit_step(self.onboarding, self.step_one, self._responses())

        text_answer = Answer.objects.get(question=self.name)
        number_answer = Answer.objects.get(question=self.hours)
        assert text_answer.answer_text == "Ada Lovelace"
        assert text_answer.answer_number is None
        assert str(number_answer.answer_number) == "37.50"
        assert number_answer.answer_text is None

    def test_submitting_the_last_step_sends_it_for_review(self):
        submission.submit_step(self.onboarding, self.step_one, self._responses())
        result = submission.submit_step(
            self.onboarding,
            self.step_two,
            [
                {
                    "question_id": self.step_two.step_questions.get().question_id,
                    "answer": {"answer_text": "All good"},
                }
            ],
        )
        assert result.submitted_for_review is True
        assert result.status == OnboardingStatus.IN_REVIEW
        assert result.total_steps == 2

    def test_a_later_step_is_locked_until_the_current_one_is_done(self):
        with self.assertRaises(submission.StepLockedError):
            submission.submit_step(self.onboarding, self.step_two, [])

    def test_progress_is_a_high_water_mark(self):
        submission.submit_step(self.onboarding, self.step_one, self._responses())
        submission.submit_step(
            self.onboarding,
            self.step_two,
            [
                {
                    "question_id": self.step_two.step_questions.get().question_id,
                    "answer": {"answer_text": "All good"},
                }
            ],
        )
        self.onboarding.status = OnboardingStatus.IN_PROGRESS
        self.onboarding.save(update_fields=["status"])

        submission.submit_step(self.onboarding, self.step_one, self._responses())
        self.onboarding.refresh_from_db()
        assert self.onboarding.completed_steps == 2

    def test_a_question_from_another_step_is_refused(self):
        other = make_question("Unrelated?")
        make_step("Elsewhere", questions=[other], order=3)

        with self.assertRaises(submission.QuestionsNotInStepError) as ctx:
            submission.submit_step(
                self.onboarding,
                self.step_one,
                [{"question_id": other.id, "answer": {"answer_text": "x"}}],
            )
        assert ctx.exception.question_ids == [other.id]

    def test_a_step_outside_the_plan_is_refused(self):
        staff_step = make_step("Staff only", role=UserRole.STAFF, order=4)
        with self.assertRaises(submission.StepNotInPlanError):
            submission.submit_step(self.onboarding, staff_step, [])

    def test_an_approved_onboarding_is_closed_to_edits(self):
        onboarding = make_onboarding(
            user=make_user("approved@example.test"),
            status=OnboardingStatus.APPROVED,
        )
        with self.assertRaises(submission.OnboardingLockedError):
            submission.submit_step(onboarding, self.step_one, self._responses())

    def test_editing_a_rejected_onboarding_reopens_it(self):
        onboarding = make_onboarding(
            user=make_user("rejected@example.test"),
            status=OnboardingStatus.REJECTED,
        )
        result = submission.submit_step(onboarding, self.step_one, self._responses())
        assert result.status == OnboardingStatus.IN_PROGRESS

    def test_a_file_question_cannot_be_answered_inline(self):
        upload = make_question("Upload your passport", AnswerType.FILE)
        step = make_step("Documents", questions=[upload], order=5)
        self.onboarding.completed_steps = 2
        self.onboarding.save(update_fields=["completed_steps"])

        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            submission.submit_step(
                self.onboarding,
                step,
                [{"question_id": upload.id, "answer": {"answer_text": "here"}}],
            )
