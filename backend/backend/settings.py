"""Django settings for the Limitless Horizon onboarding service.

Every value that differs between a laptop, CI and production is read from the
environment. Nothing in this file has to be edited to run the project: the
defaults give you SQLite, a console email backend and local file storage.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None) -> str | None:
    """Read a variable, treating an empty string as unset."""
    value = os.getenv(name)
    return value if value not in (None, "") else default


def env_bool(name: str, *, default: bool = False) -> bool:
    return (env(name) or str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    raw = env(name)
    return default if raw is None else int(raw)


def env_list(name: str, default: str = "") -> list[str]:
    return [part.strip() for part in (env(name) or default).split(",") if part.strip()]


ENVIRONMENT = env("ENVIRONMENT", "development")
DEBUG = env_bool("DEBUG", default=ENVIRONMENT == "development")

# A generated key is fine for a laptop. Anywhere else, refuse to start without one.
SECRET_KEY = env("SECRET_KEY")
if not SECRET_KEY:
    if ENVIRONMENT != "development":
        msg = "SECRET_KEY must be set outside development."
        raise RuntimeError(msg)
    SECRET_KEY = "django-insecure-development-only-key"

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost,0.0.0.0")

FRONTEND_URL = env("FRONTEND_URL", "http://localhost:3000").rstrip("/")

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_yasg",
    "corsheaders",
    "user",
    "services",
    "question",
    "answer",
    "onboarding",
]

AUTH_USER_MODEL = "user.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves the collected admin assets, so the container needs no web server
    # in front of gunicorn just to render the review screens.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# An explicit origin list. Browsers reject "allow any origin" together with
# credentialed requests, so the two settings below have to agree.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", FRONTEND_URL)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = ["authorization", "content-type", "x-csrftoken"]
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"
ASGI_APPLICATION = "backend.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# SQLite by default so that `manage.py migrate` and `manage.py test` work on a
# clean checkout. Point DB_ENGINE at MySQL to use the compose service.
DB_ENGINE = env("DB_ENGINE", "django.db.backends.sqlite3")

if "sqlite" in DB_ENGINE:
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": env("DB_NAME", str(BASE_DIR / "db.sqlite3")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": env("DB_NAME"),
            "USER": env("DB_USER"),
            "PASSWORD": env("DB_PASSWORD"),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", "3306"),
            "OPTIONS": {"init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files and uploads
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

STORAGES = {
    "default": {
        "BACKEND": env(
            "FILE_STORAGE_BACKEND", "django.core.files.storage.FileSystemStorage"
        )
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# Uploads larger than this are rejected by the serializer before they are read.
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 10)

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "backend.pagination.DefaultPagination",
    "PAGE_SIZE": env_int("API_PAGE_SIZE", 25),
    "EXCEPTION_HANDLER": "backend.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_TOKEN_MINUTES", 60)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_TOKEN_DAYS", 1)),
    "AUTH_HEADER_TYPES": (env("JWT_AUTH_HEADER_TYPE", "Bearer"),),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

SWAGGER_SETTINGS = {
    "USE_SESSION_AUTH": False,
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Paste 'Bearer <access token>' from /api/user/login/.",
        }
    },
}

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if ENVIRONMENT == "development"
    else "django.core.mail.backends.smtp.EmailBackend",
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "onboarding@limitless-horizon.test")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=False)

# ---------------------------------------------------------------------------
# Review assistant (see backend/review_assistant/)
# ---------------------------------------------------------------------------
REVIEW_ASSISTANT = {
    "PROVIDER": env("REVIEW_ASSISTANT_PROVIDER", "rules"),
    "API_KEY": env("ANTHROPIC_API_KEY"),
    "MODEL": env("REVIEW_ASSISTANT_MODEL", "claude-sonnet-4-5"),
    "BASE_URL": env("REVIEW_ASSISTANT_BASE_URL", "https://api.anthropic.com"),
    "TIMEOUT_SECONDS": env_int("REVIEW_ASSISTANT_TIMEOUT_SECONDS", 20),
    # An answer shorter than this is flagged as "thin" by the rule engine.
    "THIN_ANSWER_CHARS": env_int("REVIEW_ASSISTANT_THIN_ANSWER_CHARS", 15),
}

# ---------------------------------------------------------------------------
# Hardening applied only when DEBUG is off
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "{levelname} {name} {message}", "style": "{"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}

JAZZMIN_SETTINGS = {
    "site_title": "Limitless Horizon",
    "site_header": "Limitless Horizon",
    "site_brand": "Limitless Horizon",
    "copyright": "Limitless Horizon",
    "welcome_sign": "Welcome to the Admin Dashboard",
    "show_sidebar": True,
    "navigation_expanded": False,
    "sidebar_fixed": True,
    "order_with_respect_to": ["user", "services", "onboarding", "question", "answer"],
    "icons": {
        "user": "fas fa-user",
        "user.user": "fas fa-user",
        "services": "fas fa-concierge-bell",
        "services.service": "fas fa-cogs",
        "onboarding": "fas fa-project-diagram",
        "onboarding.onboarding": "fas fa-user-check",
        "onboarding.onboardingstep": "fas fa-list-ol",
        "onboarding.stepquestion": "fas fa-link",
        "question": "fas fa-question-circle",
        "question.question": "fas fa-question",
        "answer": "fas fa-file-alt",
        "answer.answer": "fas fa-comment-dots",
        "answer.document": "fas fa-file-pdf",
    },
    "custom_links": {
        "onboarding": [
            {
                "name": "Review queue",
                "url": "admin:review_onboardings_list",
                "icon": "fas fa-clipboard-check",
            },
        ],
    },
    "hide_apps": ["auth", "token_blacklist"],
}
