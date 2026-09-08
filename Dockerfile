# Screening-only image by default. Build with --build-arg WITH_ML=1 to add OCR and face matching.
FROM python:3.11-slim AS base
ARG WITH_ML=0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

COPY requirements.txt requirements-ml.txt ./
RUN pip install -r requirements.txt \
 && if [ "$WITH_ML" = "1" ]; then apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/* && pip install -r requirements-ml.txt; fi

COPY app ./app
COPY scripts ./scripts
COPY alembic.ini ./

# Sanctions data, the database and logs live outside the image.
# Set DATABASE_URL for Postgres; otherwise SQLite at /data/corridorcomply.db.
ENV SANCTIONS_DATA_DIR=/data/sanctions DATA_DIR=/data SANCTIONS_AUTO_UPDATE_ENABLED=false
VOLUME ["/data", "/srv/logs"]
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
