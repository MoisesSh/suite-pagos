#!/bin/sh
set -e

echo "-> Ejecutando migrations..."
python manage.py migrate --noinput

echo "-> Colectando static files..."
python manage.py collectstatic --noinput --clear 2>/dev/null || true

echo "-> Iniciando servidor..."
exec "$@"
