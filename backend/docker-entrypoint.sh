#!/bin/sh
# Apply migrations before handing over to whatever CMD asked for.
set -eu

echo "Applying migrations..."
python manage.py migrate --noinput

exec "$@"
