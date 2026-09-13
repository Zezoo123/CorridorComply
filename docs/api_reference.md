# API reference

Generated from the OpenAPI schema of CorridorComply 0.2.0. Interactive docs at `/docs`; raw schema at `/openapi.json`.

All `/api/v1/*` routes require `X-API-Key` when keys are configured. Every request may carry `X-Request-ID`; the response echoes it and every audit event and stored record cites it.

## KYC

### `POST /api/v1/kyc/verify`

Process KYC verification with document and selfie images.

Returns verification results including risk score and level.

Request body: `KYCRequest`

Response: `KYCResponse`

## AML

### `POST /api/v1/aml/screen`

Screen a person, company or vessel against the combined sanctions lists
(UN, OFAC, UK, EU). Names and listed aliases are both searched; DOB and
nationality, when supplied, are compared with the list entry.

Request body: `AMLScreenRequest`

Response: `AMLScreenResponse`

### `POST /api/v1/aml/screen/batch`

Screen up to 5,000 records in one call. Each result carries the caller's reference.

Request body: `AMLBatchRequest`

Response: `AMLBatchResponse`

## Risk

### `POST /api/v1/risk/combined`

Calculate combined risk score from both AML and KYC checks.

You can provide:
- Raw data (aml_data and/or kyc_data) - will compute risk scores
- Pre-calculated risk scores (aml_risk and/or kyc_risk) - will use directly
- Mix of both

The combined risk score weights AML at 60% and KYC at 40% when both are provided.

Request body: `CombinedRiskRequest`

Response: `CombinedRiskResponse`

## Customers & Monitoring

### `POST /api/v1/customers`

Add or update customers (by your reference). Screens them immediately unless screen_now is false.

Request body: `CustomerBatchIn`

### `GET /api/v1/customers`

List Customers

Parameters:

- `monitored` (query): 

### `DELETE /api/v1/customers/{reference}`

Stop monitoring a customer. The screening history is kept.

Parameters:

- `reference` (path, required): string

### `POST /api/v1/monitoring/rescreen`

Re-screen every monitored customer against the current list and raise alerts for changes.

Skips customers already screened against the current list version unless force=true.

Parameters:

- `force` (query): boolean

### `GET /api/v1/alerts`

List Alerts

Parameters:

- `status` (query): 

### `POST /api/v1/alerts/{alert_id}/ack`

Ack Alert

Parameters:

- `alert_id` (path, required): integer

Request body: `AlertAck`

### `GET /api/v1/screenings`

Screening history for this tenant, newest first.

Parameters:

- `limit` (query): integer

### `GET /api/v1/screenings/{screening_id}`

Get Screening

Parameters:

- `screening_id` (path, required): integer

### `GET /api/v1/tenant`

Tenant Settings

### `PUT /api/v1/tenant`

Update Tenant

Request body: `TenantSettings`

### `GET /api/v1/lists/current`

Identity of the sanctions list currently loaded.

## Corridor decisions

### `GET /api/v1/corridors`

Corridor rulesets loaded from the rules directory, with their review status.

### `GET /api/v1/corridors/fields`

The fields a rule condition may reference, with their meaning.

### `GET /api/v1/corridors/{corridor_id}`

Get Corridor

Parameters:

- `corridor_id` (path, required): string

### `POST /api/v1/decision`

Screen the customer, apply the corridor's rules, store the decision.

The outcome is the most severe of all rules that fired; every reason is
returned and stored so a reviewer sees the whole picture.

Request body: `DecisionRequest`

Response: `DecisionResponse`

### `GET /api/v1/decisions`

List Decisions

Parameters:

- `outcome` (query): 
- `pending` (query): true: awaiting a reviewer; false: dispositioned
- `corridor` (query): 
- `limit` (query): integer

### `POST /api/v1/decisions/{decision_id}/disposition`

The reviewer's call on a decision: approved, rejected or escalated, with a mandatory reason and name.

Parameters:

- `decision_id` (path, required): integer

Request body: `DispositionIn`

### `GET /api/v1/customers/{reference}/evidence`

Everything on file for one customer: profile, screenings, decisions with dispositions, alerts, list versions.

Parameters:

- `reference` (path, required): string

### `GET /api/v1/decisions/{decision_id}`

