#!/usr/bin/env bash
# Render build hook: install deps, gather static files, apply migrations.
# Render runs this on every deploy.

set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input
