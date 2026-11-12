#!/usr/bin/env bash
set -euo pipefail
python scripts/prepare_runtime.py
if [[ "${SEED_CALENDAR_DEMO:-false}" == "true" ]]; then
  python manage.py seed_calendar_demo
fi
exec gunicorn intranet.wsgi:application --config gunicorn.conf.py
