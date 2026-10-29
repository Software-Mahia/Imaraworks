# Frontend notes

The frontend is plain HTML, CSS and vanilla JavaScript served by Django templates (the `frontend` app): a login page, one page each for Employee, Manager and Finance, and a read-only audit trail for Administrators, sharing `frontend/static/frontend/auth.js`. There is no framework and no build step.

## Known limitations

- Tokens live in localStorage, so any script that runs on a page could read them. The pages never put server text into innerHTML (rows are built with createElement and textContent), but there is no Content Security Policy. An httpOnly cookie would be safer and needs more server work.
- Sign out clears the tokens in this browser. The server does not revoke the refresh token, so a copied one stays valid until it expires.
- A network error while refreshing an expired token also ends the session.
- The role check on each page is a convenience for the user. The API enforces every rule.
- Pages load their data when they open; there is no live refresh. Reload to see other people's changes.
- The Pay button is hidden on requests you raised yourself, so another Finance officer has to pay them. The seed data has two Finance users, faith and fiona, so each can pay the other's requests.
- "Paid totals" filter by the date the payment completed, in Kenyan days.
- A "Demo only" switch that makes the mock provider decline a payment appears only when the Finance page address ends in ?demo=1.
- Administrators can read the read-only `/audit/` page. It shows the whole log with payment details redacted.
- Frontend tests only check that each page route renders (tests/test_frontend_pages.py); the pages' JavaScript has no automated tests.

## How AI was used (frontend)

Claude was used in a chat window for design research and diagrams, first drafts of the pages and auth.js, Git and GitHub guidance, and help answering code-review comments. It never had access to the repository: it worked from pasted terminal output, screenshots and PR comments, and every change was copied in by hand, run locally and tested in the browser before it was committed.

How its output was checked:

- Field names, URLs and error shapes were checked against docs/API.md and real `curl` responses. Several first guesses were wrong (a guessed /api/requests/ URL, pending_manager and pending_finance statuses, amounts treated as numbers) and were replaced with what the API returns.
- Every frontend pull request was reviewed by a teammate, and the reviews caught real mistakes in AI-drafted code.

Examples of AI output that was corrected:

1. The first Employee page put server data into innerHTML. A teammate caught the XSS gap in review; rows are now built with createElement and textContent.
2. Example code still used Token auth after the switch to JWT; it was updated to use AUTH.apiFetch.
3. A suggested edit to requireRole landed inside the catch block, which would have left a blank page on an expired session. A reviewer caught it; it was fixed and retested.
4. apiFetch carried on with a failed response after logging out; a reviewer asked for a throw.
5. The Employee "Waiting on ..." line was wrong for drafts and rejected requests, because the API sends the approval block for every status. A reviewer found it; the page now shows it only for pending requests, and the backend was fixed too.
6. Approve and reject left their buttons disabled after a network error. A reviewer found it; both now use try/catch.
7. One pasted edit dropped the opening tag of the Paid totals section. The reviewer spotted it, and it was restored.

## Observability (#27)

### Done

- /health/ (liveness) and /ready/ (readiness; checks the database) for the hosting platform's probes. Production settings exempt both from the HTTPS redirect.
- A failed readiness check is logged with the reason (logger.exception), so a wrong DATABASE_URL or a rotated password is visible instead of a silent 503.

### Not done yet

- Sentry (error tracking): planned behind a SENTRY_DSN variable, with personal data and request bodies switched off, because errors on payment paths can carry names and amounts.
- Grafana (log dashboards): depends on where the app is hosted and how logs reach it. The plan is a dashboard of failed payments over time and the 5xx rate, with an alert on a run of failed payments.