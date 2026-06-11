"""Invite a newly created staff or participant account to onboard."""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from user.emails import send_onboarding_invite_email
from user.models import User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User, dispatch_uid="user.send_invite_after_user_created")
def send_invite_after_user_created(sender, instance, created, **kwargs):  # noqa: ARG001
    if not created or not instance.is_onboardable:
        return

    try:
        send_onboarding_invite_email(instance)
    except Exception:
        # A mail server being down must not roll back user creation.
        logger.exception("Could not send the onboarding invite to %s", instance.email)
    else:
        logger.info("Sent an onboarding invite to %s", instance.email)
