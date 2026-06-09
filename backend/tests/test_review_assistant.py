"""The assistant is exercised without a database and without a network."""

import json

from django.test import SimpleTestCase, TestCase, override_settings

from backend.enums import AnswerType, OnboardingStatus, UserRole
from onboarding.review_brief import build_review_brief
from review_assistant import (
    APPROVE,
    BLOCKER,
    REQUEST_CHANGES,
    WARNING,
    AnswerRecord,
    ReviewBrief,
    RuleBasedAssistant,
    get_assistant,
)
from review_assistant.llm import AnthropicAssistant
from tests.factories import (
    make_answer,
    make_document,
    make_onboarding,
    make_question,
    make_step,
    make_user,
)


def record(**overrides):
    defaults = {
        "step_title": "Identity",
        "step_number": 1,
        "question_number": 1,
        "question_text": "Your name?",
        "answer_type": "text",
        "is_required": True,
        "is_answered": True,
        "display_value": "Ada Lovelace, born 1815",
    }
    return AnswerRecord(**{**defaults, **overrides})


def brief(*records):
    return ReviewBrief(
        onboarding_id=1,
        title="Test onboarding",
        participant_role="participant",
        total_steps=1,
        completed_steps=1,
        answers=tuple(records),
    )


class RuleEngineTests(SimpleTestCase):
    def setUp(self):
        self.assistant = RuleBasedAssistant(thin_answer_chars=15)

    def test_a_complete_questionnaire_is_recommended_for_approval(self):
        summary = self.assistant.summarise(brief(record()))
        assert summary.recommendation == APPROVE
        assert summary.findings == ()
        assert "Nothing flagged" in summary.headline

    def test_a_missing_required_answer_is_a_blocker(self):
        summary = self.assistant.summarise(brief(record(is_answered=False)))
        assert summary.recommendation == REQUEST_CHANGES
        assert summary.blockers[0].severity == BLOCKER
        assert "required and unanswered" in summary.blockers[0].message

    def test_a_missing_optional_answer_is_only_a_warning(self):
        summary = self.assistant.summarise(
            brief(record(is_answered=False, is_required=False))
        )
        assert summary.recommendation == APPROVE
        assert summary.findings[0].severity == WARNING

    def test_a_short_text_answer_is_flagged(self):
        summary = self.assistant.summarise(brief(record(display_value="ok")))
        assert summary.recommendation == APPROVE
        assert "may need more detail" in summary.findings[0].message

    def test_unapproved_documents_are_flagged(self):
        summary = self.assistant.summarise(
            brief(
                record(
                    answer_type="file",
                    display_value="1 file(s)",
                    document_count=1,
                    approved_document_count=0,
                )
            )
        )
        assert "none approved yet" in summary.findings[0].message

    def test_approved_documents_are_not_flagged(self):
        summary = self.assistant.summarise(
            brief(
                record(
                    answer_type="file",
                    display_value="1 file(s)",
                    document_count=1,
                    approved_document_count=1,
                )
            )
        )
        assert summary.findings == ()

    def test_a_number_answer_is_never_called_thin(self):
        summary = self.assistant.summarise(
            brief(record(answer_type="number", display_value="7"))
        )
        assert summary.findings == ()


class RegistryTests(SimpleTestCase):
    def test_the_default_provider_is_the_rule_engine(self):
        assistant = get_assistant({"PROVIDER": "rules", "THIN_ANSWER_CHARS": 15})
        assert assistant.name == "rules"

    def test_an_unknown_provider_falls_back_to_the_rule_engine(self):
        assistant = get_assistant({"PROVIDER": "nonsense", "THIN_ANSWER_CHARS": 15})
        assert assistant.name == "rules"

    def test_anthropic_without_a_key_falls_back_to_the_rule_engine(self):
        assistant = get_assistant(
            {
                "PROVIDER": "anthropic",
                "API_KEY": None,
                "MODEL": "m",
                "BASE_URL": "https://example.test",
                "TIMEOUT_SECONDS": 1,
                "THIN_ANSWER_CHARS": 15,
            }
        )
        assert assistant.name == "rules"

    @override_settings(
        REVIEW_ASSISTANT={
            "PROVIDER": "anthropic",
            "API_KEY": "sk-test",
            "MODEL": "m",
            "BASE_URL": "https://example.test",
            "TIMEOUT_SECONDS": 1,
            "THIN_ANSWER_CHARS": 15,
        }
    )
    def test_anthropic_with_a_key_is_selected(self):
        assert get_assistant().name == "anthropic"


