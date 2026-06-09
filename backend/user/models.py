from typing import ClassVar

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from backend.enums import UserRole

#: Roles that receive an onboarding questionnaire (and an invite email).
ONBOARDABLE_ROLES = frozenset({UserRole.STAFF, UserRole.PARTICIPANT})


class UserManager(BaseUserManager):
    """Email is the login field, so the default username-based manager is out."""

    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            msg = "Email must be set"
            raise ValueError(msg)

        extra_fields.setdefault("role", UserRole.PARTICIPANT)
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", UserRole.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            msg = "Superuser must have is_staff=True."
            raise ValueError(msg)
        if extra_fields.get("is_superuser") is not True:
            msg = "Superuser must have is_superuser=True."
            raise ValueError(msg)

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    role = models.CharField(
        max_length=20, choices=UserRole.choices, default=UserRole.PARTICIPANT
    )
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["username"]

    objects = UserManager()

    class Meta:
        ordering = ("email",)

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_onboardable(self) -> bool:
        return self.role in ONBOARDABLE_ROLES

    def save(self, *args, **kwargs):
        """Keep the Django permission flags in step with ``role``.

        The rule used to live in the admin forms' ``clean()``, where it never
        ran: the admin's fieldsets exclude ``is_staff`` and ``is_superuser``,
        so ``construct_instance`` dropped the values again. Role is the source
        of truth, so the model enforces it for every caller.
        """
        if self.role == UserRole.ADMIN and not (self.is_staff and self.is_superuser):
            self.is_staff = True
            self.is_superuser = True

            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "is_staff", "is_superuser"}

        super().save(*args, **kwargs)
