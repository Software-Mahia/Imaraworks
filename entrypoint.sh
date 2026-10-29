#!/bin/sh
set -e

python manage.py migrate --noinput

if [ "${SEED_USERS:-0}" = "1" ]; then
    if [ "${SEED_REFRESH:-0}" = "1" ]; then
        python manage.py seed_users --refresh
    else
        python manage.py seed_users
    fi
fi

exec "$@"
