# ID Card Processing for Different Countries

## Overview

The system now supports processing ID cards, national IDs, and other non-passport documents from different countries. Unlike passports which use MRZ (Machine Readable Zone), ID cards have varying formats and layouts depending on the country.

## How It Works

### Document Type Detection

The system automatically routes documents to the appropriate OCR method:

1. **Passports** → MRZ extraction (existing functionality)
2. **ID Cards / National IDs / Driving Licenses** → General OCR with country-specific rules

### Processing Flow

```
Document Image
    ↓
Document Type Check
    ↓
┌─────────────────┬─────────────────┐
│   Passport      │   ID Card        │
│   (MRZ)         │   (General OCR) │
└─────────────────┴─────────────────┘
    ↓                    ↓
MRZ Extraction    Country Rules?
    ↓                    ↓
MRZ Parsing    ┌─────────┴─────────┐
    ↓          │                   │
Validation     │                   │
               Yes                 No
               ↓                   ↓
        Country-Specific    Generic Patterns
        Extraction          Extraction
```

## Country-Specific Rules

### Rule File Location

Country-specific rules are stored in:
```
premium/corridor_rules/{country_code}_{document_type}_rules.json
```

Or for general country rules:
```
premium/corridor_rules/{country_code}_rules.json
```

### Rule File Format

```json
{
  "country_code": "US",
  "document_type": "id_card",
  "extraction_patterns": {
    "document_number": "ID[\\s:]+([A-Z0-9]{6,12})",
    "name": "NAME[\\s:]+([A-Z\\s]{3,50})",
    "date_of_birth": "DOB[\\s:]+(\\d{1,2}/\\d{1,2}/\\d{4})",
    "expiry_date": "EXP[\\s:]+(\\d{1,2}/\\d{1,2}/\\d{4})"
  },
  "field_positions": {
    "document_number": {"region": [100, 50, 300, 30]},
    "name": {"region": [100, 100, 300, 30]}
  },
  "validation_rules": {
    "document_number_length": [6, 12],
    "required_fields": ["document_number", "name"]
  }
}
```

### Example: US Driver's License

```json
{
  "country_code": "US",
  "document_type": "driving_license",
  "extraction_patterns": {
    "document_number": "DL[\\s:]+([A-Z0-9]{8,12})",
    "name": "([A-Z]+,\\s+[A-Z]+)",
    "date_of_birth": "(\\d{2}/\\d{2}/\\d{4})",
    "expiry_date": "EXP[\\s:]+(\\d{2}/\\d{2}/\\d{4})"
  }
}
```

## Generic Extraction (Fallback)

When no country-specific rules are available, the system uses generic patterns:

- **Document Number**: Alphanumeric patterns, "ID:", "DOC:" prefixes
- **Date of Birth**: Various date formats (DD/MM/YYYY, YYYY-MM-DD, etc.)
- **Name**: "NAME:", "FULL NAME:" prefixes
- **Expiry Date**: "EXP:", "EXPIRY:" prefixes

## API Usage

The API automatically detects document type and routes accordingly:

```json
{
  "document_data": {
    "document_type": "id_card",
    "issuing_country": "US",
    ...
  },
  "document_image_base64": "..."
}
```

The system will:
1. Detect `document_type` is not "passport"
2. Use ID OCR instead of MRZ extraction
3. Load US-specific rules if available
4. Fall back to generic extraction if no rules found

## Adding New Country Rules

1. Create a rule file: `premium/corridor_rules/{country_code}_{document_type}_rules.json`
2. Define extraction patterns for fields
3. Optionally define field positions for region-based extraction
4. Test with sample documents

### Example: Adding Qatar ID Card Rules

```json
{
  "country_code": "QA",
  "document_type": "id_card",
  "extraction_patterns": {
    "document_number": "رقم[\\s:]+([0-9]{11})",
    "name": "الاسم[\\s:]+([\\u0600-\\u06FF\\s]+)",
    "date_of_birth": "تاريخ[\\s:]+(\\d{4}-\\d{2}-\\d{2})"
  },
  "languages": ["ar", "en"]
}
```

## Supported Document Types

- `passport` - Uses MRZ extraction (existing)
- `id_card` - Uses ID OCR with country rules
- `national_id` - Uses ID OCR with country rules
- `driving_license` - Uses ID OCR with country rules
- `residence_permit` - Uses ID OCR with country rules

## Current Limitations

1. **Language Support**: Currently optimized for English. Multi-language support requires additional OCR language models.
2. **Layout Detection**: Generic extraction may not work well for complex layouts. Country-specific rules are recommended.
3. **Field Validation**: Basic validation is performed, but country-specific validation rules can be added.

## Future Enhancements

- [ ] Multi-language OCR support (Arabic, Chinese, etc.)
- [ ] Layout detection and region-based extraction
- [ ] Machine learning-based field extraction
- [ ] Document template matching
- [ ] Barcode/QR code reading for some ID cards

## Testing

Test ID card processing:

```bash
curl -X POST http://localhost:8000/api/v1/kyc/verify \
  -H "Content-Type: application/json" \
  -d '{
    "document_data": {
      "document_type": "id_card",
      "issuing_country": "US",
      ...
    },
    "document_image_base64": "..."
  }'
```

The response will include:
- `verification_result.document_validation.extracted_data` - Extracted fields
- `verification_result.document_validation.ocr_confidence` - OCR confidence score
- `verification_result.document_validation.details` - Processing details
