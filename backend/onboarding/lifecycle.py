"""The onboarding state machine.

An onboarding moves through five states. Everything that changes ``status``
goes through this module so that the legal moves are stated once, in
``TRANSITIONS``, instead of being re-derived in each view and admin action.

    pending -> inprogress -> inreview -> approved
                    ^                 \\-> rejected -> inprogress

``approved`` is terminal: an approved onboarding cannot be edited or pushed
back into review. ``rejected`` is not -- the reviewer leaves a
``review_reason`` and the participant reopens the onboarding by editing an
answer.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from backend.enums import OnboardingStatus

TRANSITIONS: dict[str, frozenset[str]] = {
    OnboardingStatus.PENDING: frozenset({OnboardingStatus.IN_PROGRESS}),
    OnboardingStatus.IN_PROGRESS: frozenset({OnboardingStatus.IN_REVIEW}),
    OnboardingStatus.IN_REVIEW: frozenset(
        {OnboardingStatus.APPROVED, OnboardingStatus.REJECTED}
    ),
    OnboardingStatus.APPROVED: frozenset(),
    OnboardingStatus.REJECTED: frozenset({OnboardingStatus.IN_PROGRESS}),
}

#: States in which a participant may still add or change answers.
EDITABLE_STATES = frozenset(
    {
        OnboardingStatus.PENDING,
        OnboardingStatus.IN_PROGRESS,
        OnboardingStatus.REJECTED,
    }
)

#: States a reviewer may act on.
REVIEWABLE_STATES = frozenset({OnboardingStatus.IN_REVIEW})

REVIEW_OUTCOMES = frozenset({OnboardingStatus.APPROVED, OnboardingStatus.REJECTED})


class IllegalTransitionError(Exception):
    """Raised when a caller asks for a move the state machine does not allow."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        allowed = sorted(TRANSITIONS.get(current, frozenset())) or ["nothing"]
        super().__init__(
            f"An onboarding in '{current}' cannot move to '{target}' "
            f"(allowed: {', '.join(allowed)})."
        )


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, frozenset())


def is_editable(onboarding) -> bool:
    return onboarding.status in EDITABLE_STATES


def _apply(onboarding, target: str, extra_fields: dict) -> None:
    if not can_transition(onboarding.status, target):
        raise IllegalTransitionError(onboarding.status, target)

    onboarding.status = target
    for field, value in extra_fields.items():
        setattr(onboarding, field, value)
    onboarding.save(update_fields=["status", *extra_fields])


def start(onboarding) -> bool:
    """Move a freshly created onboarding to ``inprogress``.

    Idempotent: opening an onboarding that is already under way is not an
    error, which is what the "fetch a step" endpoints need.
    """
    if onboarding.status != OnboardingStatus.PENDING:
        return False
    _apply(onboarding, OnboardingStatus.IN_PROGRESS, {})
    return True


def reopen_for_edit(onboarding) -> bool:
    """Put a rejected onboarding back in the participant's hands."""
    if onboarding.status != OnboardingStatus.REJECTED:
        return False
    _apply(
        onboarding,
        OnboardingStatus.IN_PROGRESS,
        {"reviewed_at": None, "reviewed_by": None},
    )
    return True


def submit_for_review(onboarding) -> bool:
    """Called once the last step has been answered."""
    if onboarding.status == OnboardingStatus.IN_REVIEW:
        return False
    _apply(onboarding, OnboardingStatus.IN_REVIEW, {"completed_at": timezone.now()})
    return True


@transaction.atomic
def review(onboarding, outcome: str, *, reason: str | None = None, reviewer=None):
    """Record a reviewer's decision.

    A rejection without a reason is refused here rather than in each caller,
    because the participant has no other way of learning what to fix.
    """
    if outcome not in REVIEW_OUTCOMES:
        raise IllegalTransitionError(onboarding.status, outcome)

    reason = (reason or "").strip()
    if outcome == OnboardingStatus.REJECTED and not reason:
        msg = "A rejection needs a reason."
        raise ValueError(msg)

    _apply(
        onboarding,
        outcome,
        {
            "review_reason": reason or None,
            "reviewed_at": timezone.now(),
            "reviewed_by": reviewer,
        },
    )
    return onboarding
