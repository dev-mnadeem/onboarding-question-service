"""The one email this service sends."""

from django.conf import settings
from django.core.mail import send_mail

SUBJECT = "Welcome! Complete your onboarding"


def build_invite(user) -> tuple[str, str]:
    """Return the (subject, body) of the invite, without sending anything.

    Split out so the admin's preview page and the real send cannot drift.
    """
    invite_url = f"{settings.FRONTEND_URL}/login"
    body = (
        f"Hi {user.first_name or user.email},\n\n"
        f"Your account has been created. Please complete onboarding here:\n"
        f"{invite_url}\n\n"
        f"Thanks,\n"
        f"Limitless Horizon"
    )
    return SUBJECT, body


def send_onboarding_invite_email(user) -> int:
    """Send the invite. Returns the number of messages delivered."""
    subject, body = build_invite(user)
    return send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
