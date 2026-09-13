# Corridor rulesets

A corridor ruleset is the decision layer above screening and KYC for one
sending country and one receiving country. It is a JSON file in
`premium/corridor_rules/` (override the directory with `CORRIDOR_RULES_DIR`),
validated against `app/corridor/schema.py` when the API starts. An invalid file
is reported at `GET /api/v1/corridors` and never applied.

## What a ruleset contains

- `sending` / `receiving`: country, regulators, national lists that apply, the
  documents accepted for each customer type, and the fields required for CDD.
- `screening`: which lists, the match threshold, whether single-name customers
  need a date of birth, whether population-aware name variants are screened.
- `rules`: ordered list. Each rule has an `id`, a human `title`, a `when` block
  (`all` and/or `any` conditions over documented fields), an `outcome`
  (`approve`, `review`, `reject`), a `reason` shown to the reviewer, a `risk_add`,
  optional `actions`, and a `basis` naming the regulatory source.
- `reporting`: the FIU, its portal, and the fields to prefill in an STR.
- `status`: `draft` until a named compliance professional has reviewed it
  (`reviewed_by`, `reviewed_on`). The status is returned with every decision and
  stored with it, so nobody can mistake a draft for a signed ruleset.

The fields a condition may reference, with their meaning, are served at
`GET /api/v1/corridors/fields`.

## How a decision is made

`POST /api/v1/decision` with the corridor id, the customer, and optionally the
beneficiary, KYC results and transfer:

1. The customer is screened. Name variants are generated for the customer's
   population (a Filipino "Maria Clara Santos dela Cruz" is also screened as
   "Maria Clara dela Cruz" and "Maria dela Cruz"; a South Asian patronymic is
   screened without the father's name), and the best match per list entry is
   kept.
2. Identity numbers are checked against their published format. A Qatar ID
   encodes birth year and nationality, so both are compared with what the
   customer stated. A Pakistani CNIC encodes sex; an Aadhaar carries a check
   digit; a Bangladeshi 17-digit NID starts with the birth year.
3. Every rule whose conditions hold fires. The outcome is the most severe;
   every reason is returned and stored, with the rule id and its basis.
4. The screening, the decision and (when a reference is given) the customer are
   persisted, so the decision can be replayed against the same list version.

## Changing a threshold

Edit the JSON, restart (or call `reset_registry()`); no code change. The test
`test_changing_a_threshold_in_the_file_changes_the_decision` proves it.

## What the primary sources say (QA-PH)

Read on 8 September 2026 from the documents themselves; section numbers are
given so a reviewer can check the wording.

**Qatar Central Bank, AML/CFT Instructions (May 2020, English, published by QFIU)**
- 10.4: from the outset and on an ongoing basis, check whether a person is listed
  under a UNSC resolution or a Terrorist Designation Public Prosecutor Order
  circulated by the NCTC. If listed: no relationship or transaction, immediately
  (within 24 hours); STR to the FIU; inform QCB within 24 hours.
- CDD triggers include a one-off transaction of at least QR 50,000, a linked series
  totalling QR 50,000, and **carrying out MVTS above QR 3,500**; 14.12 requires
  systems to spot linked one-off transactions meant to stay under QR 50,000.
- 15.2: identification data for individuals: full name, aliases, permanent address,
  contact details, profession, work address, nationality, **QID number for Qataris
  and residents, passport number for non-residents**, date and place of birth,
  sponsor name and address, purpose; verified from a valid official document.
- 18: MVTS and wire transfers. Cross-border transfers carry full originator and
  recipient information; domestic transfers under QR 3,500 may carry names and
  account or reference only; a beneficiary provider rejects or chases missing
  information; **no transaction of any value with a listed person** (18(9));
  **charitable causes need prior approval** (18(10)); originator and recipient
  information kept 10 years (18(14)).
- 19.5: STR immediately, by the MLRO or deputy, irrespective of amount, even if no
  transaction happened; inform QCB when the STR concerns a proposed transaction.
- 6.7: outsourcing. The institution and its Board stay responsible; the SLA must
  bind the vendor to the Law and the firm's procedures and give the MLRO, QCB and
  FIU unrestricted access to documents. This shapes our contract and the on-premise
  deployment.

**Law No. 20 of 2019**: records kept at least ten years after the relationship
ends or the transaction completes; CDD on occasional transactions at the
threshold set in the Implementing Regulation; wire transfers in Article 18.

**QFCRA, Guidance on an Effective Sanctions Compliance Programme (2025)**:
screen immediately after publication of UNSC sanctions, NCTC domestic alerts or
PPO orders; fuzzy matching calibrated to the firm's risk; keep records of all
alerts and actions, including cleared false positives.

**Qatar NCTC unified record** (Ministry of Interior portal): 864 entries on
8 September 2026, 595 individuals and 269 entities, of which 112 are domestic
designations by Public Prosecutor order (reference numbers QLDi/QLDe); 119
entries carry a QID and 248 a passport number. Loaded as source `QA_NCTC` and
matched on identity number as well as name.

**Bangko Sentral ng Pilipinas**: Circular 1206 (2024), consolidated money service
business rules: pay-outs above PHP 500,000 require enhanced due diligence and are
paid only by cheque or account credit. Circular 608: a first-time claimant
presents one valid photo-bearing ID from an official authority (list in the
ruleset); beneficiaries below voting age may use a signed school ID. Memorandum
M-2025-012: every format of the National ID is accepted. AMLC: covered
transaction reports above PHP 500,000 within five working days.

**Not yet found in primary text** and therefore still marked "confirm": the exact
QCB expectations for exchange-house customer risk rating, the current AMLC STR
deadline for RTCs, and the receiving partner's own beneficiary rules.

## Version 0.3 of QA-PH

Adds beneficiary screening rules (`beneficiary-listed`, `beneficiary-identifier-match`,
`beneficiary-possible-match`), country-risk rules driven by
`app/data/countries/risk_lists.json` (FATF call-for-action and increased
monitoring, dated), an internal-watchlist rule, and OFAC's non-SDN consolidated
list in the screening policy. 29 rules.

## Version 0.2 of QA-PH

`premium/corridor_rules/qa_ph_rules.json` has 23 rules. Those citing a section
above were drafted from the primary text; those whose basis says "firm policy" or
"confirm" are judgement placeholders. It is **not reviewed** by a compliance
professional, and every decision carries `ruleset_status: draft` until it is.

## Identity validators

| Type | Checks | Facts extracted |
|---|---|---|
| `qatar_id` | 11 digits, century digit 2/3 | birth_year, nationality |
| `pk_cnic` | 13 digits, region digit | sex |
| `in_aadhaar` | 12 digits, Verhoeff check digit | none (collection is legally restricted; prefer other IDs) |
| `bd_nid` | 10, 13 or 17 digits | birth_year (17-digit) |
| `ph_philsys` | 16 digits | none |
| `passport` | per-country shape, low confidence | format_known |

A failed format check produces a `review`, never a `reject`: a typo is far more
common than fraud.
