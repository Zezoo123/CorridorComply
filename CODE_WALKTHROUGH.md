# CorridorComply Code Walkthrough

This document explains every part of the codebase step by step.

---

## 📁 Project Structure Overview

```
app/
├── main.py              # FastAPI application entry point
├── config.py            # Configuration settings
├── core/                # Core utilities and helpers
├── models/              # Pydantic data models (request/response schemas)
├── routes/              # API endpoint handlers
├── services/            # Business logic layer
├── data/                # Data files (sanctions lists, sample docs)
└── db/                  # Database models (not yet implemented)
```

---

## 🚀 1. Application Entry Point

### `app/main.py`

**Purpose:** Creates and configures the FastAPI application.

```python
def create_app() -> FastAPI:
    app = FastAPI(
        title="CorridorComply",
        version="0.1.0",
        description="Corridor-focused KYC & AML API (MVP)",
    )
```

**What it does:**
- Creates a FastAPI instance with metadata
- Registers all route handlers (health, kyc, aml, risk)
- Each router gets a URL prefix (`/kyc`, `/aml`, `/risk`)
- Tags organize endpoints in Swagger UI

**Why this structure:**
- `create_app()` function allows testing with different configurations
- Separates app creation from running (good for testing)
- Clean separation of concerns

---

## ⚙️ 2. Configuration

### `app/config.py`

**Purpose:** Centralized configuration settings.

```python
AUDIT_LOG_DIR = "./logs/audit"
CORS_ORIGINS: List[str] = ["*"]
```

**What it does:**
- Stores application-wide settings
- Currently simple, but can be extended with environment variables
- Used by logger and other modules

**Future:** Can be enhanced with `pydantic-settings` for environment-based config.

---

## 🛠️ 3. Core Utilities (`app/core/`)

### `app/core/utils.py`

**Purpose:** Shared utility functions.

```python
def generate_request_id() -> str:
    return str(uuid.uuid4())
```

**What it does:**
- Generates unique UUIDs for each API request
- Used by all routes to track requests
- Returns standard UUID format (e.g., `550e8400-e29b-41d4-a716-446655440000`)

**Why UUID:**
- Globally unique
- No collisions
- Standard format for distributed systems

---

### `app/core/ocr.py`

**Purpose:** Document OCR validation with support for multiple document types.

**Key Functions:**

**`validate_document_ocr()`:**
```python
def validate_document_ocr(
    document_image: Image.Image,
    document_type: Optional[str] = None,
    country_code: Optional[str] = None
) -> Dict[str, Any]:
```

**What it does:**
1. **Routes based on document type:**
   - Passports → MRZ extraction and parsing
   - ID cards, National IDs, Driving Licenses → ID OCR with country rules
2. **For passports:**
   - Extracts MRZ region from document
   - Uses EasyOCR to read MRZ text
   - Parses MRZ using TD3 format checker
   - Validates checksums and expiry dates
3. **For ID cards:**
   - Routes to `id_ocr.validate_id_ocr()`
   - Uses country-specific rules if available
   - Falls back to generic OCR patterns

**Why this approach:**
- Different document types require different processing
- Passports have standardized MRZ format
- ID cards vary by country and need flexible extraction
- Allows adding new document types easily

---

### `app/core/id_ocr.py`

**Purpose:** ID card OCR processing for non-passport documents.

**Key Functions:**

**`validate_id_ocr()`:**
```python
def validate_id_ocr(
    document_image: Image.Image,
    country_code: str,
    document_type: str
) -> Dict[str, Any]:
```

**What it does:**
1. **Extracts text** from entire document using EasyOCR
2. **Loads country-specific rules** from `premium/corridor_rules/` if available
3. **Extracts structured fields:**
   - Document number
   - Name
   - Date of birth
   - Expiry date
   - Address (if available)
4. **Uses extraction patterns:**
   - Country-specific regex patterns from rules files
   - Generic patterns as fallback
5. **Validates extracted data** and returns results

**Country Rules:**
- Rules stored in JSON format: `{country_code}_{document_type}_rules.json`
- Contains regex patterns for field extraction
- Can define field positions for region-based extraction
- Supports multiple languages

