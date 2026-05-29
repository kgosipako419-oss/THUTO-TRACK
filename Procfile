release: python manage.py migrate --no-input
web: gunicorn thutotrack.wsgi:application --workers 2 --bind 0.0.0.0:$PORT