Get Decision

Parameters:

- `decision_id` (path, required): integer

## Screening UI

### `GET /screen`

Screen Form

### `POST /screen`

Screen Upload

### `GET /screen/{job_id}`

Screen Report

Parameters:

- `job_id` (path, required): string

### `GET /alerts`

Alerts Page

Parameters:

- `show` (query): string

### `POST /alerts/rescreen`

Alerts Rescreen

### `POST /alerts/{alert_id}/ack`

Alerts Ack

Parameters:

- `alert_id` (path, required): integer

### `GET /screen/{job_id}/report.csv`

Screen Report Csv

Parameters:

- `job_id` (path, required): string

### `GET /screen/sample/customers.csv`

Sample Csv

### `GET /review`

Review Queue

Parameters:

- `show` (query): string

### `GET /review/{decision_id}`

Review Case

Parameters:

- `decision_id` (path, required): integer

### `POST /review/{decision_id}`

Review Disposition

Parameters:

- `decision_id` (path, required): integer

## Other

### `GET /`

Root endpoint that returns a welcome message

### `GET /health`

Health check endpoint

## Schemas

### `AMLBatchItem`

- `full_name` (required): string
- `dob`: string/null — YYYY-MM-DD
- `nationality`: string/null — ISO code or country name
- `entity_type`: string — What is being screened
- `id_numbers`: array/null — Identity numbers (QID, passport) to match exactly against list identifiers
- `reference`: string/null — Caller's own identifier for this row

### `AMLBatchRequest`

- `items` (required): array

### `AMLBatchResponse`

- `request_id` (required): string
- `list_version`: string/null
- `total` (required): integer
- `with_matches` (required): integer
- `results` (required): array

### `AMLBatchResult`

- `request_id` (required): string
- `sanctions_match`: boolean
- `pep_match`: boolean
- `risk_score` (required): integer
- `risk_level`: 
- `details`: array
- `matches`: array
- `list_version`: string/null — Identifier of the list file screened against
- `screening_id`: integer/null — Persistent evidence record id
- `name_flags`: array — single_name, patronymic, compound_surname, suffix
- `screened_variants`: array — Name forms actually screened
- `reference`: string/null
- `full_name` (required): string

### `AMLScreenRequest`

- `full_name` (required): string
- `dob`: string/null — YYYY-MM-DD
- `nationality`: string/null — ISO code or country name
- `entity_type`: string — What is being screened
- `id_numbers`: array/null — Identity numbers (QID, passport) to match exactly against list identifiers

### `AMLScreenResponse`

- `request_id` (required): string
- `sanctions_match`: boolean
- `pep_match`: boolean
- `risk_score` (required): integer
- `risk_level`: 
- `details`: array
- `matches`: array
- `list_version`: string/null — Identifier of the list file screened against
- `screening_id`: integer/null — Persistent evidence record id
- `name_flags`: array — single_name, patronymic, compound_surname, suffix
- `screened_variants`: array — Name forms actually screened

### `AlertAck`

- `by`: string/null
- `note`: string/null

### `BeneficiaryIn`

- `full_name` (required): string
- `country` (required): string
- `relationship`: string/null
- `payout_channel`: string/null
- `id_type`: string/null
- `id_number`: string/null
- `dob`: string/null

### `Body_alerts_ack_alerts__alert_id__ack_post`

- `note`: string

### `Body_review_disposition_review__decision_id__post`

- `outcome` (required): string
- `reason`: string
- `by`: string

### `Body_screen_upload_screen_post`

- `file` (required): string
- `name_col`: string
- `dob_col`: string
- `nat_col`: string
- `type_col`: string
- `ref_col`: string
- `default_type`: string
- `monitor`: string

### `CombinedRiskRequest`

- `aml_data` (required):  — AML screening data
- `kyc_data` (required):  — KYC verification data

### `CombinedRiskResponse`

- `request_id` (required): string
- `combined_risk_score` (required): integer
- `combined_risk_level` (required): 
- `risk_factors`: array
- `aml_risk_score`: integer/null
- `aml_risk_level`: /null
- `kyc_risk_score`: integer/null
- `kyc_risk_level`: /null
- `details`: array
- `aml_details`: object/null
- `kyc_details`: object/null

### `CustomerBatchIn`

