#!/bin/sh
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
# 2 核机建议 3 workers；可按 2*CPU+1 调整
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