**Generic Extraction (Fallback):**
- Document number: Alphanumeric patterns, "ID:", "DOC:" prefixes
- Dates: Various formats (DD/MM/YYYY, YYYY-MM-DD, etc.)
- Names: "NAME:", "FULL NAME:" prefixes

**Why this structure:**
- Flexible for different countries
- Easy to add new country rules
- Falls back gracefully when no rules available
- Supports both structured and unstructured ID cards

---

### `app/core/logger.py`

**Purpose:** Audit logging system with comprehensive request tracking.

```python
def log_audit_event(
    event_type: str,
    data: Dict[str, Any],
    request: Any = None,
    request_payload: Optional[Any] = None
):
```

**What it does:**
1. **Creates log directory** if it doesn't exist (`logs/audit/`)
2. **Sanitizes request payload** (removes large binary data like base64 images)
3. **Builds log entry** with:
   - Timestamp (ISO 8601 format)
   - Event type (kyc_verification, aml_screening, combined_risk_assessment)
   - Request ID (from X-Request-ID header)
   - Request payload (sanitized)
   - Risk score and risk level
   - Match summary (verification results, sanctions matches, etc.)
   - Request metadata (client IP, user agent, method, URL)
4. **Writes to daily log file** (`logs/audit/audit.log`) with daily rotation
5. **Keeps logs for 30 days** (configurable)

**Why JSON format:**
- Structured data for easy parsing
- One JSON object per line (JSONL format)
- Can append without reading entire file
- Good for log aggregation tools (ELK, Splunk, etc.)
- Easy to query and analyze

**Request Payload Sanitization:**
- Large base64 image data is replaced with size indicators
- Long strings are truncated (>1000 chars)
- Preserves all other payload fields
- Handles nested dictionaries and lists

**Example log entry:**
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "INFO",
  "logger": "audit",
  "message": "Audit event",
  "event_type": "kyc_verification",
  "request_id": "test_kyc_123",
  "client_ip": "127.0.0.1",
  "method": "POST",
  "url": "http://localhost:8000/api/v1/kyc/verify",
  "request_payload": {
    "document_data": {
      "document_type": "passport",
      "document_number": "P1234567",
      "first_name": "John",
      "last_name": "Doe"
    },
    "document_image_base64": "<base64_image_data: 12345 bytes>",
    "selfie_image_base64": "<base64_image_data: 12345 bytes>"
  },
  "status": "success",
  "risk_score": 45.5,
  "risk_level": "medium",
  "verification_result": {
    "document_verified": true,
    "face_match": true
  }
}
```

**Safe Log Rotation:**
- Custom `SafeTimedRotatingFileHandler` ensures directory exists before rotation
- Prevents crashes during log rotation
- Handles edge cases gracefully

---

### `app/core/fuzzy_match.py`

**Purpose:** Fuzzy string matching for name comparison.

```python
def fuzzy_name_match(name1: str, name2: str) -> int:
    score = fuzz.token_sort_ratio(name1_normalized, name2_normalized)
    return score
