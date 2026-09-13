# CorridorComply

Lightweight, corridor-focused KYC and AML automation for emerging-market fintechs.

CorridorComply is a developer-friendly compliance engine that helps fintech startups automate identity verification (KYC) and sanctions screening + risk scoring (AML), with a focus on specific cross-border payment corridors such as Qatar → Philippines, Qatar → Pakistan, UAE → India, and KSA → Bangladesh.

The project uses an open-core model: core KYC/AML features are open source, while advanced corridor logic, reporting, dashboards, and enterprise features are part of a premium edition.

## Project Goal

Build a simple, transparent, Python-based compliance system that fintechs can integrate quickly, starting with basic KYC/AML and expanding into corridor-specific regulatory automation.

## Sanctions Data Management

### Updating Sanctions Data

1. **Automatic Updates**:
   The system automatically looks for the latest combined sanctions file in `app/data/sanctions/combined/` with the pattern `combined_sanctions_*.csv`.

2. **Manual Updates**:
   - Place new sanctions files in the `app/data/sanctions/combined/` directory
   - The system will automatically pick up the most recent file based on modification time
   - Or specify a custom path when loading: `load_sanctions("path/to/your/file.csv")`

### Data Format

The sanctions loader expects CSV files with the following columns (case-sensitive):
- `source` - Source of the sanctions (e.g., "UN", "EU", "UK")
- `source_file` - Original filename
- `record_type` - Type of record (e.g., "individual", "entity")
- `dataid` - Unique identifier from the source
- `name` - Full name of the sanctioned entity (required)
- `aliases` - Alternative names or spellings
- `nationalities` - Nationalities (comma-separated)
- `last_updated` - Last update timestamp
- `processing_date` - Date when the record was processed

### Testing

Run the test suite with:
```bash
pytest tests/test_sanctions_loader.py -v
```

## Project Phases

### Phase 1 – MVP (Open Source)

- Basic document verification (OCR)
  - Passport MRZ extraction and validation
  - ID card OCR with country-specific rules support
  - Support for multiple document types (passport, id_card, national_id, driving_license)
- Face match (selfie vs document)
- Simple KYC risk scoring
- Sanctions screening (UN, OFAC, EU, UK)
- Fuzzy name matching for PEP detection
- Basic FastAPI backend
- Comprehensive JSON audit logs with request payload, risk scores, and match summaries

**Goal:** Create a functional KYC + AML screening pipeline anyone can run locally.

### Phase 2 – Corridor Logic (Premium / Closed Source)

- Country-specific KYC validation
- Corridor-based AML thresholds
- Cross-border risk scoring
- Regulation-specific required fields
- Local ID type recognition (e.g., Qatar ID, Philippine IDs)

**Goal:** Provide the first compliance engine tailored to GCC → South/Southeast Asia financial corridors.

### Phase 3 – Dashboard & Automation (Premium)

- Web dashboard for compliance teams
- Case management system
- Evidence/document viewer
- Risk analytics & summary panels
- Exportable SAR/STR reporting templates
- Multi-tenant SaaS mode

**Goal:** Offer a full operational compliance platform for fintechs.

### Phase 4 – Advanced AML & Growth (Premium)

- Transaction monitoring engine
- Behavioral anomaly detection
- Graph-based risk analysis
- Machine-learning-based AML scoring
- Multi-corridor support
- Enterprise on-premise deployment

**Goal:** Support scaling fintechs and regulated institutions.

## Open Source Features (Free)

### KYC Core

- **Document OCR Processing**
  - Passport MRZ (Machine Readable Zone) extraction and validation
  - ID card OCR with country-specific rules support
  - Support for multiple document types (passport, id_card, national_id, driving_license, residence_permit)
  - Automatic routing based on document type
  - Generic OCR fallback for countries without specific rules
- Document field parsing and validation
- Face-to-document matching (DeepFace)
- Expiry date and MRZ validation
- Basic identity risk scoring
- Graceful handling of small/corrupted images

### AML Core

- **Sanctions Screening**
  - Combined list from UN, OFAC (SDN), UK (OFSI consolidated list), EU and **Qatar's NCTC unified record** (domestic designations with QID and passport numbers), refreshed by `scripts/update_sanctions.py` on a schedule
  - Exact identity-number matching (a QID or passport on a list is a definite hit) alongside names and aliases
  - Names **and listed aliases** are searched; transliteration variants (Mohammed / Muhammad / Mohamed) block together
  - Entity-type aware: screen a person against individuals, a company against entities, or a vessel
  - Date of birth and nationality compared with the list entry (exact / year / mismatch), and a mismatch lowers the score
  - In-memory index: about 1 ms per screen on 30k entries
  - Every response carries the `list_version` it was screened against
  - `POST /api/v1/aml/screen` for one record, `POST /api/v1/aml/screen/batch` for up to 5,000

- **Screening web UI** at `/screen`: upload a CSV or XLSX of customers, review hits, download the report. Built for shadow runs on the customer's own machine; nothing leaves the server.

