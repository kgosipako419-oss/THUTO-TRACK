"""Django settings for thutotrack."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-me-in-production",
)
DEBUG = env_bool("DJANGO_DEBUG", True)
# Use `or` so an empty-string env var (common when set via Render's UI) falls
# back to the default instead of producing an empty list.
ALLOWED_HOSTS = [
    h.strip()
    for h in (os.getenv("DJANGO_ALLOWED_HOSTS") or "localhost,127.0.0.1,testserver").split(",")
    if h.strip()
]

# Auto-detect the public hostname from whichever PaaS we're running on so
# ALLOWED_HOSTS doesn't need manual configuration after deploy.
#   - Render injects RENDER_EXTERNAL_HOSTNAME
#   - Railway injects RAILWAY_PUBLIC_DOMAIN
_platform_host = os.getenv("RENDER_EXTERNAL_HOSTNAME") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if _platform_host and _platform_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_platform_host)

# CSRF: Django 4+ requires scheme+host in CSRF_TRUSTED_ORIGINS for cross-origin
# POSTs. Seed from env and auto-add the platform hostname when present.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in (os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS") or "").split(",") if o.strip()
]
if _platform_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{_platform_host}")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "core",
    "teachers",
    "schooladmin",
    "parents",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "thutotrack.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "thutotrack.wsgi.application"


if os.getenv("DATABASE_URL"):
    # Production: parse a Postgres URL of the form postgres://user:pass@host:port/dbname
    from urllib.parse import urlparse

    url = urlparse(os.environ["DATABASE_URL"])
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": url.path.lstrip("/"),
            "USER": url.username,
            "PASSWORD": url.password,
            "HOST": url.hostname,
            "PORT": url.port or 5432,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "teachers:login"
LOGIN_REDIRECT_URL = "core_home"
LOGOUT_REDIRECT_URL = "teachers:login"

# WhatsApp / Twilio webhook signature validation. When unset, validation is
# skipped — only safe for local development.
WHATSAPP_AUTH_TOKEN = os.getenv("WHATSAPP_AUTH_TOKEN", "")


LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Gaborone"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

# Django 5.1+ replaces STATICFILES_STORAGE / DEFAULT_FILE_STORAGE with a unified
# STORAGES dict. CompressedStaticFilesStorage (non-manifest) compresses with
# gzip/brotli but doesn't hash filenames — chosen over the manifest variant
# because the latter 500s if any referenced static file isn't in the manifest,
# which is brittle across PaaS build pipelines (Railway/Render/etc.).
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    # Railway/Render send healthchecks over internal HTTP without setting
    # X-Forwarded-Proto, so SECURE_SSL_REDIRECT would 301 them and the
    # platform marks the deploy as unhealthy. Exempt the probe path so the
    # platform always gets a direct 200.
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