```

**What it does:**
- Compares two names and returns similarity score (0-100)
- Uses `token_sort_ratio` from RapidFuzz library
- Handles word order differences ("Ahmed Ali" vs "Ali Ahmed")
- Normalizes input (lowercase, strip whitespace)

**Why fuzzy matching:**
- Names can have typos, different spellings, or word order
- Sanctions lists may have slight variations
- Returns confidence score, not just exact match

**Example:**
- "Ahmed Ali" vs "AHMED ALI" → 100 (exact match after normalization)
- "Ahmed Ali" vs "Ahmed Al" → ~90 (close match)
- "Ahmed Ali" vs "John Doe" → ~0 (no match)

---

### `app/core/validation.py`

**Purpose:** Validates KYC input fields.

**Key Components:**

#### 1. **Constants:**
```python
VALID_DOCUMENT_TYPES = {"passport", "id_card", ...}
VALID_NATIONALITIES = {"QA", "PH", "US", ...}
```
- Defines allowed values for document types and nationalities

#### 2. **FieldValidator Class:**

**`validate_date()`:**
- Checks format (YYYY-MM-DD)
- Validates date is not in future
- Checks date is not too old (before 1900)
- Returns parsed date object

**`validate_document_type()`:**
- Checks if document type is in allowed list
- Returns clear error message if invalid

**`validate_nationality()`:**
- Validates ISO country code format (2 uppercase letters)
- Checks against known valid codes
- Flexible to accept any valid ISO code

**`validate_document_number()`:**
- Checks length (3-50 characters)
- Validates characters (alphanumeric + separators)
- Can do type-specific validation (e.g., passport starts with letter)

**`validate_full_name()`:**
- Checks length (2-100 characters)
- Validates characters (letters, spaces, hyphens, apostrophes)
- Requires first and last name (must contain space)

**`validate_kyc_fields()`:**
- **Main validation function** that validates all fields
- Returns comprehensive result:
  - `is_valid`: Overall validation status
  - `missing_fields`: List of missing required fields
  - `validation_errors`: List of validation error messages
  - `data_quality_issues`: Warnings (e.g., unusual age)

**Why this approach:**
- Centralized validation logic
- Reusable across different parts of application
- Returns detailed results for better error messages
- Separates validation from business logic

---

## 📋 4. Models (`app/models/`)

Models define the structure of request and response data using Pydantic.

### `app/models/risk.py`

**Purpose:** Defines risk-related data structures.

#### **RiskLevel Enum:**
```python
class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```
- Simple enum for risk levels
- Used across all risk assessments

#### **IdentityData Base Model:**
```python
class IdentityData(BaseModel):
    full_name: str
    dob: str
    nationality: str
```
- **Base class** for shared identity fields
- Used by both AML and KYC
- Reduces code duplication

#### **AMLInputData:**
```python
class AMLInputData(IdentityData):
    pass  # Just uses identity fields
```
- Extends IdentityData
- AML only needs identity info for screening

#### **KYCInputData:**
```python
class KYCInputData(IdentityData):
    document_type: str
    document_number: str
    face_match_score: Optional[float]
    # ... more document-specific fields
```
- Extends IdentityData
- Adds document-specific fields
- Optional fields for future features (OCR, face matching)

#### **PreCalculatedRisk:**
```python
class PreCalculatedRisk(BaseModel):
    risk_score: int
    risk_level: RiskLevel
    risk_factors: List[Dict[str, Any]]
```
- Allows passing pre-calculated risk scores
- Used in `/risk/combined` endpoint

#### **CombinedRiskRequest:**
```python
class CombinedRiskRequest(BaseModel):
    aml_data: Optional[AMLInputData]
    kyc_data: Optional[KYCInputData]
    aml_risk: Optional[PreCalculatedRisk]
    kyc_risk: Optional[PreCalculatedRisk]
```
- Flexible request model
- Can provide raw data OR pre-calculated risks
- Allows mixing both

#### **CombinedRiskResponse:**
```python
class CombinedRiskResponse(BaseModel):
    request_id: str
    combined_risk_score: int
    combined_risk_level: RiskLevel
    aml_risk_score: Optional[int]
    kyc_risk_score: Optional[int]
    # ... more fields
```
- Comprehensive response with all risk data
- Includes individual and combined scores

---

### `app/models/kyc.py`

**Purpose:** KYC-specific request/response models.

#### **KYCRequest:**
```python
class KYCRequest(BaseModel):
    full_name: str
    dob: str
    nationality: str
    document_type: str
    document_number: str
```
- Input model for `/kyc/verify` endpoint
- All fields required
- Future: will add image fields

#### **KYCResponse:**
```python
class KYCResponse(BaseModel):
    request_id: str
    status: str  # "pass" | "fail" | "review"
    risk_score: int
    risk_level: RiskLevel
    details: List[str]
```
- Output model for KYC verification
- Includes request_id for tracking
- Status determined by risk level
- Details provide human-readable explanations

---

### `app/models/aml.py`

**Purpose:** AML-specific request/response models.

#### **AMLScreenRequest:**
```python
class AMLScreenRequest(BaseModel):
    full_name: str
    dob: str
    nationality: str
