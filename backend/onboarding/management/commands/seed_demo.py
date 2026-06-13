"""Populate an empty database with a questionnaire you can actually click through.

``manage.py seed_demo`` is what the README tells a reviewer to run, so it has
to leave the admin showing something meaningful: two services, seven
questions across four steps, and four participants spread over every state
the lifecycle has.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from answer.models import Answer
from backend.enums import AnswerType, OnboardingStatus, UserRole
from onboarding.models import Onboarding, OnboardingStep, StepQuestion
from question.models import Question
from services.models import Service

User = get_user_model()

DEMO_PASSWORD = "demo-password-1"

SERVICES = [
    ("Residential care", "Supported living placements."),
    ("Community outreach", "Visiting support in the participant's own home."),
]

# (step title, role, services, [(question text, answer type, required)])
STEPS = [
    (
        "Identity",
        None,
        [],
        [
            ("What is your full legal name?", AnswerType.TEXT, True),
            ("What is your date of birth?", AnswerType.DATE, True),
        ],
    ),
    (
        "Right to work",
        UserRole.STAFF,
        [],
        [
            ("Upload your right-to-work document", AnswerType.FILE, True),
            ("Do you hold a current driving licence?", AnswerType.BOOLEAN, True),
        ],
    ),
    (
        "Availability",
        UserRole.STAFF,
        ["Residential care"],
        [
            ("How many hours per week can you work?", AnswerType.NUMBER, True),
            ("Describe your preferred shift pattern", AnswerType.TEXT, False),
        ],
    ),
    (
        "Support needs",
        UserRole.PARTICIPANT,
        [],
        [("What support are you looking for?", AnswerType.TEXT, True)],
    ),
]

# (email, first name, role, service, status, completed steps)
PARTICIPANTS = [
    (
        "ada@example.test",
        "Ada",
        UserRole.STAFF,
        "Residential care",
        OnboardingStatus.IN_REVIEW,
        3,
    ),
    (
        "blaise@example.test",
        "Blaise",
        UserRole.STAFF,
        "Residential care",
        OnboardingStatus.IN_PROGRESS,
        1,
    ),
    (
        "chidi@example.test",
        "Chidi",
        UserRole.PARTICIPANT,
        None,
        OnboardingStatus.APPROVED,
        2,
    ),
    (
        "dora@example.test",
        "Dora",
        UserRole.PARTICIPANT,
        None,
        OnboardingStatus.PENDING,
        0,
    ),
]

ANSWERS = {
    "What is your full legal name?": {"answer_text": "Ada Lovelace"},
    "What is your date of birth?": {"answer_date": "1815-12-10"},
    "Do you hold a current driving licence?": {"answer_boolean": True},
    "How many hours per week can you work?": {"answer_number": "37.50"},
    "Describe your preferred shift pattern": {"answer_text": "Earlies"},
    "What support are you looking for?": {
        "answer_text": "Help with weekly shopping and appointments."
    },
}


class Command(BaseCommand):
    help = "Create a demo questionnaire, participants and answers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin-email",
            default="admin@example.test",
            help="Email for the superuser that is created if none exists.",
        )

    @transaction.atomic
    def handle(self, *args, **options):  # noqa: ARG002
        services = {
            title: Service.objects.get_or_create(
                title=title, defaults={"description": description}
            )[0]
            for title, description in SERVICES
        }

        steps = self._create_steps(services)
        admin = self._create_admin(options["admin_email"])
        self._create_onboardings(services, steps)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(services)} services, {len(steps)} steps, "
                f"{Question.objects.count()} questions and "
                f"{Onboarding.objects.count()} onboardings."
            )
        )
        self.stdout.write(f"Admin: {admin.email} / {DEMO_PASSWORD}")

    def _create_steps(self, services):
        steps = []
        for order, (title, role, service_titles, questions) in enumerate(STEPS, 1):
            step, _ = OnboardingStep.objects.get_or_create(
                title=title, defaults={"onboarding_for": role, "display_order": order}
            )
            step.services.set([services[name] for name in service_titles])

            for text, answer_type, required in questions:
                question, _ = Question.objects.get_or_create(
                    question_text=text,
                    defaults={"answer_type": answer_type, "is_required": required},
                )
                StepQuestion.objects.get_or_create(step=step, question=question)
            steps.append(step)
        return steps

    def _create_admin(self, email):
        admin = User.objects.filter(role=UserRole.ADMIN).first()
        if admin:
            return admin
        return User.objects.create_superuser(
            email=email, username="admin", password=DEMO_PASSWORD
        )

    def _create_onboardings(self, services, steps):
        questions = {q.question_text: q for q in Question.objects.all()}

        for email, first_name, role, service, status, completed in PARTICIPANTS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email.split("@")[0],
                    "first_name": first_name,
                    "role": role,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=["password"])

            onboarding, _ = Onboarding.objects.get_or_create(
                created_for=user,
                defaults={
                    "onboarding_title": f"{first_name}'s onboarding",
                    "onboarding_for": role,
                    "status": status,
                    "completed_steps": completed,
                    "completed_at": timezone.now()
                    if status
                    in (
                        OnboardingStatus.IN_REVIEW,
                        OnboardingStatus.APPROVED,
                    )
                    else None,
                },
            )
            if service:
                onboarding.services.set([services[service]])

            if completed:
                self._answer(onboarding, steps, questions, completed)

    @staticmethod
    def _answer(onboarding, steps, questions, completed_steps):
        for step in steps[:completed_steps]:
            for step_question in step.step_questions.select_related("question"):
                values = ANSWERS.get(step_question.question.question_text)
                if not values:
                    continue
                Answer.objects.get_or_create(
                    user=onboarding.created_for,
                    question=questions[step_question.question.question_text],
                    onboarding=onboarding,
                    defaults=values,
                )
