from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from answer.models import Answer
from backend.enums import OnboardingStatus
from onboarding.models import Onboarding
from onboarding.review_brief import build_review_brief


def seed():
    call_command("seed_demo", stdout=StringIO())


class SeedDemoTests(TestCase):
    def test_answers_follow_each_participants_own_plan(self):
        seed()
        chidi = Onboarding.objects.get(created_for__email="chidi@example.test")
        answered = set(
            Answer.objects.filter(onboarding=chidi).values_list(
                "question__question_text", flat=True
            )
        )

        assert "What support are you looking for?" in answered
        assert "Do you hold a current driving licence?" not in answered

    def test_the_approved_participant_has_nothing_missing(self):
        seed()
        chidi = Onboarding.objects.get(created_for__email="chidi@example.test")
        assert chidi.status == OnboardingStatus.APPROVED

        brief = build_review_brief(chidi)
        assert all(record.is_answered for record in brief.answers)

    def test_each_person_gives_their_own_name(self):
        seed()
        names = set(
            Answer.objects.filter(
                question__question_text="What is your full legal name?"
            ).values_list("answer_text", flat=True)
        )
        assert names == {"Ada Lovelace", "Blaise Pascal", "Chidi Anagonye"}

    def test_running_it_twice_adds_nothing(self):
        seed()
        counts = (Onboarding.objects.count(), Answer.objects.count())
        seed()
        assert (Onboarding.objects.count(), Answer.objects.count()) == counts
