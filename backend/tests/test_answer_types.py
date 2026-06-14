from django.test import SimpleTestCase, TestCase

from answer.answer_types import (
    InlineValueRejectedError,
    handler_for,
    inline_value_fields,
    registered_types,
)
from backend.enums import AnswerType, UserRole
from tests.factories import (
    make_answer,
    make_document,
    make_onboarding,
    make_question,
    make_user,
)


class RegistryTests(SimpleTestCase):
    def test_every_answer_type_has_a_handler(self):
        assert set(registered_types()) == set(AnswerType.values)

    def test_an_unknown_type_is_a_lookup_error(self):
        with self.assertRaises(LookupError):
            handler_for("carrier-pigeon")

    def test_only_the_inline_types_contribute_columns(self):
        assert set(inline_value_fields()) == {
            "answer_text",
            "answer_number",
            "answer_date",
            "answer_boolean",
        }

    def test_a_file_handler_refuses_an_inline_value(self):
        with self.assertRaises(InlineValueRejectedError):
            handler_for(AnswerType.FILE).extract({"answer_text": "here"})

    def test_extract_picks_the_column_for_the_type(self):
        payload = {"answer_text": "Ada", "answer_number": 7}
        assert handler_for(AnswerType.TEXT).extract(payload) == "Ada"
        assert handler_for(AnswerType.NUMBER).extract(payload) == 7


class DisplayTests(TestCase):
    def setUp(self):
        self.onboarding = make_onboarding(user=make_user(), role=UserRole.PARTICIPANT)

    def _answer(self, answer_type, **values):
        question = make_question(f"Q {answer_type}", answer_type)
        return question, make_answer(self.onboarding, question, **values)

    def test_a_false_boolean_is_an_answer(self):
        question, answer = self._answer(AnswerType.BOOLEAN, answer_boolean=False)
        handler = handler_for(question.answer_type)
        assert handler.is_answered(answer) is True
        assert handler.display(answer) == "No"

    def test_an_empty_boolean_is_not(self):
        question, answer = self._answer(AnswerType.BOOLEAN)
        assert handler_for(question.answer_type).is_answered(answer) is False

    def test_a_date_is_rendered_iso(self):
        question, answer = self._answer(AnswerType.DATE, answer_date="1815-12-10")
        answer.refresh_from_db()
        assert handler_for(question.answer_type).display(answer) == "1815-12-10"

    def test_a_file_answer_counts_its_documents(self):
        question, answer = self._answer(AnswerType.FILE)
        handler = handler_for(question.answer_type)
        assert handler.is_answered(answer) is False

        make_document(answer)
        assert handler.is_answered(answer) is True
        assert handler.display(answer) == "1 file(s)"
