#!/usr/bin/env bash
set -euo pipefail
pip install --requirement requirements.txt
# Render persistent disks are NOT mounted during build.
SQLITE_PATH=/tmp/goodmona-build.sqlite3 python manage.py collectstatic --noinput
