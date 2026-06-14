from django.urls import reverse
from rest_framework.test import APITestCase

from backend.enums import AnswerType, OnboardingStatus, UserRole
from tests.factories import (
    make_admin,
    make_onboarding,
    make_question,
    make_step,
    make_user,
)


class AuthenticatedAPITestCase(APITestCase):
    def authenticate(self, user):
        self.client.force_authenticate(user=user)
        return user


class OwnershipTests(AuthenticatedAPITestCase):
    """Nobody may read an onboarding by guessing its id."""

    def setUp(self):
        self.owner = make_user("owner@example.test")
        self.stranger = make_user("stranger@example.test")
        self.onboarding = make_onboarding(
            user=self.owner, status=OnboardingStatus.REJECTED
        )
        self.onboarding.review_reason = "Missing document"
        self.onboarding.save(update_fields=["review_reason"])

    def test_owner_can_read_status(self):
        self.authenticate(self.owner)
        response = self.client.get(
            reverse("onboarding-status", args=[self.onboarding.id])
        )
        assert response.status_code == 200
        assert response.data["review_reason"] == "Missing document"

    def test_another_participant_gets_a_404_not_the_reason(self):
        self.authenticate(self.stranger)
        response = self.client.get(
            reverse("onboarding-status", args=[self.onboarding.id])
        )
        assert response.status_code == 404
        assert "Missing document" not in str(response.data)

    def test_another_participant_cannot_read_the_steps(self):
        self.authenticate(self.stranger)
        response = self.client.get(
            reverse("onboarding-all-steps", args=[self.onboarding.id])
        )
        assert response.status_code == 404

    def test_staff_may_read_any_onboarding(self):
        self.authenticate(make_admin())
        response = self.client.get(
            reverse("onboarding-status", args=[self.onboarding.id])
        )
        assert response.status_code == 200

    def test_anonymous_callers_are_refused(self):
        response = self.client.get(
            reverse("onboarding-status", args=[self.onboarding.id])
        )
        assert response.status_code in (401, 403)


class OnboardingListTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.user = make_user()
        make_step("Identity", questions=[make_question()], order=1)
        self.onboarding = make_onboarding(user=self.user)
        make_onboarding(user=make_user("other@example.test"))

    def test_the_list_is_paginated_and_scoped_to_the_caller(self):
        self.authenticate(self.user)
        response = self.client.get(reverse("user-onboarding"))

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert set(response.data) == {"count", "next", "previous", "results"}
        assert response.data["results"][0]["total_steps"] == 1
        assert response.data["results"][0]["is_editable"] is True

    def test_listing_does_not_scale_its_queries_with_the_row_count(self):
        """Five queries for one row, and five for nine."""
        self.authenticate(self.user)
        with self.assertNumQueries(5):
            assert self.client.get(reverse("user-onboarding")).data["count"] == 1

        for _ in range(8):
            make_onboarding(user=self.user)

        with self.assertNumQueries(5):
            assert self.client.get(reverse("user-onboarding")).data["count"] == 9


class StepEndpointTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.user = make_user()
        self.question = make_question("Your name?", AnswerType.TEXT)
        self.step_one = make_step("Identity", questions=[self.question], order=1)
        self.step_two = make_step(
            "Extras", questions=[make_question("Notes?")], order=2
        )
        self.onboarding = make_onboarding(user=self.user)
        self.authenticate(self.user)

    def test_opening_a_step_starts_the_onboarding(self):
        response = self.client.get(
            reverse("onboarding-step", args=[self.onboarding.id, 1])
        )
        assert response.status_code == 200
        assert response.data["step_number"] == 1
        self.onboarding.refresh_from_db()
        assert self.onboarding.status == OnboardingStatus.IN_PROGRESS

    def test_a_locked_step_is_refused(self):
        response = self.client.get(
            reverse("onboarding-step", args=[self.onboarding.id, 2])
        )
        assert response.status_code == 400
        assert "locked" in response.data["detail"]

    def test_saved_answers_come_back_with_the_step(self):
        self.client.post(
            reverse("user-onboarding-step-complete"),
            {
                "onboarding_id": self.onboarding.id,
                "step_id": self.step_one.id,
                "responses": [
                    {"question_id": self.question.id, "answer": {"answer_text": "Ada"}}
                ],
            },
            format="json",
        )
        response = self.client.get(
            reverse("onboarding-step", args=[self.onboarding.id, 1])
        )
        answer = response.data["step_questions"][0]["user_answer"]
        assert answer == {"answer_text": "Ada"}

    def test_all_steps_endpoint_numbers_every_step(self):
        response = self.client.get(
            reverse("onboarding-all-steps", args=[self.onboarding.id])
        )
        assert [step["step_number"] for step in response.data] == [1, 2]


class SubmitEndpointTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.user = make_user()
        self.question = make_question()
        self.step = make_step("Identity", questions=[self.question], order=1)
        self.onboarding = make_onboarding(user=self.user)
        self.authenticate(self.user)

    def _post(self, responses, onboarding=None):
        return self.client.post(
            reverse("user-onboarding-step-complete"),
            {
                "onboarding_id": (onboarding or self.onboarding).id,
                "step_id": self.step.id,
                "responses": responses,
            },
            format="json",
        )

    def test_a_valid_submission_completes_the_onboarding(self):
        response = self._post(
            [{"question_id": self.question.id, "answer": {"answer_text": "Ada"}}]
        )
        assert response.status_code == 201
        assert response.data["submitted_for_review"] is True
        assert response.data["status"] == OnboardingStatus.IN_REVIEW

    def test_a_duplicated_question_is_rejected(self):
        payload = {"question_id": self.question.id, "answer": {"answer_text": "Ada"}}
        response = self._post([payload, payload])
        assert response.status_code == 400

    def test_you_cannot_submit_to_somebody_elses_onboarding(self):
        stranger_onboarding = make_onboarding(user=make_user("x@example.test"))
        response = self._post(
            [{"question_id": self.question.id, "answer": {"answer_text": "Ada"}}],
            onboarding=stranger_onboarding,
        )
        assert response.status_code == 404


class ReviewEndpointTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.participant = make_user()
        self.onboarding = make_onboarding(
            user=self.participant, status=OnboardingStatus.IN_REVIEW
        )
        self.url = reverse("onboarding-review", args=[self.onboarding.id])

    def test_a_participant_cannot_review(self):
        self.authenticate(self.participant)
        response = self.client.patch(
            self.url, {"status": OnboardingStatus.APPROVED}, format="json"
        )
        assert response.status_code == 403

    def test_an_admin_can_approve(self):
        self.authenticate(self.admin)
        response = self.client.patch(
            self.url, {"status": OnboardingStatus.APPROVED}, format="json"
        )
        assert response.status_code == 200
        self.onboarding.refresh_from_db()
        assert self.onboarding.status == OnboardingStatus.APPROVED
        assert self.onboarding.reviewed_by == self.admin

    def test_a_rejection_without_a_reason_is_refused(self):
        self.authenticate(self.admin)
        response = self.client.patch(
            self.url, {"status": OnboardingStatus.REJECTED}, format="json"
        )
        assert response.status_code == 400
        assert "review_reason" in response.data

    def test_reviewing_something_not_submitted_is_refused(self):
        self.onboarding.status = OnboardingStatus.IN_PROGRESS
        self.onboarding.save(update_fields=["status"])
        self.authenticate(self.admin)

        response = self.client.patch(
            self.url, {"status": OnboardingStatus.APPROVED}, format="json"
        )
        assert response.status_code == 400
        assert "cannot move to" in response.data["detail"]


class ReviewSummaryEndpointTests(AuthenticatedAPITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.participant = make_user()
        self.required = make_question("Your name?", AnswerType.TEXT, is_required=True)
        make_step(
            "Identity", role=UserRole.PARTICIPANT, questions=[self.required], order=1
        )
        self.onboarding = make_onboarding(
            user=self.participant, status=OnboardingStatus.IN_REVIEW
        )
        self.url = reverse("onboarding-review-summary", args=[self.onboarding.id])

    def test_participants_cannot_read_the_summary(self):
        self.authenticate(self.participant)
        assert self.client.get(self.url).status_code == 403

    def test_the_default_provider_is_deterministic(self):
        self.authenticate(self.admin)
        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.data["provider"] == "rules"
        assert response.data["recommendation"] == "request_changes"
        assert response.data["findings"][0]["severity"] == "blocker"
