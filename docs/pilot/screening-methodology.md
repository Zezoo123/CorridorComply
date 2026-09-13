# Screening methodology

Written in the vocabulary of the Wolfsberg Group guidance on sanctions
screening and the QFCRA sanctions guidance (2025), for attachment to a firm's
AML manual.

## Reference data

Lists loaded:

| List | Publisher | Why |
|---|---|---|
| UN Security Council consolidated list | UN | Binding on Qatar; QCB item 10.4 |
| Qatar NCTC unified record | Ministry of Interior | Domestic designations by Public Prosecutor order; QCB 10.4 and 18(9) |
| OFAC SDN and OFAC Consolidated (non-SDN) | US Treasury | Dollar clearing and correspondent banks |
| UK OFSI consolidated list | HM Treasury | Sterling clearing and correspondent banks |
| EU consolidated financial sanctions list | European Commission | Euro clearing and correspondent banks |
| The firm's internal watchlist | The firm | Previously rejected customers, regulator circulars, FIU requests |

Each public source is downloaded from the publisher on a schedule you set
(daily recommended), converted to a common schema, and combined into one file
whose SHA-256 checksum identifies the **list version**. The internal watchlist is
uploaded by the firm and becomes part of the same versioned file. Every screening
and decision stores the list version it ran against, so any result can be
reproduced.

**Both parties to a transfer are screened.** The sender at onboarding and on
each decision; the beneficiary on each decision, against the same lists with the
same identifiers, because QCB item 18(9) prohibits a transfer of any value where
the originator or the recipient is listed.

**Country risk** comes from a dated file of the FATF call-for-action and
increased-monitoring lists (and the EU high-risk third-country list when
populated), updated after each FATF plenary, not from constants in code.

**Licensed data not included:** politically exposed persons (QCB item 10.3
requires PEP measures; PEP data is a licensed feed which we integrate rather
than own) and adverse media. Both are offered as add-ons with the licence cost
passed through. Receiving-country designation lists (Philippines AMLC, Pakistan
NACTA, India MHA) are on the roadmap for the corridor packs.

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

No PEP data and no adverse media without a licensed feed. No ownership analysis
(OFAC 50 percent rule). No transaction monitoring. No document forgery
detection; liveness only through a configured vendor. Each is stated to the
customer in writing.

## Identity-number matches

When a customer identity number (QID, passport, CNIC, Aadhaar, national ID) is supplied, it is compared exactly against the numbers held on the lists, after stripping spaces and punctuation. An identity-number hit is reported as `match_type: identifier` with similarity 100, whatever the spelling of the name. Each such hit also carries `name_similarity`, how well the customer's name agrees with the listed name, and when one number sits against several list entries the entry whose name agrees best is reported first. That situation is real: the Qatar NCTC unified record published by the Ministry of Interior carries the same Qatari ID and date of birth against three different individuals (QLDi.013, QLDi.024, QLDi.025). The tool reports all three and leaves the decision to the reviewer rather than hiding what the source says.
