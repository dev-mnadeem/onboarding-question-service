"""Picks the assistant named by ``settings.REVIEW_ASSISTANT["PROVIDER"]``."""

from __future__ import annotations

import logging

from django.conf import settings

from review_assistant.base import ReviewAssistant
from review_assistant.llm import AnthropicAssistant
from review_assistant.rules import RuleBasedAssistant

logger = logging.getLogger(__name__)

_BUILDERS = {}


def provider(name: str):
    """Register a builder under a provider name."""

    def decorate(builder):
        _BUILDERS[name] = builder
        return builder

    return decorate


@provider("rules")
def _build_rules(config: dict) -> ReviewAssistant:
    return RuleBasedAssistant(thin_answer_chars=config["THIN_ANSWER_CHARS"])


@provider("anthropic")
def _build_anthropic(config: dict) -> ReviewAssistant:
    if not config.get("API_KEY"):
        logger.info("ANTHROPIC_API_KEY is not set, using the rule-based assistant.")
        return _build_rules(config)

    return AnthropicAssistant(
        api_key=config["API_KEY"],
        model=config["MODEL"],
        base_url=config["BASE_URL"],
        timeout=config["TIMEOUT_SECONDS"],
        fallback=_build_rules(config),
    )


def get_assistant(config: dict | None = None) -> ReviewAssistant:
    config = config if config is not None else settings.REVIEW_ASSISTANT
    name = config.get("PROVIDER", "rules")

    builder = _BUILDERS.get(name)
    if builder is None:
        logger.warning(
            "Unknown review assistant provider '%s', falling back to rules.", name
        )
        builder = _BUILDERS["rules"]

    return builder(config)


def registered_providers() -> tuple[str, ...]:
    return tuple(_BUILDERS)
