from django.urls import reverse
from rest_framework.test import APITestCase


class HealthTests(APITestCase):
    def test_healthz_is_open_and_checks_the_database(self):
        response = self.client.get(reverse("healthz"))
        assert response.status_code == 200
        assert response.data == {"status": "ok", "database": "ok"}