- `customers` (required): array
- `screen_now`: boolean

### `DecisionRequest`

- `corridor` (required): string
- `customer` (required): ref
- `beneficiary`: /null
- `kyc`: /null
- `transfer`: /null

### `DecisionResponse`

- `request_id` (required): string
- `decision_id`: integer/null
- `corridor` (required): string
- `ruleset_version` (required): string
- `ruleset_status` (required): string
- `outcome` (required): string
- `risk_score` (required): integer
- `reasons` (required): array
- `actions` (required): array
- `screening` (required): object
- `screening_id`: integer/null
- `list_version`: string/null
- `id_check`: object/null
- `beneficiary_id_check`: object/null
- `name_analysis`: object/null
- `facts` (required): object

### `DispositionIn`

- `outcome` (required): string
- `reason` (required): string — What an inspector will read
- `by` (required): string — Reviewer's name

### `DocumentData`

- `document_type` (required): string
- `document_number` (required): string
- `expiry_date` (required): string
- `issue_date`: string/null
- `issuing_country` (required): string
- `first_name` (required): string
- `last_name` (required): string
- `date_of_birth` (required): string
- `nationality` (required): string
- `address` (required): object

### `KYCRequest`

- `document_data` (required): ref
- `document_image_base64` (required): string
- `selfie_image_base64` (required): string
- `request_id`: string/null
- `metadata`: object/null

### `KYCResponse`

- `request_id` (required): string
- `status` (required): string
- `risk_score`: number/null
- `risk_level`: /null
- `verification_result`: object/null
- `timestamp` (required): string
- `error`: object/null

### `KycIn`

- `document_verified`: boolean/null
- `face_match`: boolean/null
- `document_expired`: boolean/null
- `mrz_mismatches`: integer/null
- `liveness`: boolean/null

### `MatchResult`

- `sanctioned_name` (required): string — Primary name on the list
- `matched_name`: string/null — The name or alias that produced the score
- `match_type`: string/null — 'name', 'alias' or 'identifier'
- `id_numbers`: string/null — Identity numbers on the list entry
- `source` (required): string
- `dataid`: string/null
- `record_type`: string/null
- `program`: string/null
- `listed_on`: string/null
- `similarity` (required): number — Similarity score 0-100
- `confidence` (required): string — Confidence level: high, medium, or low
- `aliases`: array
- `dob`: array/null — Dates or years of birth on the list entry
- `dob_agreement`: string/null — exact | year | mismatch | unknown
- `dob_match`: boolean/null — Whether DOB agrees (None if unknown)
- `country`: string/null
- `country_match`: boolean/null — Whether nationality agrees (None if unknown)

### `RiskLevel`


### `TenantSettings`

- `webhook_url`: string/null — POST target for new alerts
- `name`: string/null

### `TransferIn`

- `amount`: number/null — In the sending currency
- `currency`: string/null
- `receive_amount`: number/null — In the receiving currency
- `receive_currency`: string/null
- `purpose`: string/null
- `purpose_category`: string/null — family_support | charity | business | education | medical | savings | other

### `app__models__corridor__CustomerIn`

- `full_name` (required): string
- `dob`: string/null — YYYY-MM-DD
- `nationality`: string/null — ISO alpha-2
- `residence_country`: string/null
- `entity_type`: string
- `document_type`: string/null — qatar_id | passport | pk_cnic | in_aadhaar | bd_nid | ph_philsys | commercial_registration ...
- `document_number`: string/null
- `document_expiry`: string/null
- `place_of_birth`: string/null
- `mobile`: string/null
- `address_qatar`: string/null
- `profession`: string/null
- `employer_sponsor`: string/null
- `pep`: boolean/null — Politically exposed person, self-declared or from a PEP source
- `is_resident`: boolean/null
- `first_transaction`: boolean/null
- `registered_address`: string/null
- `ubo_names`: array/null
- `purpose`: string/null
- `reference`: string/null — Your customer id; when given the customer is put on file for monitoring

### `app__models__records__CustomerIn`

- `reference` (required): string — Your identifier for this customer
- `full_name` (required): string
- `dob`: string/null — YYYY-MM-DD
- `nationality`: string/null
- `entity_type`: string
- `monitored`: boolean — Re-screen automatically when lists change