- **Evidence and monitoring** (see `docs/monitoring.md`)
  - Every screening is stored with the list version (file checksum) it ran against
  - Customers on file are re-screened after each list update; changes raise alerts (`new_hit`, `new_match`, `hit_cleared`) with an optional webhook
  - `/alerts` page and `GET /api/v1/alerts`; acknowledge with a reason
  - `/review` console: queue of decisions awaiting a reviewer, case page with rules, basis and matches, disposition with mandatory reason and name; per-customer evidence bundle export
  - SQLite by default, Postgres via `DATABASE_URL`, migrations with Alembic

- **Corridor decisions** (see `docs/corridor_rules.md`)
  - `POST /api/v1/decision`: screen the customer, check identity-number formats (Qatar ID encodes birth year and nationality; CNIC, Aadhaar, NID, PhilSys), apply the corridor ruleset, return approve / review / reject with every reason and its regulatory basis
  - Population-aware name variants (Filipino middle names and compound surnames, South Asian patronymics and single names) so listed people are not missed
  - Rulesets are JSON validated by schema; `premium/corridor_rules/qa_ph_rules.json` is a **draft** awaiting compliance review

- **API keys**: `python -m app.auth new-key <tenant>` stores a hashed key in the database; `API_KEYS="tenant:key,..."` or `API_KEYS_FILE=keys.json` also work. Without keys the API runs open for local development and warns at startup.

- Basic country risk scoring
- PEP screening is **not** implemented (needs a licensed data source)

### Developer Tools

- FastAPI-based REST API
- Example endpoints (`/kyc`, `/aml`)
- JSON results
- Local dev environment
- Example tests and sample data

### Transparency

- **Comprehensive Audit Logging**
  - JSON logs written to `/logs/audit/` directory
  - Includes request payload (sanitized for large binary data)
  - Includes risk scores and match summaries
  - Timestamped with ISO 8601 format
  - Daily log rotation with 30-day retention
  - Verification script included (`scripts/verify_audit_logging.py`)
- Explainable decision outputs
- Public documentation

## Closed Source / Premium Features

### Corridor Packs

- Qatar → Philippines
- Qatar → Pakistan
- UAE → India
- KSA → Bangladesh
- Additional corridor expansions

**Includes:**
- Corridor-specific KYC rules
- Country-specific AML thresholds
- Required identity fields
- Local beneficiary requirements
- Cross-border risk logic

### Advanced AML

- Behavioral pattern analysis
- Machine learning for anomaly detection
- Graph risk modeling
- Source-of-funds modeling

### Case Management Dashboard

- Case review workflow
- Alerts center
- Document viewer
- Risk heatmaps
- User roles & permissions

### Reporting Tools

- Auto-generated SAR/STR reports
- Regulator-ready export formats
- Compliance summaries

### Enterprise

- On-premise deployment
- High-availability edition
- Advanced audit trail system
- Custom corridor rules
- SLA and compliance support

## Tech Stack

- Python
- FastAPI
- EasyOCR / Tesseract
- DeepFace
- FuzzyWuzzy or RapidFuzz
- SQLite or Postgres
- Docker (later phases)

## Installation (Local)

```bash
git clone https://github.com/Zezoo123/CorridorComply
cd CorridorComply
python -m venv .venv && source .venv/bin/activate

pip install -r requirements.txt        # API + sanctions screening
pip install -r requirements-ml.txt     # optional: document OCR + face matching (large)
pip install -r requirements-dev.txt    # tests

python scripts/update_sanctions.py     # download and combine UN, OFAC, UK, EU lists
uvicorn app.main:app --reload          # http://127.0.0.1:8000/docs and /screen
```

Screen one name:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/aml/screen \
  -H "Content-Type: application/json" -H "X-API-Key: $KEY" \
  -d '{"full_name": "Ayman al-Zawahiri", "dob": "1951-06-19", "nationality": "EG", "entity_type": "person"}'
```

Run the tests (ML-dependent tests are skipped unless you pass `--run-slow`):

```bash
pytest
pytest --run-slow
```

Docker (screening-only by default; add `--build-arg WITH_ML=1` for OCR and face matching):

```bash
docker build -t corridorcomply .
docker run -p 8000:8000 -v $(pwd)/app/data/sanctions:/data/sanctions corridorcomply
```

## Pilot pack

`docs/pilot/` holds what a compliance officer receives: onboarding guide, data-handling note, screening methodology, a draft outsourcing clause (QCB item 6.7), and the generated API reference. Liveness is a vendor interface (`LIVENESS_PROVIDER=http`, `LIVENESS_URL`, `LIVENESS_API_KEY`); with no provider the KYC result says "not checked".

## Contributing

Open-source contributions are welcome for:

- OCR improvements
- Additional sanctions lists
- Performance improvements
- Bug fixes

Premium corridor packs, dashboard, and advanced AML features are closed source and not part of public contributions.

## License

MIT for everything outside `premium/`. The `premium/` directory is proprietary; see `premium/LICENSE`.
