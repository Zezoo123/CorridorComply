# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CorridorComply is a corridor-focused KYC and AML compliance engine for emerging-market fintechs. It provides identity verification (passport MRZ/ID card OCR, face matching) and sanctions screening with fuzzy name matching. Uses an open-core model: core KYC/AML features are open source, premium corridor-specific rules are closed source in `premium/`.

## Common Commands

```bash
# Install dependencies (core; add requirements-ml.txt for OCR/face matching, requirements-dev.txt for tests)
pip install -r requirements.txt -r requirements-dev.txt
pip install -r requirements-ml.txt   # optional, large

# Run the API server
uvicorn app.main:app --reload

# Run all fast tests (FastAPI TestClient; no server needed)
pytest

# Run a single test file
pytest tests/test_aml_service.py -v

# Include slow tests (load ML models / download real data)
pytest --run-slow

# Manual smoke scripts that need a running server live in scripts/manual/

# Update sanctions lists manually
python scripts/update_sanctions.py
```

## Architecture

### API Layer (`app/routes/`)
FastAPI routers:
- `/api/v1/kyc/verify` - Document OCR + face matching verification
- `/api/v1/aml/screen` and `/api/v1/aml/screen/batch` - Sanctions screening against consolidated lists
- `/api/v1/risk/combined` - Combined risk scoring
- `/api/v1/customers`, `/api/v1/monitoring/rescreen`, `/api/v1/alerts`, `/api/v1/screenings`, `/api/v1/tenant`, `/api/v1/lists/current` (`records.py`) - persistence and ongoing monitoring
- `/screen`, `/alerts`, `/review` (`screen_ui.py`) - Jinja2 UI: upload a customer file, alerts, and the review console (queue, case page, disposition with mandatory reason). `POST /api/v1/decisions/{id}/disposition`, `GET /api/v1/customers/{ref}/evidence` (migration 0003 adds disposition columns). The UI acts for one tenant (`UI_TENANT`, default `default`).

`/api/v1/*` routes require `X-API-Key` when keys are configured (`app/auth.py`, `API_KEYS` / `API_KEYS_FILE`); the tenant lands in `request.state.tenant` and in every audit event.

### Services (`app/services/`)
- `kyc_service.py` - Orchestrates document validation and face matching
- `aml_service.py` - Sanctions screening (thin wrapper over `screening.py`)
- `records.py` - Persistence: tenants, list versions (by checksum), screenings, customers, re-screening + alerts + webhook
- `screening.py` - In-memory screening index: names + aliases, blocking keys, entity-type filter, DOB/nationality agreement, `list_version`
- `risk_engine.py` - Unified risk scoring (AML weighted 60%, KYC 40%)
- `sanctions_loader.py` - Loads/caches combined sanctions CSV, auto-finds latest file
- `face_match.py` - DeepFace-based face comparison
- `liveness.py` - `LivenessProvider` interface: `NullProvider` (default, reports "not checked") and `HttpProvider` (vendor endpoint via `LIVENESS_PROVIDER=http`, `LIVENESS_URL`, `LIVENESS_API_KEY`); result feeds `RiskEngine.calculate_kyc_risk_score(liveness=...)`

### Corridor engine (`app/corridor/`)
- `schema.py` - Pydantic contract for a ruleset (documents, required fields, screening policy, rules with `when` conditions over `FIELDS`, reporting). `status` must be `draft` until `reviewed_by` is set.
- `engine.py` - `RulesetRegistry` loads `premium/corridor_rules/*.json` (or `CORRIDOR_RULES_DIR`); `decide()` builds facts and fires every matching rule; outcome is the most severe.
- `identifiers.py` - ID-number validators: `qatar_id` (birth year + nationality), `pk_cnic`, `in_aadhaar` (Verhoeff), `bd_nid`, `ph_philsys`, passports.
- `names.py` - Population-aware name variants and flags; used by `AMLService.screen_sync` when `use_variants` is on.
- Routes in `app/routes/corridor.py`: `/api/v1/decision` (screens the sender AND the beneficiary; both screenings persisted, migration 0004 adds `beneficiary_screening_id`), `/api/v1/decisions`, `/api/v1/corridors`. Decisions persist in the `decisions` table (migration 0002).
- Tests use `tests/data/corridor_rules/` via `CORRIDOR_RULES_DIR` and `reset_registry()`.

### Database (`app/db/`)
SQLAlchemy 2 models in `models.py`; lazy engine in `database.py` (`DATABASE_URL`, default SQLite under `data/`); Alembic migrations in `migrations/` (`alembic upgrade head`). Tests get a fresh SQLite file via the `db` fixture. `app/monitoring.py` is the re-screen CLI for cron.

