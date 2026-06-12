from django.urls import path

from .views import QuestionListAPIView

urlpatterns = [
    path("", QuestionListAPIView.as_view(), name="question-list"),
]
