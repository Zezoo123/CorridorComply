# Data handling (pilot)

**Where the software runs.** On your machine or server, in Qatar. The Docker
image contains code and no customer data. We do not operate a hosted service
during the pilot and we never receive your customers' data.

**What is stored, and where.**

| Data | Where | Why |
|---|---|---|
| Sanctions lists (UN, OFAC SDN and consolidated, UK, EU, Qatar NCTC) and your internal watchlist | `/data/sanctions` on your host | Screening; each combined file is a checksummed list version |
| Screenings (name, DOB, nationality, matches, list version, request id, tenant) | your database (`DATABASE_URL`, SQLite by default) | Evidence of what was screened, when, against what |
| Customers you keep on file | your database | Re-screening when lists change |
| Decisions, reasons, dispositions | your database | The disposition trail for inspection |
| Alerts | your database | Ongoing monitoring |
| Audit log (JSON lines) | `logs/audit/` on your host | Every API call with sanitized payload, request id, tenant; images are never written |
| Application log | `logs/app.log` | Operational; request bodies and headers are not logged |
| Uploaded files | not stored | Rows are screened in memory; the report lives in memory until restart |
| Document and selfie images | not stored | Processed in memory for OCR and face match |

**Retention.** Nothing is deleted automatically. Law No. 20 of 2019 requires
ten years; you decide the policy and apply it to the database and the log
directory. Deleting a customer stops monitoring but keeps the history.

**Access.** API keys are stored as SHA-256 hashes; each key belongs to one tenant
and sees only that tenant's records. The web UI is protected by a login
(`UI_USERNAME` / `UI_PASSWORD`); the reviewer's name on dispositions defaults to
the logged-in user. Keep it on a private network regardless. QCB item 6.7 gives your MLRO, QCB and the FIU a
right of access to records held by a vendor: everything is in your database and
your log directory, in plain JSON, exportable per customer.

**What we can see.** Nothing, unless you send us a file for a demo. If you do,
we delete it after the session and confirm in writing.

**Not done in the pilot.** Encryption at rest beyond what your host provides;
per-user accounts and roles in the web UI (one shared login); automatic
retention enforcement. Each is
on the roadmap and none is hidden.
