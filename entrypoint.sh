#!/bin/sh
set -e

python manage.py migrate --noinput

if [ "${SEED_USERS:-0}" = "1" ]; then
    python manage.py seed_users
fi

exec "$@"
