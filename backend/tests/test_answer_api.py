import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from answer.models import Document
from backend.enums import AnswerType, OnboardingStatus, UserRole
from tests.factories import (
    make_answer,
    make_document,
    make_onboarding,
    make_question,
    make_service,
    make_step,
    make_user,
)

MEDIA = tempfile.mkdtemp(prefix="limitless-test-media-")


def a_file(name="passport.pdf", size=64):
    return SimpleUploadedFile(name, b"x" * size, content_type="application/pdf")


@override_settings(MEDIA_ROOT=MEDIA)
class UploadDocumentTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.upload_question = make_question("Upload your passport", AnswerType.FILE)
        self.text_question = make_question("Your name?", AnswerType.TEXT)
        make_step(
            "Documents",
            questions=[self.upload_question, self.text_question],
            order=1,
        )
        self.onboarding = make_onboarding(user=self.user)
        self.url = reverse("upload-document")
        self.client.force_authenticate(user=self.user)

    def _upload(self, question, onboarding=None, file=None):
        return self.client.post(
            self.url,
            {
                "onboarding_id": (onboarding or self.onboarding).id,
                "question_id": question.id,
                "file": file or a_file(),
            },
            format="multipart",
        )

    def test_a_file_question_accepts_an_upload(self):
        response = self._upload(self.upload_question)
        assert response.status_code == 201
        assert Document.objects.count() == 1
        assert response.data["question_id"] == self.upload_question.id

    def test_a_text_question_does_not(self):
        response = self._upload(self.text_question)
        assert response.status_code == 400
        assert "does not accept file uploads" in response.data["detail"]

    def test_a_question_outside_this_onboardings_plan_is_refused(self):
        """A step the onboarding does not contain must not become an upload target.

        This is the case the old role-based check let through: a step for the
        same role but a different service.
        """
        other_service = make_service("Community outreach")
        outside = make_question("Upload your DBS check", AnswerType.FILE)
        make_step(
            "Other service",
            role=UserRole.PARTICIPANT,
            services=[other_service],
            questions=[outside],
            order=2,
        )

        response = self._upload(outside)
        assert response.status_code == 400
        assert "not part of this onboarding" in response.data["detail"]
        assert Document.objects.count() == 0

    def test_an_all_roles_step_is_still_a_valid_upload_target(self):
        """The mirror of the case above: the old check also refused valid ones."""
        everyone = make_question("Upload a photo", AnswerType.FILE)
        make_step("Open to all", role=None, questions=[everyone], order=3)

        assert self._upload(everyone).status_code == 201

    def test_you_cannot_upload_into_somebody_elses_onboarding(self):
        stranger = make_onboarding(user=make_user("x@example.test"))
        assert (
            self._upload(self.upload_question, onboarding=stranger).status_code == 404
        )

    def test_an_approved_onboarding_is_closed_to_uploads(self):
        self.onboarding.status = OnboardingStatus.APPROVED
        self.onboarding.save(update_fields=["status"])

        response = self._upload(self.upload_question)
        assert response.status_code == 400
        assert "closed to uploads" in response.data["detail"]

    @override_settings(MAX_UPLOAD_SIZE_MB=1, MEDIA_ROOT=MEDIA)
    def test_an_oversized_file_is_refused(self):
        response = self._upload(self.upload_question, file=a_file(size=2 * 1024 * 1024))
        assert response.status_code == 400
        assert "File too large (max 1MB)." in str(response.data["file"])


@override_settings(MEDIA_ROOT=MEDIA)
class ListDocumentsTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.stranger = make_user("stranger@example.test")
        question = make_question("Upload your passport", AnswerType.FILE)
        make_step("Documents", questions=[question], order=1)

        self.onboarding = make_onboarding(user=self.user)
        make_document(make_answer(self.onboarding, question))

        stranger_onboarding = make_onboarding(user=self.stranger)
        make_document(make_answer(stranger_onboarding, question), name="private.pdf")
        self.url = reverse("list-documents")

    def test_the_list_only_contains_the_callers_own_documents(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert "private.pdf" not in str(response.data)

    def test_the_list_is_paginated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        assert set(response.data) == {"count", "next", "previous", "results"}

    def test_filtering_by_onboarding(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url, {"onboarding_id": self.onboarding.id})
        assert response.data["count"] == 1

        response = self.client.get(self.url, {"onboarding_id": 9999})
        assert response.data["count"] == 0
