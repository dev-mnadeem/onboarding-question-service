from django.urls import path

from .views import ListDocumentsAPIView, UploadDocumentAPIView

urlpatterns = [
    path("upload/", UploadDocumentAPIView.as_view(), name="upload-document"),
    path("documents/", ListDocumentsAPIView.as_view(), name="list-documents"),
]
