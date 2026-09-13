# Roadmap

## Pilot MVP (current)

Goal: a licensed remittance house or obligated entity on the Qatar → Philippines corridor runs real customers through it and can show the result to an inspector.

Done: screening engine with aliases, transliteration, entity types, DOB, nationality and identity numbers; six list sources plus the firm's watchlist; API keys and tenants; persistence with list versions; re-screening and alerts; corridor engine with the QA-PH draft ruleset (30 rules, cited); beneficiary screening; review console with dispositions; evidence bundle; passport and ID-card MRZ with per-field checksums; liveness interface; pilot pack.

Open: sign-off of the QA-PH ruleset by a named compliance professional (#15); passport OCR on low-quality scans (#46); response polish (#13).

## Post-pilot

- PEP and adverse-media feeds (licensed), ownership data for the OFAC 50 percent rule
- Receiving-country designation lists (Philippines AMLC, Pakistan NACTA, India MHA) and the UAE and Saudi local lists, as corridor packs
- Qatar → Pakistan, UAE → India, Saudi Arabia → Bangladesh rulesets
- Per-user accounts and roles in the console; retention enforcement; encryption at rest
- STR prefill export for Ekhtar and goAML
- Transaction monitoring (structuring under thresholds, one sender to many beneficiaries)
- Billing
