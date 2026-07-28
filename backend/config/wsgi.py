"""
WSGI config for RouteLog.

On Vercel with USE_SQLITE, run migrate once per cold start so /tmp DB has tables.
Prefer DATABASE_URL (Supabase) in production.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

if os.getenv("USE_SQLITE", "").lower() == "true" or (
    os.getenv("VERCEL") and not os.getenv("DATABASE_URL")
):
    try:
        from django.core.management import call_command

        call_command("migrate", "--noinput", verbosity=0)
    except Exception as exc:  # noqa: BLE001
        # Don't crash import; health/plan will surface errors
        print(f"auto-migrate skipped/failed: {exc}")
