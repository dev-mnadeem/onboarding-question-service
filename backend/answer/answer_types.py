"""One handler per ``AnswerType``, kept in a registry.

Adding a question type used to mean editing a dict of required field names in
one module, an ``if answer_type == "file"`` branch in another and a hand-built
response payload in a third. Here a type is one class: declare which column
stores it, how to tell whether it has been answered and how to show it, then
register it.
"""

from __future__ import annotations

from typing import ClassVar

from backend.enums import AnswerType


class InlineValueRejectedError(Exception):
    """Raised for types whose value does not travel in the JSON body."""


class AnswerTypeHandler:
    """Base class. ``answer_type`` and ``value_field`` are the whole contract."""

    answer_type: ClassVar[str]
    #: Column on ``answer.models.Answer`` holding the value, or ``None``.
    value_field: ClassVar[str | None] = None
    #: Whether the value arrives in the JSON submit payload.
    accepts_inline_value: ClassVar[bool] = True

    def extract(self, payload: dict):
        """Pull this type's value out of a validated answer payload."""
        if not self.accepts_inline_value:
            msg = (
                f"A '{self.answer_type}' question is answered through "
                f"POST /api/answer/upload/, not in the submit payload."
            )
            raise InlineValueRejectedError(msg)
        return payload.get(self.value_field)

    def is_answered(self, answer) -> bool:
        value = getattr(answer, self.value_field, None)
        return value not in (None, "")

    def display(self, answer) -> str:
        value = getattr(answer, self.value_field, None)
        return "" if value in (None, "") else str(value)


class TextAnswerHandler(AnswerTypeHandler):
    answer_type = AnswerType.TEXT
    value_field = "answer_text"


class NumberAnswerHandler(AnswerTypeHandler):
    answer_type = AnswerType.NUMBER
    value_field = "answer_number"


class DateAnswerHandler(AnswerTypeHandler):
    answer_type = AnswerType.DATE
    value_field = "answer_date"

    def display(self, answer) -> str:
        value = answer.answer_date
        return "" if value is None else value.isoformat()


class BooleanAnswerHandler(AnswerTypeHandler):
    answer_type = AnswerType.BOOLEAN
    value_field = "answer_boolean"

    def is_answered(self, answer) -> bool:
        # False is a perfectly good answer to a yes/no question.
        return answer.answer_boolean is not None

    def display(self, answer) -> str:
        if answer.answer_boolean is None:
            return ""
        return "Yes" if answer.answer_boolean else "No"


class FileAnswerHandler(AnswerTypeHandler):
    answer_type = AnswerType.FILE
    value_field = None
    accepts_inline_value = False

    def is_answered(self, answer) -> bool:
        return answer.documents.exists()

    def display(self, answer) -> str:
        count = answer.documents.count()
        return f"{count} file(s)" if count else ""


_REGISTRY: dict[str, AnswerTypeHandler] = {}


def register(handler: AnswerTypeHandler) -> AnswerTypeHandler:
    _REGISTRY[handler.answer_type] = handler
    return handler


for _handler in (
    TextAnswerHandler(),
    NumberAnswerHandler(),
    DateAnswerHandler(),
    BooleanAnswerHandler(),
    FileAnswerHandler(),
):
    register(_handler)


def handler_for(answer_type: str) -> AnswerTypeHandler:
    try:
        return _REGISTRY[answer_type]
    except KeyError as exc:
        msg = f"No handler registered for answer type '{answer_type}'."
        raise LookupError(msg) from exc


def registered_types() -> tuple[str, ...]:
    return tuple(_REGISTRY)


def inline_value_fields() -> tuple[str, ...]:
    """The Answer columns that a submit payload is allowed to set."""
    return tuple(
        handler.value_field
        for handler in _REGISTRY.values()
        if handler.accepts_inline_value and handler.value_field
    )