### Core (`app/core/`)
- `ocr.py` - Passport MRZ extraction using EasyOCR and mrz library
- `id_ocr.py` - ID card OCR with country-specific rules
- `fuzzy_match.py` - RapidFuzz-based name matching (token_sort_ratio), used by MRZ comparison
- `names.py` - Name normalization (unidecode, titles, particles) and blocking keys (consonant skeleton)
- `dates.py` - DOB parsing for list fields and requests; agreement levels exact/year/mismatch/unknown
- `countries_match.py` - List country names to ISO alpha-2
- `mrz_detect.py` - MRZ region detection from passport images
- `logger.py` - Audit logging to `logs/audit/` as JSON

### Sanctions Data Pipeline
Raw data in `app/data/sanctions/raw/{un,ofac,uk,eu}/` is converted by `scripts/convert_*.py` to normalized CSVs in `normalized/`, then combined into `combined/combined_sanctions_*.csv` (the combiner keeps the newest three). The loader picks the latest combined file by modification time and caches it in memory. `SANCTIONS_DATA_DIR` overrides the data location; tests use a temp dir via the `sanctions_data_dir` fixture.

Sources: UN, OFAC, OFAC_CONS (non-SDN consolidated; `scripts/convert_ofac_cons_to_csv.py` reuses the SDN parser), UK (OFSI ConList), EU, QA_NCTC (Qatar NCTC unified record from the MOI portal JSON; `scripts/convert_qa_nctc_to_csv.py`), INTERNAL (the firm's watchlist; `app/services/lists.py` installs it from an upload and rebuilds the combined file in-app, honouring `SANCTIONS_DATA_DIR`). The screening index also matches identity numbers (`identifier_keys`, `match_type: identifier`). Country risk: `app/data/countries/risk_lists.json` (FATF lists, dated) via `country_risk()`.

Converters: OFAC dates of birth are parsed from the SDN `remarks` column; the EU file carries birth dates on separate rows of an entity group; the UK search-service export has no DOB or nationality (the OFSI ConList.csv does, see the tracker).

Heavy ML imports (EasyOCR, DeepFace, OpenCV) are lazy, inside `KYCService.process_kyc`, so the API and screening endpoints start without them.

## Key Patterns

### Risk Scoring
Risk scores are 0-100. Thresholds: HIGH ≥70, MEDIUM ≥40, LOW <40. `RiskEngine` in `risk_engine.py` is the only place scores are computed: `KYCService` and the combined route call it rather than scoring inline. An AML match whose DOB disagrees with every candidate is demoted.

### Request IDs
All endpoints accept `X-Request-ID` header for tracing. If not provided, generates `req_{uuid8}` format.

### Image Handling
Document and selfie images are passed as base64-encoded strings in request payloads. The `decode_base64_image()` function in `kyc.py` handles data URL prefixes.

### Sanctions Updates
Run `scripts/update_sanctions.py --max-age-hours N` from a scheduler, then `python -m app.monitoring rescreen`. The startup auto-update still exists but is off by default (`SANCTIONS_AUTO_UPDATE_ENABLED=false`). A running API reloads a newer combined file on its own (`SANCTIONS_RELOAD_CHECK_SECONDS`). The loader ignores the `combined_sanctions_latest.csv` symlink and reports the dated file name as the list version.

## Configuration

Environment variables (see `app/config.py`):
- `LOG_LEVEL` - Logging level (default: INFO)
- `SANCTIONS_UPDATE_INTERVAL_DAYS` - Days between updates (default: 7)
- `SANCTIONS_AUTO_UPDATE_ENABLED` - Auto-update on startup (default: false; use the scheduler)
- `DATABASE_URL` - SQLAlchemy URL (default SQLite in `data/`)
- `UI_TENANT` - Tenant the web UI acts for (default `default`)
- `CORRIDOR_RULES_DIR` - Directory of corridor ruleset JSON files (default `premium/corridor_rules`)
- `LIVENESS_PROVIDER` / `LIVENESS_URL` / `LIVENESS_API_KEY` / `LIVENESS_TIMEOUT` - vendor liveness check (default none)

Docs: `docs/pilot/` is the pilot pack; regenerate `docs/api_reference.md` with `python scripts/export_api_reference.py` after route changes.
- `ENVIRONMENT` - development/production
- `DEBUG` - Enable debug mode
- `CORS_ORIGINS` - Comma-separated allowed origins (unset = no CORS headers)
- `API_KEYS` / `API_KEYS_FILE` - API keys as `tenant:key,...` or a JSON file `{tenant: key}`; unset = open API (dev only)
- `SANCTIONS_DATA_DIR` - Location of raw/normalized/combined sanctions data

## Testing Notes

- API tests use the `client` (TestClient) and `sanctions_data_dir` fixtures from `conftest.py`; no running server needed
- `@pytest.mark.slow` tests are skipped unless `--run-slow` is passed (they load ML models or download real data)
- Face matching tests require actual face images; 1x1 test images fail gracefully
- Audit log assertions read `logs/audit/audit.log` relative to the repo root
