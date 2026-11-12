#!/usr/bin/env bash
set -euo pipefail
python scripts/prepare_runtime.py
exec gunicorn intranet.wsgi:application --config gunicorn.conf.py
