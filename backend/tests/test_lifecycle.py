from django.test import TestCase

from backend.enums import OnboardingStatus
from onboarding import lifecycle
from tests.factories import make_admin, make_onboarding, make_user


class TransitionTableTests(TestCase):
    def test_pending_may_only_start(self):
        assert lifecycle.can_transition(
            OnboardingStatus.PENDING, OnboardingStatus.IN_PROGRESS
        )
        assert not lifecycle.can_transition(
            OnboardingStatus.PENDING, OnboardingStatus.APPROVED
        )

    def test_approved_is_terminal(self):
        assert lifecycle.TRANSITIONS[OnboardingStatus.APPROVED] == frozenset()

    def test_rejected_can_be_reworked(self):
        assert lifecycle.can_transition(
            OnboardingStatus.REJECTED, OnboardingStatus.IN_PROGRESS
        )

    def test_editable_states(self):
        rejected = make_onboarding(
            user=make_user("rejected@example.test"), status=OnboardingStatus.REJECTED
        )
        in_review = make_onboarding(
            user=make_user("inreview@example.test"), status=OnboardingStatus.IN_REVIEW
        )
        assert lifecycle.is_editable(rejected)
        assert not lifecycle.is_editable(in_review)


class StartTests(TestCase):
    def test_start_moves_pending_to_in_progress(self):
        onboarding = make_onboarding(status=OnboardingStatus.PENDING)
        assert lifecycle.start(onboarding) is True
        onboarding.refresh_from_db()
        assert onboarding.status == OnboardingStatus.IN_PROGRESS

    def test_start_is_idempotent(self):
        onboarding = make_onboarding(status=OnboardingStatus.IN_PROGRESS)
        assert lifecycle.start(onboarding) is False
        assert onboarding.status == OnboardingStatus.IN_PROGRESS


class SubmitTests(TestCase):
    def test_submit_stamps_completed_at(self):
        onboarding = make_onboarding(status=OnboardingStatus.IN_PROGRESS)
        assert lifecycle.submit_for_review(onboarding) is True
        onboarding.refresh_from_db()
        assert onboarding.status == OnboardingStatus.IN_REVIEW
        assert onboarding.completed_at is not None

    def test_approved_onboarding_cannot_be_resubmitted(self):
        onboarding = make_onboarding(status=OnboardingStatus.APPROVED)
        with self.assertRaises(lifecycle.IllegalTransitionError):
            lifecycle.submit_for_review(onboarding)


class ReviewTests(TestCase):
    def setUp(self):
        self.reviewer = make_admin()

    def test_approval_records_the_reviewer(self):
        onboarding = make_onboarding(status=OnboardingStatus.IN_REVIEW)
        lifecycle.review(onboarding, OnboardingStatus.APPROVED, reviewer=self.reviewer)
        onboarding.refresh_from_db()
        assert onboarding.status == OnboardingStatus.APPROVED
        assert onboarding.reviewed_by == self.reviewer
        assert onboarding.reviewed_at is not None
        assert onboarding.review_reason is None

    def test_rejection_requires_a_reason(self):
        onboarding = make_onboarding(status=OnboardingStatus.IN_REVIEW)
        with self.assertRaises(ValueError):
            lifecycle.review(
                onboarding,
                OnboardingStatus.REJECTED,
                reason="   ",
                reviewer=self.reviewer,
            )
        onboarding.refresh_from_db()
        assert onboarding.status == OnboardingStatus.IN_REVIEW

    def test_cannot_review_something_not_submitted(self):
        onboarding = make_onboarding(status=OnboardingStatus.IN_PROGRESS)
        with self.assertRaises(lifecycle.IllegalTransitionError):
            lifecycle.review(
                onboarding, OnboardingStatus.APPROVED, reviewer=self.reviewer
            )

    def test_review_rejects_a_non_outcome_status(self):
        onboarding = make_onboarding(status=OnboardingStatus.IN_REVIEW)
        with self.assertRaises(lifecycle.IllegalTransitionError):
            lifecycle.review(
                onboarding, OnboardingStatus.PENDING, reviewer=self.reviewer
            )


class ReopenTests(TestCase):
    def test_reopen_clears_the_review_stamp(self):
        reviewer = make_admin()
        onboarding = make_onboarding(status=OnboardingStatus.IN_REVIEW)
        lifecycle.review(
            onboarding,
            OnboardingStatus.REJECTED,
            reason="Missing document",
            reviewer=reviewer,
        )

        assert lifecycle.reopen_for_edit(onboarding) is True
        onboarding.refresh_from_db()
        assert onboarding.status == OnboardingStatus.IN_PROGRESS
        assert onboarding.reviewed_at is None
        assert onboarding.reviewed_by is None
        # The reason survives so the participant can still read it.
        assert onboarding.review_reason == "Missing document"

    def test_reopen_ignores_anything_not_rejected(self):
        onboarding = make_onboarding(status=OnboardingStatus.IN_PROGRESS)
        assert lifecycle.reopen_for_edit(onboarding) is False
