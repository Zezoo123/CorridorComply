#!/bin/sh
# Seed the lists on first start, migrate the database, run the API.
set -e
DATA_DIR="${DATA_DIR:-/data}"
LISTS="${SANCTIONS_DATA_DIR:-$DATA_DIR/sanctions}"
mkdir -p "$LISTS/combined" "$DATA_DIR" /srv/logs/audit
if [ -z "$(ls -A "$LISTS/combined" 2>/dev/null)" ] && [ -d /srv/lists/combined ] && [ -n "$(ls -A /srv/lists/combined 2>/dev/null)" ]; then
  echo "Seeding sanctions lists from the image into $LISTS"
  cp -R /srv/lists/. "$LISTS/"
fi
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
