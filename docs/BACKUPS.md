# Database, backups and restore

## Which database where

| Where | Database | Why |
|---|---|---|
| Local development and tests | SQLite (`db.sqlite3`) | No setup, fast tests. |
| Deployed demo (Render) | PostgreSQL 18 | A real multi-user database. It enforces the row locks that payments rely on (`select_for_update()` does nothing on SQLite). |

The app picks the database from `DATABASE_URL`. Production settings refuse to start without it
(see `imaraworks/settings/prod.py` and `docs/ARCHITECTURE.md`).

## The deployed demo

- App: https://imaraworks-dwtq.onrender.com (health: `/health/`, database check: `/ready/`)
- Created from `render.yaml` (Render Blueprint), free plan for both the web service and the database.
- Database created: **2026-10-28**.

### Free-plan limits (checked against Render's docs on 2026-10-28)

- The free Postgres database **expires 30 days after creation: 2026-11-27**. After that it is
  inaccessible unless upgraded, and Render deletes it and its data after a further 14 days.
- Free databases have **no automatic backups**.
- The free web service sleeps after 15 minutes without traffic; the first request afterwards takes about a minute.

Because of this, backups are manual and are the team's responsibility. Take one before every demo, before
every deploy that changes migrations, and before the expiry date.

## Taking a backup

Needs Docker. Use the same major version as the database (18). Run in PowerShell, from any folder
**outside the repository**.

1. In Render, open the database and copy its **External Database URL**. Treat it like a password: never put it
   in the repo, the README, an issue or a chat.
2. Run:

```
New-Item -ItemType Directory -Force C:\Users\<you>\imara-backups
$env:PGURL = "<external database url>"
docker run --rm -e PGURL -v C:\Users\<you>\imara-backups:/backup postgres:18 sh -c 'pg_dump -Fc "$PGURL" -f /backup/imaraworks-YYYY-MM-DD.dump'
Remove-Item Env:PGURL
```

3. Check the file is not empty and lists the tables:

```
Get-Item C:\Users\<you>\imara-backups\imaraworks-YYYY-MM-DD.dump | Select-Object Name, Length
docker run --rm -v C:\Users\<you>\imara-backups:/backup postgres:18 pg_restore --list /backup/imaraworks-YYYY-MM-DD.dump | Select-Object -First 20
```

**Never commit a dump.** The repository is public and a dump holds payment records and password hashes.
Keep dumps in a private folder outside the project. `*.dump` should stay out of git.

## Retention

Keep the **last 7 dumps** and delete older ones. Name files with the date so they sort.

## Restoring (tested)

Restore into a fresh local database first to check a backup is usable:

```
docker run --name imara-pg18 -e POSTGRES_PASSWORD=localpass -e POSTGRES_DB=imara_restore -p 5433:5432 -d postgres:18
docker exec imara-pg18 pg_isready -U postgres
docker cp C:\Users\<you>\imara-backups\imaraworks-YYYY-MM-DD.dump imara-pg18:/tmp/b.dump
docker exec imara-pg18 pg_restore -U postgres -d imara_restore --no-owner --no-privileges /tmp/b.dump
docker exec imara-pg18 psql -U postgres -d imara_restore -c "select username from auth_user order by id;"
docker rm -f imara-pg18
```

`--no-owner --no-privileges` is needed because the dump names Render's database role, which does not exist locally.

**Result of the test on 2026-10-28:** a dump of the live Render database (about 60 KB, 157 entries) restored
into a local Postgres 18 with all 7 demo users and 6 vendors present.

To restore into a new Render database (for example after the free one expires), point `PGURL` at the new
database's External URL and run:

    $env:PGURL = "<new external database url>"
    docker run --rm -e PGURL -v C:\Users\<you>\imara-backups:/backup postgres:18 sh -c 'pg_restore --no-owner --no-privileges -d "$PGURL" /backup/imaraworks-YYYY-MM-DD.dump'
    Remove-Item Env:PGURL

Or skip the restore and start fresh: the app runs migrations and `seed_users` on start. A restore has not been
tried against a Render database yet; the local restore above is the tested path.

## Live demo

- App: https://imaraworks-dwtq.onrender.com
- Health check: https://imaraworks-dwtq.onrender.com/health/
- Uptime status: <stats.uptimerobot.com/2Gdx65XONA>

The demo runs on Render's free plan, so the first request after a quiet period can take about a minute.
The free database expires on 2026-11-27; see [Database, backups and restore](docs/BACKUPS.md).
## When the free database expires

1. Take a backup a few days before 2026-11-27.
2. Create a new free database (Render allows one free database per workspace) or upgrade.
3. Point `DATABASE_URL` at it, redeploy (migrations run on start), and restore the dump if the data matters.
4. Update the dates in this file.
