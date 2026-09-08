# Persistence, list versions and ongoing monitoring

## What is stored

Every screening is written to the database with the tenant, the request id, the
submitted data, the result and the **list version** it ran against. A list
version is one combined sanctions file identified by its SHA-256 checksum, so a
decision made months ago can be replayed against exactly the list it used.

Tables: `tenants`, `api_keys`, `list_versions`, `customers`, `screenings`, `alerts`.

By default the database is SQLite at `data/corridorcomply.db`. Set
`DATABASE_URL=postgresql+psycopg://user:pass@host/db` for production and run
`alembic upgrade head` (the Docker image does this on start).

## Keeping the list fresh

The API does not download lists itself any more (`SANCTIONS_AUTO_UPDATE_ENABLED`
defaults to false). Run the update script from a scheduler, then re-screen:

```
# every day at 03:00 (OFAC publishes same-day changes)
0 3 * * *  cd /srv && python scripts/update_sanctions.py --max-age-hours 20 && python -m app.monitoring rescreen
```

A running API notices a newer combined file within `SANCTIONS_RELOAD_CHECK_SECONDS`
(default 60) and reloads it; no restart needed.

## Ongoing monitoring

1. Put customers on file: `POST /api/v1/customers` with your reference, name, DOB,
   nationality and type. They are screened immediately. Or tick "keep these
   customers on file" in the upload UI.
2. After each list update, `python -m app.monitoring rescreen` (or
   `POST /api/v1/monitoring/rescreen`) re-screens every monitored customer that
   has not yet been screened against the current list version.
3. A change raises an alert:
   - `new_hit`: the customer matched nothing before and matches now
   - `new_match`: an additional list entry now matches
   - `hit_cleared`: a previous hit no longer matches
4. Alerts are listed at `GET /api/v1/alerts` and on the `/alerts` page, and are
   POSTed to the tenant's webhook (`PUT /api/v1/tenant {"webhook_url": ...}`).
   Acknowledge with `POST /api/v1/alerts/{id}/ack` and a reason; the reason is
   stored and audit-logged.

## API keys

```
python -m app.auth new-key acme-exchange "laptop of the MLRO"
python -m app.auth list
python -m app.auth revoke cc_abc123
```

Keys are stored as SHA-256 hashes in `api_keys`. `API_KEYS` / `API_KEYS_FILE`
still work for environment-based configuration. Everything a key does is scoped
to its tenant: screenings, customers, alerts and settings.
