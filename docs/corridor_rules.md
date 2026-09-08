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

## Version zero of QA-PH

`premium/corridor_rules/qa_ph_rules.json` was drafted from public material and
is **not reviewed**. Rules that encode facts (ID formats, list mechanics,
FATF call-for-action countries) are testable today. Rules that encode
judgement (which fields QCB requires, thresholds, minimum age) are placeholders
for a compliance advisor to correct and sign. Until then every decision carries
`ruleset_status: draft`.

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
