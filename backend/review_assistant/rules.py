"""The deterministic assistant. Always available, needs no API key.

This is both the default provider and the fallback for every other one, so
the repository behaves identically on a laptop with no credentials as it does
in an environment that has them -- only the wording of the headline changes.
"""

from __future__ import annotations

from review_assistant.base import (
    APPROVE,
    BLOCKER,
    REQUEST_CHANGES,
    WARNING,
    ReviewBrief,
    ReviewFinding,
    ReviewSummary,
)

DEFAULT_THIN_ANSWER_CHARS = 15


class RuleBasedAssistant:
    """Flags unanswered required questions, thin prose and unapproved files."""

    name = "rules"

    def __init__(self, thin_answer_chars: int = DEFAULT_THIN_ANSWER_CHARS) -> None:
        self.thin_answer_chars = thin_answer_chars

    def summarise(self, brief: ReviewBrief) -> ReviewSummary:
        findings = [
            finding for record in brief.answers for finding in self._check(record)
        ]

        blockers = [f for f in findings if f.severity == BLOCKER]
        warnings = [f for f in findings if f.severity == WARNING]

        if blockers:
            recommendation = REQUEST_CHANGES
            headline = (
                f"{len(blockers)} required item(s) still missing across "
                f"{brief.total_steps} step(s)."
            )
        elif warnings:
            recommendation = APPROVE
            headline = (
                f"Every required question is answered. "
                f"{len(warnings)} item(s) are worth a second look."
            )
        else:
            recommendation = APPROVE
            headline = (
                f"All {len(brief.answers)} question(s) answered across "
                f"{brief.total_steps} step(s). Nothing flagged."
            )

        return ReviewSummary(
            recommendation=recommendation,
            headline=headline,
            findings=tuple(findings),
            provider=self.name,
        )

    def _check(self, record) -> list[ReviewFinding]:
        where = f"Step {record.step_number} ({record.step_title}), Q{record.question_number}"

        if not record.is_answered:
            if record.is_required:
                return [ReviewFinding(BLOCKER, f"{where} is required and unanswered.")]
            return [ReviewFinding(WARNING, f"{where} was skipped (optional).")]

        if record.answer_type == "file":
            if record.approved_document_count == 0:
                return [
                    ReviewFinding(
                        WARNING,
                        f"{where} has {record.document_count} uploaded file(s), "
                        f"none approved yet.",
                    )
                ]
            return []

        if (
            record.answer_type == "text"
            and len(record.display_value.strip()) < self.thin_answer_chars
        ):
            return [
                ReviewFinding(
                    WARNING,
                    f"{where} answered with {len(record.display_value.strip())} "
                    f"character(s) -- may need more detail.",
                )
            ]

        return []
