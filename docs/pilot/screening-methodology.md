# Screening methodology

Written in the vocabulary of the Wolfsberg Group guidance on sanctions
screening and the QFCRA sanctions guidance (2025), for attachment to a firm's
AML manual.

## Reference data

Lists loaded: UN Security Council consolidated list; OFAC SDN; UK OFSI
consolidated list; EU consolidated financial sanctions list; Qatar NCTC unified
record (UNSC designations as applied in Qatar and domestic designations by
Public Prosecutor order). Each source is downloaded from the publisher on a
schedule you set (daily recommended), converted to a common schema, and
combined into one file whose SHA-256 checksum identifies the **list version**.
Every screening and decision stores the list version it ran against, so any
result can be reproduced.

Fields used from each entry: primary name, all listed aliases (including
non-Latin script forms), entity type (individual, entity, vessel), dates or
years of birth, nationalities, identity numbers, programme or regime, listing
date.

## Matching

1. **Normalisation.** Names are transliterated to ASCII, lower-cased,
   punctuation removed, honorifics removed (Dr, Haji, Sheikh, Colonel ...).
2. **Candidate selection.** Each name and alias is indexed by its tokens and by
   a consonant skeleton that groups transliteration variants (Mohammed,
   Muhammad, Mohamed). Particles (al, bin, abu, de, la ...) are not used as keys.
   A query retrieves entries sharing enough significant tokens or skeletons.
3. **Scoring.** Candidates are scored with token-sort similarity so word order
   does not matter (Yasin Abdul Rahman = Abdul Rahman Yasin). The best-scoring
   name or alias per entry is kept and reported as "matched on".
4. **Population-aware variants.** For a person, additional name forms are
   screened: a Filipino name without the middle (mother's maiden) name and with
   the compound surname kept together; a South Asian name without a patronymic
   ("s/o", "bin"); suffixes removed. The best match across variants is kept.
5. **Identity numbers.** Any identity number supplied (QID, passport) is matched
   exactly against the identity numbers on the lists. An identifier match is
   reported as such and treated as a confirmed match regardless of name score.
6. **Entity type.** A person is screened against individuals, a company against
   entities and organisations, a vessel against vessels, unless "any" is chosen.
7. **Secondary identifiers.** Date of birth is compared as exact, same year,
   mismatch or unknown; nationality as match, mismatch or unknown after mapping
   list country names to ISO codes.

## Thresholds and calibration

The similarity threshold defaults to 85 of 100 and is set per corridor in the
ruleset. Above 95 is reported as high confidence, 85 to 94 as medium. The firm
chooses and documents its threshold; a test set of known true and false
positives is provided to see the effect of moving it. A match whose date of
birth disagrees with every candidate is demoted in the risk score, never hidden.

## Alerts, dispositions and records

Every screening is stored with its matches. Decisions whose outcome is review or
reject wait for a reviewer, who records approved, rejected or escalated with a
mandatory reason and their name; the time to close is recorded. Cleared false
positives are therefore kept with their reason, as the QFCRA guidance expects.

## Ongoing screening

Customers kept on file are re-screened against every new list version. A new
hit, an additional matching entry, or a cleared hit raises an alert with the
exact entry that changed. Alerts are acknowledged with a reason.

## Document checks (KYC)

The machine-readable zone of a passport (TD3) or ID card (TD1) is located,
read, and parsed; each check digit (document number, birth date, expiry,
composite) is reported separately so a reviewer can tell an OCR misread from a
tampered field. Expiry is checked against today. The parsed fields are compared
with the data the customer submitted (name, document number, date of birth,
nationality, expiry, issuing country) and mismatches are scored. The selfie is
compared with the document photo. Liveness runs only when a vendor is
configured and says so otherwise.

## Known limits

No PEP data. No ownership analysis (OFAC 50 percent rule). OFAC non-SDN lists
not loaded. No transaction monitoring. No document forgery detection; liveness
only through a configured vendor. Each is stated to the customer in writing.
