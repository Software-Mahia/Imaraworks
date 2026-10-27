# ImaraWorks vendor payment & approval system.
#
# The same image runs on a laptop, in CI, and on the deployed demo, which
# removes "works on my machine" drift (issue #26).
#
# Build:  docker build -t imaraworks .
# Run:    docker run --rm -p 8000:8000 --env-file .env imaraworks
# Compose: docker compose up --build
#
# The entrypoint (entrypoint.sh) applies migrations before the CMD runs;
# set SEED_USERS=1 to also create the demo users on start.

FROM python:3.12-slim AS base

# Python runs leaner and logs immediately in containers.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first: this layer is cached until requirements.txt changes,
# so code edits rebuild in seconds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY . .

# Collect static files at build time so WhiteNoise can serve them with DEBUG
# off (see imaraworks/settings/base.py). manage.py uses the dev settings by
# default, which allow the non-secret dev key; the runtime still reads the
# real environment, so no secret is baked into the image.
RUN python manage.py collectstatic --noinput

# Run as a non-root user: a compromise in the app can't then write to the
# image or the mounted volume as root. /app/data must exist in the image,
# otherwise Docker creates that volume mountpoint as root and appuser can't
# write the SQLite database into it.
RUN useradd --create-home --uid 1000 appuser \
    && chmod +x entrypoint.sh \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Migrations run on start (entrypoint.sh), then gunicorn, the production
# WSGI server (runserver is dev-only).
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "imaraworks.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
