"""Django settings for RouteLog (Spotter HOS assessment)."""

from pathlib import Path
import os
import urllib.parse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# backend/.env for local flags; repo-root .env for shared secrets (ORS key, etc.)
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env", override=True)
load_dotenv(BASE_DIR / ".env.local", override=True)
load_dotenv(BASE_DIR.parent / ".env.local", override=True)

ON_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-in-production-routelog",
)
DEBUG = os.getenv("DJANGO_DEBUG", "false" if ON_VERCEL else "true").lower() == "true"

_default_hosts = "localhost,127.0.0.1,.vercel.app"
ALLOWED_HOSTS = [
    h.strip() for h in os.getenv("ALLOWED_HOSTS", _default_hosts).split(",") if h.strip()
]
if ON_VERCEL and ".vercel.app" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".vercel.app")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.drivers",
    "apps.trips",
    "apps.logs",
    "apps.hos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"


def _database_from_url(url: str) -> dict:
    parsed = urllib.parse.urlparse(url)
    name = parsed.path.lstrip("/")
    if "?" in name:
        name = name.split("?", 1)[0]
    qs = urllib.parse.parse_qs(parsed.query)
    sslmode = (qs.get("sslmode") or ["require"])[0]
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name or "postgres",
        "USER": urllib.parse.unquote(parsed.username or ""),
        "PASSWORD": urllib.parse.unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or 5432),
        "OPTIONS": {"sslmode": sslmode},
    }


# Prefer DATABASE_URL (Supabase / Neon / Vercel Postgres), else discrete POSTGRES_* vars.
if os.getenv("DATABASE_URL"):
    DATABASES = {"default": _database_from_url(os.environ["DATABASE_URL"])}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "routelog"),
            "USER": os.getenv("POSTGRES_USER", "routelog"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "routelog"),
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "OPTIONS": {"sslmode": os.getenv("POSTGRES_SSLMODE", "prefer")},
        }
    }

# Local/unit-test escape hatch when Postgres is unavailable.
if os.getenv("USE_SQLITE", "").lower() == "true":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Serverless filesystem is ephemeral — keep media under /tmp on Vercel
if ON_VERCEL:
    MEDIA_ROOT = Path("/tmp/routelog_media")
else:
    MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]
if os.getenv("CORS_ALLOW_VERCEL", "true").lower() == "true":
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https://.*\.vercel\.app$",
    ]
CORS_ALLOW_ALL_ORIGINS = DEBUG and os.getenv("CORS_ALLOW_ALL", "true").lower() == "true"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
}

ORS_API_KEY = os.getenv("ORS_API_KEY", "")
NOMINATIM_USER_AGENT = os.getenv(
    "NOMINATIM_USER_AGENT",
    "RouteLogHOS/1.0 (Spotter assessment; contact@localhost)",
)
ROUTING_FALLBACK_MPH = float(os.getenv("ROUTING_FALLBACK_MPH", "55"))

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() == "true"

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv("CSRF_TRUSTED_ORIGINS", "https://*.vercel.app").split(",")
    if o.strip()
]
