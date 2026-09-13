# Corridor rule packs (proprietary)

Rulesets are JSON files validated by `app/corridor/schema.py` and applied by the open-source engine. This directory is under the proprietary notice in `../LICENSE`.

| Corridor | File | Status |
|---|---|---|
| Qatar → Philippines | `qa_ph_rules.json` | v0.3, draft: 30 rules drafted from the QCB AML/CFT Instructions, Law 20/2019, QFCRA sanctions guidance and BSP circulars; awaiting review by a named compliance professional |
| Qatar → Pakistan | planned | after the first pilot |
| UAE → India | planned | |
| Saudi Arabia → Bangladesh | planned | |

`template.json` is the starting point for a new corridor. `status` stays `draft` until `reviewed_by` and `reviewed_on` are set, and the status travels with every decision.
