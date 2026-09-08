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
FastAPI routers for three main endpoints:
- `/api/v1/kyc/verify` - Document OCR + face matching verification
- `/api/v1/aml/screen` - Sanctions/PEP screening against consolidated lists
- `/api/v1/risk` - Combined risk scoring

### Services (`app/services/`)
- `kyc_service.py` - Orchestrates document validation and face matching
- `aml_service.py` - Sanctions screening with fuzzy matching
- `risk_engine.py` - Unified risk scoring (AML weighted 60%, KYC 40%)
- `sanctions_loader.py` - Loads/caches combined sanctions CSV, auto-finds latest file
- `face_match.py` - DeepFace-based face comparison

### Core (`app/core/`)
- `ocr.py` - Passport MRZ extraction using EasyOCR and mrz library
- `id_ocr.py` - ID card OCR with country-specific rules
- `fuzzy_match.py` - RapidFuzz-based name matching (token_sort_ratio)
- `mrz_detect.py` - MRZ region detection from passport images
- `logger.py` - Audit logging to `logs/audit/` as JSON

### Sanctions Data Pipeline
Raw data in `app/data/sanctions/raw/{un,ofac,uk,eu}/` is converted by `scripts/convert_*.py` to normalized CSVs in `normalized/`, then combined into `combined/combined_sanctions_*.csv` (the combiner keeps the newest three). The loader picks the latest combined file by modification time and caches it in memory. `SANCTIONS_DATA_DIR` overrides the data location; tests use a temp dir via the `sanctions_data_dir` fixture.

Heavy ML imports (EasyOCR, DeepFace, OpenCV) are lazy, inside `KYCService.process_kyc`, so the API and screening endpoints start without them.

## Key Patterns

### Risk Scoring
Risk scores are 0-100. Thresholds: HIGH ≥70, MEDIUM ≥40, LOW <40. The `RiskEngine` class in `risk_engine.py` centralizes all risk calculations.

### Request IDs
All endpoints accept `X-Request-ID` header for tracing. If not provided, generates `req_{uuid8}` format.

### Image Handling
Document and selfie images are passed as base64-encoded strings in request payloads. The `decode_base64_image()` function in `kyc.py` handles data URL prefixes.

### Sanctions Auto-Update
On API startup, `SanctionsLoader.check_if_update_needed()` checks file age against `SANCTIONS_UPDATE_INTERVAL_DAYS` (default: 7). If stale and `SANCTIONS_AUTO_UPDATE_ENABLED=true`, runs `scripts/update_sanctions.py` in background thread.

## Configuration

Environment variables (see `app/config.py`):
- `LOG_LEVEL` - Logging level (default: INFO)
- `SANCTIONS_UPDATE_INTERVAL_DAYS` - Days between updates (default: 7)
- `SANCTIONS_AUTO_UPDATE_ENABLED` - Auto-update on startup (default: true)
- `ENVIRONMENT` - development/production
- `DEBUG` - Enable debug mode
- `CORS_ORIGINS` - Comma-separated allowed origins (unset = no CORS headers)
- `SANCTIONS_DATA_DIR` - Location of raw/normalized/combined sanctions data

## Testing Notes

- API tests use the `client` (TestClient) and `sanctions_data_dir` fixtures from `conftest.py`; no running server needed
- `@pytest.mark.slow` tests are skipped unless `--run-slow` is passed (they load ML models or download real data)
- Face matching tests require actual face images; 1x1 test images fail gracefully
- Audit log assertions read `logs/audit/audit.log` relative to the repo root