```
- Simple input: just identity fields
- AML screening doesn't need document info

#### **AMLScreenResponse:**
```python
class AMLScreenResponse(BaseModel):
    request_id: str
    sanctions_match: bool
    pep_match: bool
    risk_score: int
    risk_level: RiskLevel
    details: List[str]
    matches: List[MatchResult]
```
- Comprehensive AML screening result
- Includes match details (which sanctions lists matched)

#### **MatchResult:**
```python
class MatchResult(BaseModel):
    sanctioned_name: str
    source: str  # Which sanctions list
    similarity: int  # 0-100
    confidence: str  # "high" | "medium" | "low"
    dob_match: Optional[bool]
    country_match: Optional[bool]
```
- Details about each match found
- Helps explain why risk score is what it is

---

## 🔧 5. Services (`app/services/`)

Services contain the business logic - the "what" the application does.

### `app/services/sanctions_loader.py`

**Purpose:** Loads and caches sanctions lists from CSV files.

```python
class SanctionsLoader:
    _cache = None  # Class-level cache
    
    @classmethod
    def load_sanctions(cls):
        if cls._cache is not None:
            return cls._cache  # Return cached data
```

**What it does:**
1. **Scans** `app/data/sanctions/` for CSV files
2. **Reads** each CSV file with pandas
3. **Adds** `source` column (filename without extension)
4. **Combines** all lists into one DataFrame
5. **Caches** result (only loads once)
6. **Handles** empty files gracefully

**Why caching:**
- CSV files don't change during runtime
- Avoids re-reading files on every request
- Much faster for repeated requests

**Error handling:**
- Skips empty files
- Handles missing files
- Returns empty DataFrame if no data

---

### `app/services/aml_service.py`

**Purpose:** Performs AML (Anti-Money Laundering) screening.

```python
@staticmethod
def screen(request_id: str, full_name: str, dob: str, nationality: str):
```

**What it does:**
1. **Loads sanctions lists** (via SanctionsLoader)
2. **Fuzzy matches** name against all sanctions entries
3. **Checks DOB and country** if available in sanctions data
4. **Calculates risk score** using RiskEngine
5. **Logs audit event** with request_id
6. **Returns** comprehensive result

**Fuzzy matching logic:**
```python
score = fuzzy_name_match(full_name, row["name"])
if score >= SIMILARITY_THRESHOLD:  # 85%
    # It's a potential match
```

**Risk calculation:**
- Uses `RiskEngine.calculate_aml_risk_score()`
- Considers:
  - Number of matches
  - Match confidence (similarity score)
  - DOB/country matches
  - Multiple sanctions lists

**Why this structure:**
- Separates business logic from API layer
- Reusable (can be called from routes or other services)
- Testable independently

---

### `app/services/kyc_service.py`

**Purpose:** Performs KYC (Know Your Customer) verification with document OCR and face matching.

```python
@classmethod
async def process_kyc(
    cls,
    request_id: str,
    full_name: str,
    dob: str,
    nationality: str,
    document_type: str,
    document_number: str,
    document_image: Image.Image,
    selfie_image: Image.Image,
    expiry_date: Optional[str] = None,
    issuing_country: Optional[str] = None
):
```

**What it does:**
1. **Processes document and selfie images** (calculates size, extracts metadata)
2. **Performs document OCR validation** using `validate_document_ocr()`
   - For passports: Extracts and parses MRZ (Machine Readable Zone)
   - For ID cards: Uses general OCR with country-specific rules
   - Automatically routes based on document type
3. **Compares extracted data** with request data (MRZ vs provided fields)
4. **Performs face matching** between document photo and selfie
5. **Calculates risk score** using RiskEngine
6. **Determines status** (pass/fail/review) based on risk level
7. **Builds detailed response** with validation results
8. **Logs audit event** with request_id and all relevant data

**Document OCR Integration:**
```python
document_validation = validate_document_ocr(
    document_image,
    document_type=document_type,
    country_code=issuing_country or nationality
)
# Automatically routes to:
# - MRZ extraction for passports
# - ID OCR for id_card, national_id, driving_license, etc.
```

**Image Processing:**
- Handles small/corrupted images gracefully
- Estimates size from dimensions if image can't be saved
- Converts images to proper format for face matching
- Handles different image channel formats (RGB, grayscale, etc.)

**Status determination:**
- HIGH risk → "fail"
- MEDIUM risk → "review"
- LOW risk → "pass"

**Why comprehensive details:**
- Helps users understand why verification passed/failed
- Useful for compliance teams
- Makes debugging easier
- Includes OCR confidence scores and extraction details

---

### `app/services/risk_engine.py`

**Purpose:** Unified risk calculation engine for both AML and KYC.

**Key Components:**

#### **RiskFactorType Enum:**
```python
class RiskFactorType(str, Enum):
    AML_SANCTIONS = "aml_sanctions"
    AML_PEP = "aml_pep"
    KYC_DOCUMENT = "kyc_document"
    KYC_FACE_MATCH = "kyc_face_match"
    # ... more types
