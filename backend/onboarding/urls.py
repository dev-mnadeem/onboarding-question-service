from django.urls import path

from .views import (
    OnboardingAllStepsAPIView,
    OnboardingReviewAPIView,
    OnboardingReviewSummaryAPIView,
    OnboardingStatusAPIView,
    OnboardingStepAPIView,
    UserOnboardingListAPIView,
    UserOnboardingStepSubmitAPIView,
)

urlpatterns = [
    path("user/", UserOnboardingListAPIView.as_view(), name="user-onboarding"),
    path(
        "user/answer/",
        UserOnboardingStepSubmitAPIView.as_view(),
        name="user-onboarding-step-complete",
    ),
    path(
        "<int:onboarding_id>/steps/",
        OnboardingAllStepsAPIView.as_view(),
        name="onboarding-all-steps",
    ),
    path(
        "<int:onboarding_id>/step/<int:step_order>/",
        OnboardingStepAPIView.as_view(),
        name="onboarding-step",
    ),
    path(
        "<int:onboarding_id>/status/",
        OnboardingStatusAPIView.as_view(),
        name="onboarding-status",
    ),
    path(
        "<int:onboarding_id>/review/",
        OnboardingReviewAPIView.as_view(),
        name="onboarding-review",
    ),
    path(
        "<int:onboarding_id>/review-summary/",
        OnboardingReviewSummaryAPIView.as_view(),
        name="onboarding-review-summary",
    ),
]
