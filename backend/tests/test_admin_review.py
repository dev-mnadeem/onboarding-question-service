"""The reviewer's own screens, which are the only UI this service has."""

from django.test import TestCase
from django.urls import reverse

from backend.enums import AnswerType, OnboardingStatus, UserRole
from tests.factories import (
    PASSWORD,
    make_admin,
    make_answer,
    make_onboarding,
    make_question,
    make_step,
    make_user,
)


class ReviewQueueTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.client.login(username=self.admin.email, password=PASSWORD)

        make_step("Identity", questions=[make_question()], order=1)
        self.waiting = make_onboarding(
            user=make_user("waiting@example.test"), status=OnboardingStatus.IN_REVIEW
        )
        self.draft = make_onboarding(
            user=make_user("draft@example.test"), status=OnboardingStatus.PENDING
        )
        self.url = reverse("admin:review_onboardings_list")

    def test_the_queue_shows_only_what_is_waiting_by_default(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert "waiting@example.test" in response.text
        assert "draft@example.test" not in response.text

    def test_the_status_filter_widens_it(self):
        response = self.client.get(self.url, {"status": "all"})
        assert "draft@example.test" in response.text

    def test_the_queue_is_not_reachable_anonymously(self):
        self.client.logout()
        response = self.client.get(self.url)
        assert response.status_code == 302
        assert "/admin/login/" in response["Location"]

    def test_the_queue_does_not_scale_its_queries_with_the_row_count(self):
        with self.assertNumQueries(10):
            self.client.get(self.url, {"status": "all"})

        for index in range(6):
            make_onboarding(
                user=make_user(f"extra{index}@example.test"),
                status=OnboardingStatus.IN_REVIEW,
            )

        with self.assertNumQueries(10):
            self.client.get(self.url, {"status": "all"})


class ReviewDetailTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.client.login(username=self.admin.email, password=PASSWORD)

        self.text = make_question("Your name?", AnswerType.TEXT)
        self.number = make_question("Hours per week?", AnswerType.NUMBER)
        make_step(
            "Identity",
            role=UserRole.PARTICIPANT,
            questions=[self.text, self.number],
            order=1,
        )
        self.onboarding = make_onboarding(
            user=make_user("waiting@example.test"),
            status=OnboardingStatus.IN_REVIEW,
            completed_steps=1,
        )
        make_answer(self.onboarding, self.text, answer_text="Ada Lovelace")
        make_answer(self.onboarding, self.number, answer_number="37.50")
        self.url = reverse("admin:review_onboarding_detail", args=[self.onboarding.id])

    def test_every_answer_type_is_rendered_not_just_text(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert "Ada Lovelace" in response.text
        assert "37.50" in response.text

    def test_the_assistant_summary_is_shown(self):
        response = self.client.get(self.url)
        assert "Review assistant" in response.text
        assert "provider: rules" in response.text

    def test_approving_records_the_decision(self):
        response = self.client.post(self.url, {"status": "approved", "reason": ""})
        assert response.status_code == 302

        self.onboarding.refresh_from_db()
        assert self.onboarding.status == OnboardingStatus.APPROVED
        assert self.onboarding.reviewed_by == self.admin

    def test_rejecting_without_a_reason_is_refused(self):
        self.client.post(self.url, {"status": "rejected", "reason": "  "})
        self.onboarding.refresh_from_db()
        assert self.onboarding.status == OnboardingStatus.IN_REVIEW

    def test_a_decision_on_a_draft_is_refused(self):
        """A crafted POST must not skip the state machine."""
        draft = make_onboarding(
            user=make_user("draft@example.test"), status=OnboardingStatus.PENDING
        )
        url = reverse("admin:review_onboarding_detail", args=[draft.id])

        self.client.post(url, {"status": "approved", "reason": ""})
        draft.refresh_from_db()
        assert draft.status == OnboardingStatus.PENDING

    def test_an_already_reviewed_onboarding_offers_no_form(self):
        self.client.post(self.url, {"status": "approved", "reason": ""})
        response = self.client.get(self.url)
        assert "Record decision" not in response.text


class ChangelistTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.client.login(username=self.admin.email, password=PASSWORD)
        make_step("Identity", questions=[make_question()], order=1)
        make_step("Extras", questions=[make_question("Notes?")], order=2)

    def test_the_onboarding_changelist_shows_a_computed_progress(self):
        make_onboarding(user=make_user("a@example.test"), completed_steps=1)
        response = self.client.get(reverse("admin:onboarding_onboarding_changelist"))
        assert response.status_code == 200
        assert "1 / 2" in response.text

    def test_the_changelist_does_not_scale_its_queries_with_the_row_count(self):
        make_onboarding(user=make_user("a@example.test"))
        url = reverse("admin:onboarding_onboarding_changelist")

        with self.assertNumQueries(10):
            self.client.get(url)

        for index in range(6):
            make_onboarding(user=make_user(f"b{index}@example.test"))

        with self.assertNumQueries(10):
            self.client.get(url)

    def test_the_answer_changelist_renders_each_type_through_its_handler(self):
        onboarding = make_onboarding(user=make_user("a@example.test"))
        make_answer(
            onboarding,
            make_question("Licence?", AnswerType.BOOLEAN),
            answer_boolean=False,
        )
        response = self.client.get(reverse("admin:answer_answer_changelist"))
        assert response.status_code == 200
        assert ">No<" in response.text