```
- Categorizes different types of risk factors
- Used for tracking and reporting

#### **Risk Level Calculation:**
```python
@classmethod
def calculate_risk_level(cls, risk_score: int) -> RiskLevel:
    if risk_score >= 70:
        return RiskLevel.HIGH
    elif risk_score >= 40:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW
```
- Converts numeric score to risk level
- Consistent thresholds across all checks

#### **AML Risk Calculation:**
```python
def calculate_aml_risk_score(
    matches: List[Dict],
    has_sanctions_match: bool,
    has_pep_match: bool
):
```

**Scoring logic:**
- Sanctions match: +50 base
- High confidence match: +30 additional
- Medium confidence: +15
- DOB match: +10
- Country match: +5
- Multiple matches: +5 per match (max +20)
- PEP match (if no sanctions): +30

**Why weighted scoring:**
- Sanctions matches are highest risk
- Confidence matters (exact match vs fuzzy)
- Multiple indicators increase risk

#### **KYC Risk Calculation:**
```python
def calculate_kyc_risk_score(
    document_valid: bool,
    face_match_score: Optional[float],
    # ... more parameters
):
```

**Scoring logic:**
- Invalid document: +40
- Face mismatch: +35
- Low face match confidence: +20
- Expired document: +30
- Poor OCR quality: +25
- Missing fields: +5 per field (max +20)

**Why this structure:**
- Each risk factor has clear weight
- Additive scoring (multiple issues compound)
- Capped at 100

#### **Combined Risk Calculation:**
```python
def calculate_combined_risk_score(
    aml_risk_data: Optional[Dict],
    kyc_risk_data: Optional[Dict]
):
```

**Weighting:**
- AML: 60% weight (more important)
- KYC: 40% weight
- If only one provided, uses it directly

**Why weighted combination:**
- AML risks (sanctions) are more critical
- KYC risks (document issues) are important but secondary
- Allows flexible risk assessment

---

## 🛣️ 6. Routes (`app/routes/`)

Routes handle HTTP requests and responses - the API layer.

### `app/routes/health.py`

**Purpose:** Health check endpoint.

```python
@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

**What it does:**
- Simple endpoint to check if API is running
- Used by monitoring tools, load balancers
- No authentication needed

---

### `app/routes/kyc.py`

**Purpose:** KYC verification endpoint.

```python
@router.post("/verify", response_model=KYCResponse)
async def verify_kyc(payload: KYCRequest):
    request_id = generate_request_id()
    result = KYCService.verify(request_id=request_id, ...)
    return KYCResponse(**result)
```

**What it does:**
1. **Receives** KYCRequest from client
2. **Generates** unique request_id
3. **Calls** KYCService.verify() with all data
4. **Returns** KYCResponse (automatically validated by Pydantic)

**Why this structure:**
- Route handles HTTP concerns (request/response)
- Service handles business logic
- Clean separation of concerns

---

### `app/routes/aml.py`

**Purpose:** AML screening endpoint.

