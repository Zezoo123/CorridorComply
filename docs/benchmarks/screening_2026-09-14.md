# Screening benchmark, 2026-09-14

List version `combined_sanctions_20260914_211428.csv@2026-09-14T21:14:29` · seed 7 · 6058 screens · 3.71 ms per screen

## Recall on 600 listed individuals (date of birth supplied)

| Name as supplied | Asked | Found | Found at rank 1 | Recall | Top-1 |
|---|---:|---:|---:|---:|---:|
| Exactly as listed | 600 | 599 | 496 | 99.8% | 82.7% |
| A listed alias | 299 | 299 | 256 | 100.0% | 85.6% |
| One transliteration change | 521 | 499 | 406 | 95.8% | 77.9% |
| Surname first | 598 | 598 | 495 | 100.0% | 82.8% |
| Middle token dropped | 475 | 463 | 332 | 97.5% | 69.9% |
| One letter missing | 565 | 558 | 460 | 98.8% | 81.4% |

## False positives on 3000 synthetic clean names (date of birth and nationality supplied)

| Population | Names | Flagged | Medium or high | Flagged rate | Medium/high rate |
|---|---:|---:|---:|---:|---:|
| BD | 429 | 20 | 4 | 4.7% | 0.9% |
| EG | 428 | 35 | 10 | 8.2% | 2.3% |
| IN | 429 | 4 | 0 | 0.9% | 0.0% |
| LK | 428 | 0 | 0 | 0.0% | 0.0% |
| NP | 428 | 1 | 0 | 0.2% | 0.0% |
| PH | 429 | 1 | 1 | 0.2% | 0.2% |
| PK | 429 | 20 | 9 | 4.7% | 2.1% |
| **All** | 3000 | 81 | 24 | 2.7% | 0.8% |

Most frequently matched list entries:

- MOHAMMED AL-AHMED [UK]: 6
- Mahmoud Ibraheem SA'IID [EU]: 4
- WEHBE, MOHAMAD HASAN [OFAC]: 3
- BASHIR MOHAMED MAHAMOUD [UN]: 3
- ALI, AHMED MOHAMMED HAMED [OFAC]: 3
- Mohammed Ali NASR [EU]: 3
- KARIM ALI, ALI ABDUL [OFAC]: 2
- Gud Mullah Mohammad Hassan [EU]: 2
- MOHAMED AMIN MOSTAFA [UN]: 2
- AHMAD MAHMOOD HASSAN [UN]: 2

Examples:

| Clean name | DOB | Nat | Best match | Via | Sim | DOB | Risk |
|---|---|---|---|---|---:|---|---|
| Karim Adel Ali | 1971-06-17 | EG | KARIM ALI, ALI ABDUL | KARIM, ALI ABDUL | 89.66 | mismatch | low 39 |
| Mohammad Arif Ali | 1987-03-20 | PK | JAFARI, MOHAMMAD ALI | JAFARI, MOHAMMAD ALI | 88.89 | mismatch | low 35 |
| Mohammad Islam Ahmed | 1982-02-03 | BD | MOHAMMED AL-AHMED | MOHAMMAD AL-AHMED | 86.49 | mismatch | low 35 |
| Hany Ahmed Nasser | 1980-12-26 | EG | NASSER AHMED MUTHANA | NASSER AHMED MUTHANA | 86.49 | mismatch | low 35 |
| Mohamed Said Hassan | 1970-07-04 | EG | WEHBE, MOHAMAD HASAN | WAHBI, MOHAMED HASSAN | 87.18 | mismatch | low 35 |
| Mohammad Ahmed Islam | 1985-04-27 | BD | MOHAMMED AL-AHMED | MOHAMMAD AL-AHMED | 86.49 | mismatch | low 35 |
| Abdul Akter Ali | 1979-11-20 | BD | SA'ID AL-JAMAL | ABU-ALI (short form abdul ali) | 63.64 | year | low 35 |
| Mohammed Rao | 1999-06-17 | IN | RA'D, MUHAMMAD HASAN | RAAD, MOHAMMED | 88.0 | mismatch | low 35 |
| Mahmoud Mohamed Ali | 1971-07-14 | EG | BASHIR MOHAMED MAHAMOUD | BASHIR MOHAMED MAHMOUD | 87.8 | mismatch | low 35 |
| Amr Salem | 1986-07-21 | EG | Amr SALEM | Amr SALEM | 100.0 | mismatch | medium 50 |
| Mohammed Thomas | 1971-05-06 | IN | MOHAMMAD AMAN AKHUND | MULLAH MOHAMMED OMAN | 85.71 | mismatch | low 39 |
| Hassan Tariq Ahmed | 1967-09-10 | PK | MOUKALLED, HASSAN AHMED | MOUKALLED, HASSAN AHMED | 94 | year | medium 65 |
| Youssef Mahmoud Ali | 1978-07-08 | EG | YOUSSEF, ADNAN MAHMOUD | YOUSSEF, ADNAN MAHMOUD | 85.0 | mismatch | low 35 |
| Mohammed Karim Ali | 1983-09-01 | BD | KARNIB, ALI MOHAMAD | KARNIB, ALI MOHAMMED | 91.89 | mismatch | low 35 |
| Mahmoud Mohamed Ali | 1989-11-10 | EG | BASHIR MOHAMED MAHAMOUD | BASHIR MOHAMED MAHMOUD | 87.8 | mismatch | low 35 |

## Recall misses (first 15)

| Form | Query | Listed as | Source | Got instead |
|---|---|---|---|---|
| translit | ali abd alnabi ahmed ebrahim m alshofa | ALSHOFA, ALI ABDULNABI AHMED EBRAHIM M | OFAC | - |
| translit | mohammed iahya mujahid | Mohammed Yahya Mujahid | EU | - |
| translit | mohammad iazdi | YAZDI, MOHAMMAD | OFAC | AZIMI, MOHAMMAD NAZAR; AZIZ HAJMOHAM-MADI |
| as_listed | HAJI NOORULLAH | NOORULLAH, HAJI | OFAC | - |
| translit | nurullah | NOORULLAH, HAJI | OFAC | Norullah Noori |
| typo | norullah | NOORULLAH, HAJI | OFAC | Norullah Noori |
| dropped_middle | abdul murad | ABDUL HAKIM MURAD | UK | - |
| dropped_middle | abu baasyir | Abu Bakar Ba'asyir | EU | - |
| translit | paul dabi jr | DABY JR., PAUL | OFAC | - |
| dropped_middle | paul jr | DABY JR., PAUL | OFAC | Bol Malong |
| translit | marial chanuong iol mangok | MARIAL CHANUONG YOL MANGOK | UN | - |
| translit | ii xuan wu | WU, YI XUAN | OFAC | - |
| translit | iolanda sofia cano alzate | CANO ALZATE, YOLANDA SOFIA | OFAC | - |
| dropped_middle | abdul shah | ABDUL BAQI BASIR AWAL SHAH | UN | - |
| translit | mikhail iuryevich avdeyev | AVDEYEV, MIKHAIL YURYEVICH | OFAC | MIKHAIL YURIEVICH AVDEEV; Михаил Юрьевич АВДЕЕВ |

Method: `scripts/benchmark_screening.py`. Synthetic names are drawn from pools of common given names and surnames; a hit on one is counted as a false positive even if a real listed person shares the name, so the rate is an upper bound.
