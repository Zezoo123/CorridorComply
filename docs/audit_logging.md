# Audit Logging Implementation

## Overview

This document describes the audit logging implementation for the CorridorComply API, addressing GitHub issue #11.

## Requirements

The audit logging system must:
1. Write JSON logs to `/logs` folder
2. Include request payload
3. Include risk score
4. Include match summary
5. Include timestamp

## Implementation

### Log Location

Audit logs are written to: `logs/audit/audit.log`

The logs are:
- Rotated daily at midnight
- Kept for 30 days
- Formatted as JSON (one entry per line)

### Log Format

Each audit log entry contains:

```json
{
  "timestamp": "2025-01-16T10:30:45.123456",
  "level": "INFO",
  "logger": "audit",
  "message": "Audit event",
  "event_type": "kyc_verification|aml_screening|combined_risk_assessment",
  "request_id": "req_abc123",
  "client_ip": "127.0.0.1",
  "user_agent": "Mozilla/5.0...",
  "method": "POST",
  "url": "http://localhost:8000/api/v1/kyc/verify",
  "request_payload": {
    "document_data": {...},
    "document_image_base64": "<base64_image_data: 12345 bytes>",
    "selfie_image_base64": "<base64_image_data: 12345 bytes>"
  },
  "status": "success|error",
  "risk_score": 45.5,
  "risk_level": "medium",
  "verification_result": {...},
  "document_verified": true,
  "face_match": true,
  ...
}
```

### Fields Included

#### Required Fields (per GitHub issue #11)

1. **Request Payload** ✅
   - Full request payload is included in `request_payload` field
   - Large binary data (base64 images) are sanitized to show size only
   - All other payload fields are included

2. **Risk Score** ✅
   - Included in `risk_score` field
   - For combined risk: `combined_risk_score`
   - For AML: `risk_score`
   - For KYC: `risk_score`

3. **Match Summary** ✅
   - For KYC: `verification_result`, `document_verified`, `face_match`
   - For AML: `sanctions_match`, `pep_match`, `match_count`, `matches`
   - For Combined Risk: `aml_sanctions_match`, `kyc_document_verified`, `kyc_face_match`

4. **Timestamp** ✅
   - Included in `timestamp` field
   - Format: ISO 8601 (UTC)

### Endpoints with Audit Logging

All main API endpoints have audit logging:

1. **POST /api/v1/kyc/verify**
   - Event type: `kyc_verification`
   - Logs: request payload, risk score, verification results, face match status

2. **POST /api/v1/aml/screen**
   - Event type: `aml_screening`
   - Logs: request payload, risk score, sanctions/PEP matches

3. **POST /api/v1/risk/combined**
   - Event type: `combined_risk_assessment`
   - Logs: request payload, combined risk score, AML and KYC details

### Request Payload Sanitization

The `sanitize_request_payload()` function:
- Removes large base64 image data (replaces with size indicator)
- Truncates very long strings (>1000 chars)
- Preserves all other payload fields
- Handles nested dictionaries and lists

### Testing

Run the audit logging tests:

```bash
pytest tests/test_audit_logging.py -v
```

The test suite verifies:
- All endpoints generate audit logs
- Required fields are present (request_payload, risk_score, match summary, timestamp)
- Timestamp format is correct
- Logs are written to the correct location

### Example Audit Log Entry

```json
{
  "timestamp": "2025-01-16T10:30:45.123456",
  "level": "INFO",
  "logger": "audit",
  "message": "Audit event",
  "event_type": "kyc_verification",
  "request_id": "req_abc123",
  "client_ip": "127.0.0.1",
  "method": "POST",
  "url": "http://localhost:8000/api/v1/kyc/verify",
  "request_payload": {
    "document_data": {
      "document_type": "passport",
      "document_number": "TEST123456",
      "first_name": "John",
      "last_name": "Doe",
      "date_of_birth": "1990-01-01",
      "nationality": "US",
      "issuing_country": "US",
      "expiry_date": "2030-01-01"
    },
    "document_image_base64": "<base64_image_data: 12345 bytes>",
    "selfie_image_base64": "<base64_image_data: 12345 bytes>"
  },
  "status": "success",
  "risk_score": 45.5,
  "risk_level": "medium",
  "verification_result": {
    "document_verified": true,
    "face_match": true,
    "match_score": 0.95
  },
  "document_verified": true,
  "face_match": true,
  "document_type": "passport",
  "nationality": "US"
}
```

## Files Modified

1. `app/core/logger.py` - Enhanced `log_audit_event()` to accept and log request payloads
2. `app/routes/kyc.py` - Updated to pass request payload to audit logging
3. `app/routes/aml.py` - Updated to pass request payload to audit logging
4. `app/routes/risk.py` - Updated to pass request payload to audit logging
5. `tests/test_audit_logging.py` - Comprehensive test suite for audit logging

## Status

✅ All requirements from GitHub issue #11 are implemented and tested.

