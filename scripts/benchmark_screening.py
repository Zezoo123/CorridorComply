"""
Screening quality benchmark: recall on listed persons under realistic name variation,
and false-positive rate on a synthetic population of common clean names.

    python scripts/benchmark_screening.py            # live lists, 600 listed persons, 3000 clean names
    python scripts/benchmark_screening.py --sample 200 --clean 500 --out docs/benchmarks

Recall: for each sampled listed individual, the engine is asked to find that entry
under several forms of the name (as listed, an alias, a transliteration change, a
different token order, a dropped middle token, a one-letter typo), with the list's
date of birth supplied. A form counts as found when the sampled entry is among the
matches; "top" when it is the first match.

False positives: names are generated from pools of common given names and surnames
for the corridor populations (Pakistani, Indian, Bangladeshi, Filipino, Egyptian,
Nepali, Sri Lankan), each with a date of birth and nationality. Any hit on such a
name is a false positive for the purposes of this benchmark, since the names are
synthetic; high-confidence hits are the ones a reviewer would have to work on.

The numbers depend on the list version and are written with it.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.names import normalize  # noqa: E402
from app.services.aml_service import AMLService  # noqa: E402
from app.services.screening import get_index  # noqa: E402

# ------------------------------------------------------------------ name variation
TRANSLIT_RULES: List[Tuple[str, str]] = [
    ("mohammed", "muhammad"), ("mohammad", "mohamed"), ("muhammad", "mohammed"), ("mohamed", "muhammad"),
    ("hussein", "hossain"), ("hussain", "husain"), ("hossein", "hussein"),
    ("abdul", "abd al"), ("abdel", "abdul"), ("abdullah", "abdallah"),
    ("al-", "al "), ("el ", "al "), ("al ", "el "),
    ("ou", "u"), ("ee", "i"), ("oo", "u"), ("ai", "ay"), ("ei", "ai"),
    ("q", "k"), ("kh", "k"), ("gh", "g"), ("dh", "d"), ("th", "t"), ("ph", "f"),
    ("y", "i"), ("ck", "k"), ("sh", "ch"), ("z", "s"), ("v", "w"),
    ("ah ", "a "), ("eh ", "e "),
]


def listed_name(name: str) -> str:
    """OFAC writes 'LAST, FIRST'; a customer writes 'First Last'."""
    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    return name


def translit(name: str, rng: random.Random) -> Optional[str]:
    n = normalize(name)
    rules = list(TRANSLIT_RULES)
    rng.shuffle(rules)
    for a, b in rules:
        if a in n:
            out = n.replace(a, b, 1)
            if out != n:
                return out
    return None


def reorder(name: str) -> Optional[str]:
    t = normalize(name).split()
    if len(t) < 2:
        return None
    return " ".join([t[-1]] + t[:-1])


def drop_middle(name: str) -> Optional[str]:
    t = normalize(name).split()
    if len(t) < 3:
        return None
    return " ".join([t[0], t[-1]])


def typo(name: str, rng: random.Random) -> Optional[str]:
    t = normalize(name).split()
    long_tokens = [i for i, tok in enumerate(t) if len(tok) >= 5]
    if not long_tokens:
        return None
    i = rng.choice(long_tokens)
    pos = rng.randrange(1, len(t[i]) - 1)
    t[i] = t[i][:pos] + t[i][pos + 1:]
    return " ".join(t)


def latin(s: str) -> bool:
    return bool(s) and bool(re.fullmatch(r"[A-Za-z0-9 ,.'\-()/]+", s.strip()))


# ------------------------------------------------------------------ synthetic clean population
POOLS: Dict[str, Dict[str, List[str]]] = {
    "PK": {
        "given": ["Muhammad", "Mohammad", "Ahmed", "Ali", "Imran", "Usman", "Bilal", "Hassan", "Hussain", "Asad", "Faisal",
                  "Kamran", "Adnan", "Shahid", "Tariq", "Zeeshan", "Waqas", "Saad", "Fahad", "Umar", "Ayesha", "Fatima",
                  "Sana", "Hira", "Maryam", "Zainab", "Rabia", "Sadia", "Amna", "Iqra"],
        "middle": ["Imran", "Ahmed", "Ali", "Asif", "Arif", "Javed", "Tariq", "Aslam", "Akram", "Iqbal", "Bibi", "Noor", ""],
        "surname": ["Khan", "Malik", "Chaudhry", "Butt", "Sheikh", "Qureshi", "Siddiqui", "Baig", "Mirza", "Rana", "Awan",
                    "Bhatti", "Iqbal", "Ahmed", "Raza", "Shah", "Mahmood", "Akhtar", "Hussain", "Ali"],
    },
    "IN": {
        "given": ["Rahul", "Amit", "Rajesh", "Suresh", "Vijay", "Anil", "Sanjay", "Ravi", "Manoj", "Deepak", "Arjun", "Vikram",
                  "Priya", "Anjali", "Sunita", "Neha", "Pooja", "Kavita", "Deepa", "Lakshmi", "Mohammed", "Abdul", "Shaik"],
        "middle": ["Kumar", "Singh", "Prasad", "Chandra", "Devi", "Lal", "Nath", "Raj", "", "", ""],
        "surname": ["Sharma", "Verma", "Gupta", "Singh", "Kumar", "Patel", "Nair", "Menon", "Reddy", "Rao", "Iyer", "Pillai",
                    "Das", "Yadav", "Mishra", "Joshi", "Thomas", "Varghese", "Khan", "Ansari"],
    },
    "BD": {
        "given": ["Mohammad", "Mohammed", "Md", "Abdul", "Rafiqul", "Shafiqul", "Jahangir", "Kamal", "Jamal", "Nasir", "Habib",
                  "Sohel", "Rubel", "Shahin", "Farida", "Nasrin", "Shahnaz", "Rokeya", "Sultana", "Taslima"],
        "middle": ["Rahman", "Islam", "Hossain", "Alam", "Uddin", "Ahmed", "Karim", "Miah", "Begum", "Akter", "", ""],
        "surname": ["Islam", "Rahman", "Hossain", "Ahmed", "Uddin", "Alam", "Miah", "Sarkar", "Chowdhury", "Khan", "Begum",
                    "Akter", "Molla", "Haque", "Karim", "Ali", "Sheikh", "Mondal", "Talukder", "Bhuiyan"],
    },
    "PH": {
        "given": ["Maria", "Jose", "Juan", "Antonio", "Angelica", "Jhon", "Mark", "Joshua", "Christian", "Michael", "Angelo",
                  "Rowena", "Marites", "Jocelyn", "Grace", "Cristina", "Ronald", "Reynaldo", "Ferdinand", "Lorna"],
        "middle": ["Santos", "Reyes", "Cruz", "Garcia", "Bautista", "Mendoza", "Villanueva", "Ramos", "Torres", "Castillo", ""],
        "surname": ["Dela Cruz", "Santos", "Reyes", "Garcia", "Bautista", "Mendoza", "Villanueva", "Ramos", "Torres",
                    "Castillo", "Fernandez", "Gonzales", "Aquino", "Pascual", "Manalo", "Del Rosario", "De Leon", "Salazar",
                    "Flores", "Rivera"],
    },
    "EG": {
        "given": ["Ahmed", "Mohamed", "Mahmoud", "Mostafa", "Khaled", "Omar", "Youssef", "Amr", "Karim", "Tamer", "Hany",
                  "Nour", "Fatma", "Mona", "Sara", "Yasmin", "Heba", "Dina", "Rania", "Aya"],
        "middle": ["Mohamed", "Ahmed", "Mahmoud", "Hassan", "Ibrahim", "Abdel", "Said", "Fathy", "Samir", "Adel", ""],
        "surname": ["El Sayed", "Hassan", "Ibrahim", "Abdelaziz", "Abdelrahman", "Mahmoud", "Ali", "Mostafa", "Farag",
                    "Saleh", "Kamel", "Salem", "Gaber", "Ramadan", "Shaaban", "Fahmy", "Nasser", "Radwan", "Zaki", "Amin"],
    },
    "NP": {
        "given": ["Ram", "Shyam", "Sameer", "Bikash", "Suresh", "Rajesh", "Santosh", "Prakash", "Dipak", "Sunita", "Sita",
                  "Gita", "Anita", "Laxmi", "Kamala"],
        "middle": ["Bahadur", "Kumar", "Prasad", "Devi", "Kumari", "", ""],
        "surname": ["Thapa", "Gurung", "Tamang", "Rai", "Limbu", "Magar", "Shrestha", "Pradhan", "Adhikari", "Karki",
                    "Bhandari", "Khadka", "Basnet", "Pandey", "Sharma"],
    },
    "LK": {
        "given": ["Kiran", "Nuwan", "Chaminda", "Sanath", "Kumara", "Ruwan", "Lasith", "Dinesh", "Nilmini", "Sandya",
                  "Kumari", "Mohamed", "Fathima", "Rizwan"],
        "middle": ["Kumara", "Prasad", "Dilshan", "Nirmal", "", ""],
        "surname": ["Perera", "Fernando", "Silva", "De Silva", "Jayasuriya", "Bandara", "Wickramasinghe", "Rajapaksa",
                    "Dissanayake", "Gunawardena", "Nazeer", "Cassim"],
    },
}


def clean_population(n: int, rng: random.Random) -> List[Dict[str, str]]:
    out = []
    pops = list(POOLS)
    for i in range(n):
        pop = pops[i % len(pops)]
        pool = POOLS[pop]
        mid = rng.choice(pool["middle"])
        name = " ".join(x for x in (rng.choice(pool["given"]), mid, rng.choice(pool["surname"])) if x)
        dob = date(rng.randint(1965, 2002), rng.randint(1, 12), rng.randint(1, 28)).isoformat()
        out.append({"name": name, "dob": dob, "nationality": pop})
    return out


# ------------------------------------------------------------------ benchmark
def run(sample: int, clean: int, seed: int = 7) -> Dict:
    rng = random.Random(seed)
    index = get_index()
    people = [e for e in index.entries if e.record_type == "individual" and latin(e.name) and e.dob_dates]
    targets = rng.sample(people, min(sample, len(people)))

    forms = ["as_listed", "alias", "translit", "reordered", "dropped_middle", "typo"]
    # the same person often sits on several lists; any entry with the same normalized name counts
    by_name: Dict[str, set] = {}
    for x in index.entries:
        by_name.setdefault(normalize(x.name), set()).add(f"{x.source}:{x.dataid}")
    found = Counter()
    top = Counter()
    asked = Counter()
    misses: List[Dict] = []
    t0 = time.time()
    n_screens = 0
    for e in targets:
        base = listed_name(e.name)
        dob = sorted(e.dob_dates)[0].isoformat()
        aliases = [a for a in e.aliases if latin(a)]
        queries = {
            "as_listed": base,
            "alias": listed_name(rng.choice(aliases)) if aliases else None,
            "translit": translit(base, rng),
            "reordered": reorder(base),
            "dropped_middle": drop_middle(base),
            "typo": typo(base, rng),
        }
        key = f"{e.source}:{e.dataid}"
        for form in forms:
            q = queries[form]
            if not q:
                continue
            asked[form] += 1
            r = AMLService.screen_sync(q, dob=dob)
            n_screens += 1
            keys = [f"{m['source']}:{m['dataid']}" for m in r["matches"]]
            same = {key} | by_name.get(normalize(e.name), set())
            if any(k in same for k in keys):
                found[form] += 1
                if keys and keys[0] in same:
                    top[form] += 1
            elif len(misses) < 60:
                misses.append({"form": form, "query": q, "listed": e.name, "source": e.source, "dob": dob,
                               "got": [m["sanctioned_name"] for m in r["matches"][:2]]})
    recall_time = time.time() - t0

    pop = clean_population(clean, rng)
    t1 = time.time()
    fp = Counter()
    fp_high = Counter()
    offenders = Counter()
    fp_examples: List[Dict] = []
    for c in pop:
        r = AMLService.screen_sync(c["name"], dob=c["dob"], nationality=c["nationality"])
        n_screens += 1
        if r["sanctions_match"]:
            fp[c["nationality"]] += 1
            best = r["matches"][0]
            offenders[f"{best['sanctioned_name']} [{best['source']}]"] += 1
            if r["risk_level"].value in ("high", "medium"):
                fp_high[c["nationality"]] += 1
            if len(fp_examples) < 40:
                fp_examples.append({"name": c["name"], "dob": c["dob"], "nationality": c["nationality"],
                                    "best": best["sanctioned_name"], "via": best.get("matched_name"),
                                    "similarity": best["similarity"], "screened_as": best.get("screened_as"),
                                    "dob_agreement": best.get("dob_agreement"), "risk": r["risk_level"].value,
                                    "score": r["risk_score"]})
    fp_time = time.time() - t1

    per_pop = Counter(c["nationality"] for c in pop)
    return {
        "list_version": index.list_version,
        "run_at": date.today().isoformat(),
        "seed": seed,
        "recall": {f: {"asked": asked[f], "found": found[f], "top": top[f],
                       "recall": round(found[f] / asked[f], 4) if asked[f] else None,
                       "top1": round(top[f] / asked[f], 4) if asked[f] else None} for f in forms},
        "recall_sample": len(targets),
        "misses": misses,
        "false_positives": {
            "population": clean,
            "by_nationality": {p: {"names": per_pop[p], "flagged": fp[p], "flagged_medium_or_high": fp_high[p],
                                   "rate": round(fp[p] / per_pop[p], 4), "rate_medium_or_high": round(fp_high[p] / per_pop[p], 4)}
                               for p in sorted(per_pop)},
            "overall_rate": round(sum(fp.values()) / clean, 4),
            "overall_rate_medium_or_high": round(sum(fp_high.values()) / clean, 4),
            "top_offending_entries": offenders.most_common(10),
            "examples": fp_examples,
        },
        "ms_per_screen": round(1000 * (recall_time + fp_time) / max(n_screens, 1), 2),
        "screens": n_screens,
    }


def to_markdown(res: Dict) -> str:
    lines = [f"# Screening benchmark, {res['run_at']}", "",
             f"List version `{res['list_version']}` · seed {res['seed']} · {res['screens']} screens · {res['ms_per_screen']} ms per screen", "",
             f"## Recall on {res['recall_sample']} listed individuals (date of birth supplied)", "",
             "| Name as supplied | Asked | Found | Found at rank 1 | Recall | Top-1 |", "|---|---:|---:|---:|---:|---:|"]
    labels = {"as_listed": "Exactly as listed", "alias": "A listed alias", "translit": "One transliteration change",
              "reordered": "Surname first", "dropped_middle": "Middle token dropped", "typo": "One letter missing"}
    for f, v in res["recall"].items():
        if v["asked"]:
            lines.append(f"| {labels[f]} | {v['asked']} | {v['found']} | {v['top']} | {v['recall']:.1%} | {v['top1']:.1%} |")
    fp = res["false_positives"]
    lines += ["", f"## False positives on {fp['population']} synthetic clean names (date of birth and nationality supplied)", "",
              "| Population | Names | Flagged | Medium or high | Flagged rate | Medium/high rate |", "|---|---:|---:|---:|---:|---:|"]
    for p, v in fp["by_nationality"].items():
        lines.append(f"| {p} | {v['names']} | {v['flagged']} | {v['flagged_medium_or_high']} | {v['rate']:.1%} | {v['rate_medium_or_high']:.1%} |")
    lines.append(f"| **All** | {fp['population']} | {sum(v['flagged'] for v in fp['by_nationality'].values())} | "
                 f"{sum(v['flagged_medium_or_high'] for v in fp['by_nationality'].values())} | {fp['overall_rate']:.1%} | {fp['overall_rate_medium_or_high']:.1%} |")
    if fp["top_offending_entries"]:
        lines += ["", "Most frequently matched list entries:", ""]
        lines += [f"- {name}: {n}" for name, n in fp["top_offending_entries"]]
    if fp["examples"]:
        lines += ["", "Examples:", "", "| Clean name | DOB | Nat | Best match | Via | Sim | DOB | Risk |", "|---|---|---|---|---|---:|---|---|"]
        for x in fp["examples"][:15]:
            via = f"{x['via']}" + (f" (short form {x['screened_as']})" if x.get("screened_as") else "")
            lines.append(f"| {x['name']} | {x['dob']} | {x['nationality']} | {x['best']} | {via} | {x['similarity']} | {x['dob_agreement']} | {x['risk']} {x['score']} |")
    if res["misses"]:
        lines += ["", "## Recall misses (first 15)", "", "| Form | Query | Listed as | Source | Got instead |", "|---|---|---|---|---|"]
        for m in res["misses"][:15]:
            lines.append(f"| {m['form']} | {m['query']} | {m['listed']} | {m['source']} | {'; '.join(m['got']) or '-'} |")
    lines += ["", "Method: `scripts/benchmark_screening.py`. Synthetic names are drawn from pools of common given names and surnames; "
              "a hit on one is counted as a false positive even if a real listed person shares the name, so the rate is an upper bound.", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", type=int, default=600, help="listed individuals to sample for recall")
    ap.add_argument("--clean", type=int, default=3000, help="synthetic clean names for the false-positive rate")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=None, help="directory to write screening_<date>.md and .json")
    args = ap.parse_args()
    res = run(args.sample, args.clean, args.seed)
    md = to_markdown(res)
    print(md)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / f"screening_{res['run_at']}.md").write_text(md, encoding="utf-8")
        (args.out / f"screening_{res['run_at']}.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
        print(f"\nwritten to {args.out}/screening_{res['run_at']}.md and .json")


if __name__ == "__main__":
    main()
