# Pilot onboarding guide

Goal: a compliance officer can run CorridorComply on their own machine within a
day, screen a customer file, and see a decision with reasons.

## 1. Run it (screening-only, no ML stack)

```bash
docker build -t corridorcomply .
docker run -d --name cc -p 8000:8000 -v $(pwd)/cc-data:/data corridorcomply
docker exec cc python scripts/update_sanctions.py        # first list download, a few minutes
docker exec cc python -m app.auth new-key <your-firm>     # prints the API key once
```

Open `http://localhost:8000/screen`. Nothing you upload leaves the machine.
Postgres instead of SQLite: set `DATABASE_URL` on the container.

For document OCR and face matching, build with `--build-arg WITH_ML=1`.

## 2. Screen a file (the shadow run)

Upload a CSV or XLSX of customers at `/screen`. Recognised headers: name,
date of birth, nationality, type, id. Tick "keep on file" to enrol the
customers for re-screening. Download the report as CSV; every row carries the
list version it was screened against.

## 3. Call the API

```bash
curl -s -X POST http://localhost:8000/api/v1/decision \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{
  "corridor": "QA-PH",
  "customer": {"full_name": "Maria Clara Santos", "dob": "1985-02-14", "place_of_birth": "Cebu",
               "nationality": "PH", "document_type": "qatar_id", "document_number": "28560812345",
               "document_expiry": "2028-01-01", "mobile": "+974...", "address_qatar": "Doha",
               "profession": "nurse", "employer_sponsor": "Hamad Medical", "purpose": "family support",
               "reference": "CUST-1001"},
  "beneficiary": {"full_name": "Jose Santos", "country": "PH", "relationship": "father",
                  "payout_channel": "cash", "id_type": "ph_philsys", "id_number": "1234-5678-9012-3456"},
  "transfer": {"amount": 3000, "currency": "QAR", "receive_amount": 47000, "receive_currency": "PHP"}
}'
```

The response carries `outcome` (approve / review / reject), every rule that
fired with its regulatory basis, the screening matches, identity-number checks,
`decision_id`, `screening_id` and `list_version`.

## 4. Review and close

Decisions with outcome review or reject wait at `/review`. Record a disposition
with a reason and your name. `GET /api/v1/customers/{reference}/evidence`
exports everything on file for one customer.

## 5. Keep lists fresh and customers monitored

```
0 3 * * *  docker exec cc sh -c "python scripts/update_sanctions.py --max-age-hours 20 && python -m app.monitoring rescreen"
```

Changes raise alerts at `/alerts` and, if configured, at your webhook.

## What you need from us

An API key, this guide, the data-handling note, the screening methodology, and
the outsourcing clause. What we need from you: the customer file for the shadow
run, and thirty minutes with the MLRO.
