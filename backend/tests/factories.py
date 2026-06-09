"""Small builders so each test states only what it cares about."""

from django.contrib.auth import get_user_model

from answer.models import Answer, Document
from backend.enums import AnswerType, OnboardingStatus, UserRole
from onboarding.models import Onboarding, OnboardingStep, StepQuestion
from question.models import Question
from services.models import Service

User = get_user_model()

PASSWORD = "test-password-123"


def make_user(email="participant@example.test", role=UserRole.PARTICIPANT, **extra):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        username=extra.pop("username", email.split("@")[0]),
        role=role,
        **extra,
    )


def make_admin(email="admin@example.test"):
    return User.objects.create_superuser(
        email=email, username="admin", password=PASSWORD
    )


def make_service(title="Residential care"):
    return Service.objects.create(title=title)


def make_question(text="Your name?", answer_type=AnswerType.TEXT, is_required=True):
    return Question.objects.create(
        question_text=text, answer_type=answer_type, is_required=is_required
    )


def make_step(title="Identity", role=None, services=(), questions=(), order=0):
    step = OnboardingStep.objects.create(
        title=title, onboarding_for=role, display_order=order
    )
    if services:
        step.services.set(services)
    for question in questions:
        StepQuestion.objects.create(step=step, question=question)
    return step


def make_onboarding(
    user=None,
    role=UserRole.PARTICIPANT,
    status=OnboardingStatus.PENDING,
    services=(),
    completed_steps=0,
):
    user = user or make_user()
    onboarding = Onboarding.objects.create(
        created_for=user,
        onboarding_title="Test onboarding",
        onboarding_for=role,
        status=status,
        completed_steps=completed_steps,
    )
    if services:
        onboarding.services.set(services)
    return onboarding


def make_answer(onboarding, question, **values):
    return Answer.objects.create(
        user=onboarding.created_for,
        question=question,
        onboarding=onboarding,
        **values,
    )


def make_document(answer, name="passport.pdf", is_approved=False):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return Document.objects.create(
        answer=answer,
        uploaded_file=SimpleUploadedFile(name, b"file-bytes"),
        is_approved=is_approved,
    )
