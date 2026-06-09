from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework.permissions import IsAdminUser

from backend.health import healthz
from user.views import onboarding_email_preview

schema_view = get_schema_view(
    openapi.Info(
        title="Limitless Horizon onboarding API",
        default_version="v1",
        description=(
            "Questionnaire onboarding: participants answer step by step, "
            "reviewers approve or reject."
        ),
    ),
    public=False,
    permission_classes=(IsAdminUser,),
)

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/user/", include("user.urls")),
    path("api/question/", include("question.urls")),
    path("api/answer/", include("answer.urls")),
    path("api/onboarding/", include("onboarding.urls")),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path("swagger.json", schema_view.without_ui(cache_timeout=0), name="schema-json"),
]

if settings.ENVIRONMENT == "development":
    urlpatterns += [
        path(
            "dev/email-preview/<int:user_id>/",
            onboarding_email_preview,
            name="onboarding_email_preview",
        ),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
