# Observability (#27)

## Done
- /health/ (liveness) and /ready/ (readiness; checks the database) for the hosting platform's probes. Production settings exempt both from the HTTPS redirect.
- A failed readiness check is logged with the reason (logger.exception), so a wrong DATABASE_URL or a rotated password is visible instead of a silent 503.

## Not done yet
- Sentry (error tracking): planned behind a SENTRY_DSN variable, with personal data and request bodies switched off, because errors on payment paths can carry names and amounts.
- Grafana (log dashboards): depends on where the app is hosted and how logs reach it. The plan is a dashboard of failed payments over time and the 5xx rate, with an alert on a run of failed payments.