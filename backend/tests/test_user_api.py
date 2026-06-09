from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from backend.enums import UserRole
from tests.factories import PASSWORD, make_admin, make_user

User = get_user_model()


class AuthEndpointTests(APITestCase):
    def setUp(self):
        self.user = make_user("participant@example.test")

    def test_login_returns_a_token_pair_and_the_role(self):
        response = self.client.post(
            reverse("login"),
            {"email": self.user.email, "password": PASSWORD},
            format="json",
        )
        assert response.status_code == 200
        assert set(response.data) == {"access", "refresh", "role", "user_id"}
        assert response.data["role"] == UserRole.PARTICIPANT

    def test_a_wrong_password_is_refused(self):
        response = self.client.post(
            reverse("login"),
            {"email": self.user.email, "password": "nope"},
            format="json",
        )
        assert response.status_code == 400

    def test_me_requires_authentication(self):
        assert self.client.get(reverse("current-user")).status_code in (401, 403)

    def test_me_describes_the_caller(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("current-user"))
        assert response.data["email"] == self.user.email
        assert response.data["is_staff"] is False

    def test_logout_blacklists_the_refresh_token(self):
        login = self.client.post(
            reverse("login"),
            {"email": self.user.email, "password": PASSWORD},
            format="json",
        )
        refresh = login.data["refresh"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        assert (
            self.client.post(
                reverse("logout"), {"refresh": refresh}, format="json"
            ).status_code
            == 200
        )

        reuse = self.client.post(
            reverse("token_refresh"), {"refresh": refresh}, format="json"
        )
        assert reuse.status_code == 401


class RolePermissionTests(TestCase):
    def test_the_admin_role_grants_django_staff_and_superuser(self):
        """The rule used to sit in a form clean() where it never ran."""
        user = make_user("boss@example.test", role=UserRole.ADMIN)
        user.refresh_from_db()
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_promoting_an_existing_user_also_works_with_update_fields(self):
        user = make_user("later@example.test", role=UserRole.PARTICIPANT)
        assert user.is_staff is False

        user.role = UserRole.ADMIN
        user.save(update_fields=["role"])
        user.refresh_from_db()
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_other_roles_do_not_gain_admin_access(self):
        user = make_user("staffer@example.test", role=UserRole.STAFF)
        assert user.is_staff is False
        assert user.is_onboardable is True

    def test_a_superuser_is_created_with_the_admin_role(self):
        assert make_admin().role == UserRole.ADMIN


class InviteEmailTests(TestCase):
    def test_creating_a_participant_sends_the_invite(self):
        mail.outbox.clear()
        user = make_user("new@example.test", role=UserRole.PARTICIPANT)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]
        assert mail.outbox[0].subject == "Welcome! Complete your onboarding"
        assert "/login" in mail.outbox[0].body

    def test_creating_an_admin_does_not(self):
        mail.outbox.clear()
        make_user("nomail@example.test", role=UserRole.ADMIN)
        assert mail.outbox == []

    def test_saving_an_existing_user_does_not_send_a_second_invite(self):
        user = make_user("again@example.test")
        mail.outbox.clear()

        user.first_name = "Renamed"
        user.save(update_fields=["first_name"])
        assert mail.outbox == []
