from unittest import mock

from django.db import OperationalError
from django.urls import reverse
from rest_framework.test import APITestCase


class HealthTests(APITestCase):
    def test_healthz_is_open_and_checks_the_database(self):
        response = self.client.get(reverse("healthz"))
        assert response.status_code == 200
        assert response.data == {"status": "ok", "database": "ok"}

    def test_an_unreachable_database_is_a_503_without_driver_detail(self):
        failure = OperationalError("could not connect to db-host as app_user")
        with (
            mock.patch("backend.health.connection.cursor", side_effect=failure),
            self.assertLogs("backend.health", level="ERROR"),
        ):
            response = self.client.get(reverse("healthz"))

        assert response.status_code == 503
        assert response.data == {"status": "unhealthy", "database": "unreachable"}
