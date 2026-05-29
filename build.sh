#!/usr/bin/env bash
# Render build hook: install deps and gather static files.
# Migrations run at startup (see render.yaml startCommand) because on the
# first Blueprint deploy the linked Postgres may not be reachable until the
# web service is actually starting up.

set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
