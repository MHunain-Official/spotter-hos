"""Vercel build hook: run migrations when DATABASE_URL is configured."""

from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("skip migrate: DATABASE_URL not set")
        return
    print("Running migrate (DATABASE_URL present)…")
    from django.core.management import execute_from_command_line

    execute_from_command_line(["manage.py", "migrate", "--noinput"])


if __name__ == "__main__":
    main()