```python
@router.post("/screen", response_model=AMLScreenResponse)
async def screen_aml(payload: AMLScreenRequest):
    request_id = generate_request_id()
    result = AMLService.screen(request_id=request_id, ...)
    return AMLScreenResponse(**result)
```

**Same pattern as KYC route:**
- Generate request_id
- Call service
- Return response

---

### `app/routes/risk.py`

**Purpose:** Combined risk assessment endpoint.

**This is more complex because it:**
1. Accepts multiple input types (raw data OR pre-calculated risks)
2. May call both AML and KYC services
3. Combines results

```python
@router.post("/combined", response_model=CombinedRiskResponse)
async def get_combined_risk(payload: CombinedRiskRequest):
    request_id = generate_request_id()
    
    # Process AML risk
    if payload.aml_risk:
        # Use pre-calculated
    elif payload.aml_data:
        # Calculate from raw data
        aml_result = AMLService.screen(...)
    
    # Process KYC risk (similar logic)
    
    # Calculate combined risk
    combined_result = RiskEngine.calculate_combined_risk_score(...)
    
    # Log and return
```

**Why this flexibility:**
- Clients may have already run AML/KYC separately
- Can reuse those results
- Or provide raw data for fresh calculation
- Or mix both approaches

---

## 🔄 Data Flow Example

Let's trace a KYC verification request:

1. **Client sends POST** to `/kyc/verify` with JSON body
2. **FastAPI validates** request against `KYCRequest` model
3. **Route handler** (`kyc.py`) receives validated data
4. **Route generates** request_id using `generate_request_id()`
5. **Route calls** `KYCService.verify()` with request_id and data
6. **Service validates** fields using `FieldValidator`
7. **Service calculates** risk using `RiskEngine.calculate_kyc_risk_score()`
8. **Service logs** audit event using `log_audit_event()`
9. **Service returns** result dictionary
10. **Route converts** to `KYCResponse` model (Pydantic validates)
11. **FastAPI serializes** to JSON and sends HTTP response

**At each step:**
- Request ID is passed along
- Data is validated
- Errors are handled gracefully
- Everything is logged

---

## 🎯 Key Design Patterns

### 1. **Separation of Concerns**
- Routes: HTTP handling
- Services: Business logic
- Models: Data structure
- Core: Utilities

### 2. **Dependency Injection**
- Services don't create dependencies
- Passed in as parameters
- Makes testing easier

### 3. **Single Responsibility**
- Each class/function does one thing
- Easy to understand and modify

### 4. **DRY (Don't Repeat Yourself)**
- IdentityData base class
- Reusable validation functions
- Shared risk engine

### 5. **Fail Gracefully**
- Validation errors don't crash
- Returns detailed error messages
- Logs everything for debugging

---

## 📝 Summary

**Core:** Utilities (UUID generation, logging, validation, fuzzy matching)
**Models:** Data structures (request/response schemas)
**Services:** Business logic (AML screening, KYC verification, risk calculation)
**Routes:** API endpoints (HTTP request/response handling)

**Flow:** Client → Route → Service → Core Utilities → Response

**Key Features:**
- Request IDs for tracking
- Comprehensive validation
- Detailed risk scoring
- **Comprehensive audit logging** with request payload, risk scores, and match summaries
- **Multi-document type support** (passports, ID cards, national IDs, driving licenses)
- **Country-specific OCR rules** for ID card processing
- **Graceful image processing** for small/corrupted images
- Flexible API design

**Recent Enhancements:**
- **Audit Logging:** All API endpoints now log comprehensive audit events with request payloads, risk scores, match summaries, and timestamps
- **ID Card Processing:** Support for ID cards from different countries with country-specific extraction rules
- **Image Processing:** Improved handling of small test images and corrupted image data
- **Face Matching:** Enhanced to handle different image channel formats (RGB, grayscale, 2-channel, etc.)

This architecture makes the code:
- **Testable:** Each layer can be tested independently
- **Maintainable:** Clear separation of concerns
- **Extensible:** Easy to add new features (document types, country rules, etc.)
- **Debuggable:** Request IDs and comprehensive logging help trace issues
- **Compliant:** Full audit trail for regulatory requirements

