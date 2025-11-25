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
- Face match (selfie vs document)
- Simple KYC risk scoring
- Sanctions screening (UN, OFAC, EU, UK)
- Fuzzy name matching for PEP detection
- Basic FastAPI backend
- Simple JSON audit logs

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

- OCR extraction (EasyOCR/Tesseract)
- Document field parsing
- Face-to-document matching (DeepFace)
- Expiry date and MRZ validation
- Basic identity risk scoring

### AML Core

- **Sanctions Screening**
  - Combined sanctions list from multiple sources (UN, EU, UK)
  - Automatic updates with latest sanctions data
  - Fuzzy name matching with configurable thresholds
  - In-memory caching for better performance
  - Support for custom sanctions lists
  
  Example usage:
  ```python
  from app.services.sanctions_loader import load_sanctions, SanctionsLoader
  
  # Load the latest sanctions data
  df = load_sanctions()  # Uses cached version if available
  
  # Or load a specific file
  # df = load_sanctions("path/to/sanctions.csv")
  
  # Clear the cache if needed
  SanctionsLoader.clear_cache()
  ```

- Basic PEP fuzzy matching
- Basic country risk scoring
- Local watchlist matching

### Developer Tools

- FastAPI-based REST API
- Example endpoints (`/kyc`, `/aml`)
- JSON results
- Local dev environment
- Example tests and sample data

### Transparency

- Simple audit logs
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
git clone https://github.com/yourname/corridorcomply
cd corridorcomply
pip install -r requirements.txt

# For development with additional tools
pip install -r requirements-dev.txt  # If you have a dev requirements file

# Install in development mode
pip install -e .
uvicorn main:app --reload
```

## Contributing

Open-source contributions are welcome for:

- OCR improvements
- Additional sanctions lists
- Performance improvements
- Bug fixes

Premium corridor packs, dashboard, and advanced AML features are closed source and not part of public contributions.

## License

MIT
