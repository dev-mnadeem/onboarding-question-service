"""Summarises a completed onboarding for whoever has to approve it.

``get_assistant()`` returns whichever provider the settings name. Every
provider implements ``summarise(ReviewBrief) -> ReviewSummary``, and every
provider that can fail falls back to the deterministic rule engine, so the
feature works on a checkout with no API key.
"""

from review_assistant.base import (
    APPROVE,
    BLOCKER,
    REQUEST_CHANGES,
    WARNING,
    AnswerRecord,
    ReviewAssistant,
    ReviewBrief,
    ReviewFinding,
    ReviewSummary,
)
from review_assistant.registry import get_assistant, registered_providers
from review_assistant.rules import RuleBasedAssistant

__all__ = [
    "APPROVE",
    "BLOCKER",
    "REQUEST_CHANGES",
    "WARNING",
    "AnswerRecord",
    "ReviewAssistant",
    "ReviewBrief",
    "ReviewFinding",
    "ReviewSummary",
    "RuleBasedAssistant",
    "get_assistant",
    "registered_providers",
]
