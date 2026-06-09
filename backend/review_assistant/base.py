"""The data a reviewer needs, and the port that produces a summary of it.

Nothing in this module imports Django models. A provider receives a
``ReviewBrief`` -- plain values -- and returns a ``ReviewSummary``. That keeps
the LLM adapter testable without a database and makes the rule engine a
drop-in replacement rather than a special case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

APPROVE = "approve"
REQUEST_CHANGES = "request_changes"

BLOCKER = "blocker"
WARNING = "warning"


@dataclass(frozen=True)
class AnswerRecord:
    """One question and what the participant did with it."""

    step_title: str
    step_number: int
    question_number: int
    question_text: str
    answer_type: str
    is_required: bool
    is_answered: bool
    display_value: str = ""
    document_count: int = 0
    approved_document_count: int = 0


@dataclass(frozen=True)
class ReviewBrief:
    """Everything a provider is allowed to see about one onboarding."""

    onboarding_id: int
    title: str
    participant_role: str
    total_steps: int
    completed_steps: int
    answers: tuple[AnswerRecord, ...]


@dataclass(frozen=True)
class ReviewFinding:
    severity: str
    message: str


@dataclass(frozen=True)
class ReviewSummary:
    """What the reviewer is shown above the approve/reject buttons."""

    recommendation: str
    headline: str
    findings: tuple[ReviewFinding, ...] = field(default_factory=tuple)
    provider: str = "rules"

    @property
    def blockers(self) -> tuple[ReviewFinding, ...]:
        return tuple(f for f in self.findings if f.severity == BLOCKER)

    def as_dict(self) -> dict:
        return {
            "recommendation": self.recommendation,
            "headline": self.headline,
            "provider": self.provider,
            "findings": [
                {"severity": f.severity, "message": f.message} for f in self.findings
            ],
        }


class ReviewAssistant(Protocol):
    """The provider port."""

    name: str

    def summarise(self, brief: ReviewBrief) -> ReviewSummary: ...
