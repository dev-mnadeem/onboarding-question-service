"""An LLM-backed assistant, written against the same port as the rule engine.

It deliberately uses ``urllib`` rather than a vendor SDK: the HTTP call is
twenty lines and adding a dependency for it would mean a reviewer who only
wants to run the tests still has to install it.

Any failure -- no key, a timeout, a non-JSON body -- is not an error. The
caller gets the rule engine's answer instead, with the provider name saying
so, because a review screen that breaks when a third party is down is worse
than one that is occasionally less eloquent.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import replace

from review_assistant.base import (
    APPROVE,
    BLOCKER,
    REQUEST_CHANGES,
    WARNING,
    ReviewBrief,
    ReviewFinding,
    ReviewSummary,
)
from review_assistant.rules import RuleBasedAssistant

logger = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"
MAX_TOKENS = 1024

SYSTEM_PROMPT = (
    "You review completed onboarding questionnaires. You are given the "
    "questions and the participant's answers as JSON. Reply with JSON only, "
    'shaped {"recommendation": "approve" | "request_changes", '
    '"headline": string, "findings": [{"severity": "blocker" | "warning", '
    '"message": string}]}. Use "blocker" only for a required question that '
    "was not answered. Keep the headline under 200 characters."
)


class AnthropicAssistant:
    """Calls the Messages API, falling back to ``RuleBasedAssistant``."""

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com",
        timeout: int = 20,
        fallback: RuleBasedAssistant | None = None,
        transport=None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.fallback = fallback or RuleBasedAssistant()
        # Injected in tests so the provider can be exercised without a network.
        self._transport = transport or self._post

    def summarise(self, brief: ReviewBrief) -> ReviewSummary:
        try:
            payload = self._transport(self._request_body(brief))
            return self._parse(payload)
        except Exception:
            logger.warning(
                "Review assistant provider '%s' unavailable, using rules.",
                self.name,
                exc_info=True,
            )
            summary = self.fallback.summarise(brief)
            return replace(summary, provider=f"rules (fallback from {self.name})")

    def _request_body(self, brief: ReviewBrief) -> dict:
        return {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "title": brief.title,
                            "role": brief.participant_role,
                            "total_steps": brief.total_steps,
                            "answers": [
                                {
                                    "step": record.step_title,
                                    "question": record.question_text,
                                    "type": record.answer_type,
                                    "required": record.is_required,
                                    "answered": record.is_answered,
                                    "value": record.display_value,
                                }
                                for record in brief.answers
                            ],
                        }
                    ),
                }
            ],
        }

    def _post(self, body: dict) -> dict:
        request = urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=json.dumps(body).encode(),
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode())

    def _parse(self, payload: dict) -> ReviewSummary:
        text = "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        )
        parsed = json.loads(text)

        recommendation = (
            APPROVE if parsed.get("recommendation") == APPROVE else REQUEST_CHANGES
        )
        findings = tuple(
            ReviewFinding(
                severity=BLOCKER if item.get("severity") == BLOCKER else WARNING,
                message=str(item["message"]),
            )
            for item in parsed.get("findings", [])
            if item.get("message")
        )
        return ReviewSummary(
            recommendation=recommendation,
            headline=str(parsed["headline"]),
            findings=findings,
            provider=self.name,
        )
