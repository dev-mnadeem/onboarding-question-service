from django.urls import path

from .views import DocumentFileAPIView, ListDocumentsAPIView, UploadDocumentAPIView

urlpatterns = [
    path("upload/", UploadDocumentAPIView.as_view(), name="upload-document"),
    path("documents/", ListDocumentsAPIView.as_view(), name="list-documents"),
    path(
        "documents/<int:document_id>/file/",
        DocumentFileAPIView.as_view(),
        name="document-file",
    ),
]
