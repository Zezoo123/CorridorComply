# CorridorComply screening image.
#   docker build -t corridorcomply .                    # lists downloaded at build time (needs internet once)
#   docker build --build-arg WITH_LISTS=0 -t corridorcomply .   # no lists baked in (CI, or update after start)
#   docker build --build-arg WITH_ML=1 -t corridorcomply .      # adds OCR and face matching
FROM python:3.11-slim AS base
ARG WITH_ML=0
ARG WITH_LISTS=1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

COPY requirements.txt requirements-ml.txt ./
RUN pip install -r requirements.txt \
 && if [ "$WITH_ML" = "1" ]; then apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/* && pip install -r requirements-ml.txt; fi

COPY app ./app
COPY scripts ./scripts
COPY premium ./premium
COPY alembic.ini ./
COPY deploy/entrypoint.sh /usr/local/bin/corridorcomply-entrypoint
RUN chmod +x /usr/local/bin/corridorcomply-entrypoint

# Lists baked into the image at /srv/lists so the container screens offline from first start.
# The entrypoint copies them to /data/sanctions when that directory is empty; later updates
# (scripts/update_sanctions.py inside the container) write to /data/sanctions and survive restarts.
RUN if [ "$WITH_LISTS" = "1" ]; then SANCTIONS_DATA_DIR=/srv/lists python scripts/update_sanctions.py \
      && rm -rf /srv/lists/raw && find /srv/lists/normalized -type f -delete; \
    else mkdir -p /srv/lists; fi

# Runtime data (SQLite database, lists, audit log) lives in /data, outside the image.
ENV SANCTIONS_DATA_DIR=/data/sanctions DATA_DIR=/data SANCTIONS_AUTO_UPDATE_ENABLED=false
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"
ENTRYPOINT ["corridorcomply-entrypoint"]
