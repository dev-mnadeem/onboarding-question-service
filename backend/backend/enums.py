from django.db import models


class UserRole(models.TextChoices):
    """Who a person is. Also decides which onboarding steps they are shown."""

    STAFF = "staff", "Staff"
    PARTICIPANT = "participant", "Participant"
    ADMIN = "admin", "Admin"


class AnswerType(models.TextChoices):
    """The shape of the value a question expects.

    Each member has a handler in ``answer.answer_types``.
    """

    TEXT = "text", "Text"
    NUMBER = "number", "Number"
    DATE = "date", "Date"
    BOOLEAN = "boolean", "Yes / No"
    FILE = "file", "File Upload"


class OnboardingStatus(models.TextChoices):
    """The five states an onboarding can be in.

    The legal moves between them live in ``onboarding.lifecycle.TRANSITIONS``.
    """

    PENDING = "pending", "Pending"
    IN_PROGRESS = "inprogress", "In Progress"
    IN_REVIEW = "inreview", "In Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
