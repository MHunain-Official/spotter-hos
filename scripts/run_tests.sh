#!/usr/bin/env bash
# Run required + preferred backend test suite
set -euo pipefail
cd "$(dirname "$0")/../backend"
# shellcheck disable=SC1091
source .venv/bin/activate
export USE_SQLITE=true
python manage.py test apps.hos.tests.test_engine -v 2
