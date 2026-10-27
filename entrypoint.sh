#!/bin/sh
# Container entrypoint: prepare the database, then hand over to the CMD.
#
# Safe to run on every start:
#   - `migrate --noinput` applies only pending migrations (a no-op otherwise).
#   - `seed_users` uses get_or_create, so restarts do not duplicate data.
#
# Demo/users seeding is opt-in through SEED_USERS=1 (docker-compose sets it).
# With DEBUG off it also needs SEED_USER_PASSWORD, otherwise the command refuses
# to run and the container stops instead of starting with the dev password.
set -e

python manage.py migrate --noinput

if [ "${SEED_USERS:-0}" = "1" ]; then
    python manage.py seed_users
fi

# exec so gunicorn (or whatever the CMD is) becomes PID 1 and receives signals.
exec "$@"