class AnthropicProviderTests(SimpleTestCase):
    def _assistant(self, transport):
        return AnthropicAssistant(
            api_key="sk-test",
            model="test-model",
            base_url="https://example.test",
            transport=transport,
        )

    def test_a_well_formed_response_is_parsed(self):
        payload = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "recommendation": "request_changes",
                            "headline": "One question is unanswered.",
                            "findings": [
                                {"severity": "blocker", "message": "Q1 is empty."}
                            ],
                        }
                    ),
                }
            ]
        }
        summary = self._assistant(lambda _body: payload).summarise(brief(record()))

        assert summary.provider == "anthropic"
        assert summary.recommendation == REQUEST_CHANGES
        assert summary.findings[0].message == "Q1 is empty."

    def test_the_prompt_carries_the_questions_and_answers(self):
        captured = {}

        def transport(body):
            captured.update(body)
            return {"content": [{"type": "text", "text": '{"headline": "ok"}'}]}

        self._assistant(transport).summarise(brief(record()))
        content = json.loads(captured["messages"][0]["content"])

        assert captured["model"] == "test-model"
        assert content["answers"][0]["question"] == "Your name?"
        assert content["answers"][0]["value"] == "Ada Lovelace, born 1815"

    def test_a_transport_failure_falls_back_to_the_rule_engine(self):
        def explode(_body):
            msg = "connection refused"
            raise OSError(msg)

        summary = self._assistant(explode).summarise(brief(record(is_answered=False)))

        assert summary.recommendation == REQUEST_CHANGES
        assert summary.provider == "rules (fallback from anthropic)"
        assert summary.blockers

    def test_an_unparseable_body_falls_back_too(self):
        summary = self._assistant(
            lambda _body: {"content": [{"type": "text", "text": "not json"}]}
        ).summarise(brief(record()))
        assert summary.provider == "rules (fallback from anthropic)"


class ReviewBriefTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.text = make_question("Your name?", AnswerType.TEXT)
        self.upload = make_question("Upload your passport", AnswerType.FILE)
        self.optional = make_question("Notes?", AnswerType.TEXT, is_required=False)
        make_step(
            "Identity",
            role=UserRole.PARTICIPANT,
            questions=[self.text, self.upload, self.optional],
            order=1,
        )
        self.onboarding = make_onboarding(
            user=self.user, status=OnboardingStatus.IN_REVIEW
        )

    def test_the_brief_covers_every_question_in_the_plan(self):
        make_answer(self.onboarding, self.text, answer_text="Ada Lovelace")
        result = build_review_brief(self.onboarding)

        assert result.total_steps == 1
        assert len(result.answers) == 3
        assert result.answers[0].display_value == "Ada Lovelace"
        assert result.answers[0].is_answered is True
        assert result.answers[1].is_answered is False

    def test_a_file_answer_counts_its_documents(self):
        answer = make_answer(self.onboarding, self.upload)
        make_document(answer, is_approved=True)
        make_document(answer, name="second.pdf")

        upload_record = next(
            r
            for r in build_review_brief(self.onboarding).answers
            if r.answer_type == AnswerType.FILE
        )
        assert upload_record.document_count == 2
        assert upload_record.approved_document_count == 1
        assert upload_record.is_answered is True

    def test_building_a_brief_does_not_scale_with_the_question_count(self):
        make_answer(self.onboarding, self.text, answer_text="Ada Lovelace")
        with self.assertNumQueries(5):
            build_review_brief(self.onboarding)
