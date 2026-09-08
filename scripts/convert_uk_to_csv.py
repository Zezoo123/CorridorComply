#!/usr/bin/env python3
"""
Convert the UK sanctions list to the normalized CSV format.

Preferred input: the OFSI consolidated list (ConList.csv), which carries
dates of birth, nationalities, name variants (one row per alias, grouped by
Group ID), identity documents and addresses.

Fallback input: the .ods export from the UK sanctions search service, which
has only names, regime and type.

Output: app/data/sanctions/normalized/uk/uk_sanctions_YYYYMMDD.csv plus a
uk_sanctions_latest.csv symlink.
"""
from __future__ import annotations

import logging
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(), logging.FileHandler('sanctions_processing.log')])
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / 'app' / 'data' / 'sanctions' / 'raw' / 'uk'
OUT_DIR = PROJECT_ROOT / 'app' / 'data' / 'sanctions' / 'normalized' / 'uk'

COLUMN_ORDER = [
    'source', 'source_file', 'dataid', 'reference_number', 'list_type', 'record_type', 'name',
    'first_name', 'middle_name', 'last_name', 'aliases', 'nationalities', 'gender', 'pob_cities',
    'pob_countries', 'dob_dates', 'dob_years', 'addresses', 'id_numbers', 'program', 'comments',
    'listed_on', 'last_updated', 'processing_date',
]

GROUP_TYPE = {'individual': 'individual', 'entity': 'entity', 'ship': 'vessel'}


def clean(text) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ''
    text = unicodedata.normalize('NFKC', str(text))
    return ' '.join(text.split()).strip()


def upper_clean(text) -> str:
    return clean(text).upper()


def uk_date(value: str) -> Optional[str]:
    """dd/mm/yyyy -> yyyy-mm-dd; '00/00/1994' -> None (year only)."""
    m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', clean(value))
    if not m or m.group(1) == '00' or m.group(2) == '00':
        return None
    d, mo, y = m.groups()
    try:
        return datetime(int(y), int(mo), int(d)).strftime('%Y-%m-%d')
    except ValueError:
        return None


def uk_year(value: str) -> Optional[str]:
    m = re.search(r'(\d{4})$', clean(value))
    return m.group(1) if m else None


def assemble_name(row: pd.Series) -> str:
    """Name 1..5 are given names in order; Name 6 is the surname / entity name."""
    parts = [clean(row.get(f'Name {i}', '')) for i in (1, 2, 3, 4, 5)]
    surname = clean(row.get('Name 6', ''))
    return ' '.join(p for p in parts + [surname] if p)


# ----------------------------------------------------------------- ConList
def load_conlist(path: Path) -> pd.DataFrame:
    logger.info(f"Loading OFSI ConList from {path}")
    df = pd.read_csv(path, skiprows=1, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    df.columns = [c.strip() for c in df.columns]
    logger.info(f"Loaded {len(df)} rows, {df['Group ID'].nunique()} groups")
    return df


def normalize_conlist(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    today = datetime.now().strftime('%Y-%m-%d')
    records: List[Dict[str, str]] = []
    for group_id, g in df.groupby('Group ID', sort=False):
        primary_rows = g[g['Alias Type'].str.strip().str.lower() == 'primary name']
        primary = primary_rows.iloc[0] if len(primary_rows) else g.iloc[0]
        name = upper_clean(assemble_name(primary))
        if not name:
            continue
        aliases: List[str] = []
        for _, r in g.iterrows():
            n = upper_clean(assemble_name(r))
            if n and n != name and n not in aliases:
                aliases.append(n)
            nl = clean(r.get('Name Non-Latin Script', ''))
            if nl and nl not in aliases:
                aliases.append(nl)

        dob_dates, dob_years = set(), set()
        for v in g['DOB']:
            if not clean(v):
                continue
            full = uk_date(v)
            if full:
                dob_dates.add(full)
            y = uk_year(v)
            if y:
                dob_years.add(y)

        nationalities = sorted({upper_clean(v) for v in g['Nationality'] if clean(v)})
        pob_cities = sorted({upper_clean(v) for v in g['Town of Birth'] if clean(v)})
        pob_countries = sorted({upper_clean(v) for v in g['Country of Birth'] if clean(v)})
        ids = []
        for col, label in (('Passport Number', 'Passport'), ('National Identification Number', 'National ID')):
            for v in g[col]:
                v = clean(v)
                if v and f'{label}: {v}' not in ids:
                    ids.append(f'{label}: {v}')
        addresses = []
        for _, r in g.iterrows():
            parts = [clean(r.get(f'Address {i}', '')) for i in range(1, 7)] + [clean(r.get('Post/Zip Code', '')), clean(r.get('Country', ''))]
            addr = ', '.join(p for p in parts if p)
            if addr and addr not in addresses:
                addresses.append(addr)
        genders = {clean(m.group(1)) for v in g['Other Information'] for m in [re.search(r'\(Gender\):\s*(\w+)', str(v))] if m}
        regimes = sorted({clean(v) for v in g['Regime'] if clean(v)})
        listed_on = min((clean(v) for v in g['Listed On'] if clean(v)), default='')
        last_updated = max((clean(v) for v in g['Last Updated'] if clean(v)), default='')
        record_type = GROUP_TYPE.get(clean(primary.get('Group Type', '')).lower(), 'entity')

        records.append({
            'source': 'UK', 'source_file': source_file, 'dataid': str(group_id), 'reference_number': str(group_id),
            'list_type': 'UK Sanctions List', 'record_type': record_type, 'name': name,
            'first_name': upper_clean(primary.get('Name 1', '')) if record_type == 'individual' else '',
            'middle_name': ' '.join(p for p in (upper_clean(primary.get(f'Name {i}', '')) for i in (2, 3, 4, 5)) if p) if record_type == 'individual' else '',
            'last_name': upper_clean(primary.get('Name 6', '')) if record_type == 'individual' else '',
            'aliases': '; '.join(aliases), 'nationalities': '; '.join(nationalities),
            'gender': next(iter(genders), '').upper(), 'pob_cities': '; '.join(pob_cities),
            'pob_countries': '; '.join(pob_countries), 'dob_dates': '; '.join(sorted(dob_dates)),
            'dob_years': '; '.join(sorted(dob_years)), 'addresses': '; '.join(addresses),
            'id_numbers': '; '.join(ids), 'program': '; '.join(regimes),
            'comments': clean(primary.get('Other Information', ''))[:2000],
            'listed_on': _iso(listed_on), 'last_updated': _iso(last_updated), 'processing_date': today,
        })
    out = pd.DataFrame(records, columns=COLUMN_ORDER)
    logger.info(f"Created {len(out)} normalized UK records: {out['record_type'].value_counts().to_dict()}")
    return out


def _iso(uk: str) -> str:
    return uk_date(uk) or uk


# --------------------------------------------------------------- ODS fallback
def load_ods_fallback(path: Path, source_file: str) -> pd.DataFrame:
    logger.warning("Using the search-service ODS export: no DOB, nationality or aliases in this source")
    df = pd.read_excel(path, engine='odf')
    df.columns = [str(c).strip() for c in df.columns]
    today = datetime.now().strftime('%Y-%m-%d')
    records = []
    for _, r in df.iterrows():
        name = upper_clean(r.get('Name', ''))
        if not name:
            continue
        records.append({
            'source': 'UK', 'source_file': source_file, 'dataid': clean(r.get('Unique ID', '')),
            'reference_number': clean(r.get('OFSI Group ID', '')), 'list_type': 'UK Sanctions List',
            'record_type': GROUP_TYPE.get(clean(r.get('Type', '')).lower(), 'entity'), 'name': name,
            'first_name': '', 'middle_name': '', 'last_name': '', 'aliases': '', 'nationalities': '',
            'gender': '', 'pob_cities': '', 'pob_countries': '', 'dob_dates': '', 'dob_years': '',
            'addresses': '', 'id_numbers': '', 'program': clean(r.get('Regime Name', '')),
            'comments': clean(r.get('Sanctions Imposed', '')), 'listed_on': _iso(clean(r.get('Date Designated', ''))),
            'last_updated': today, 'processing_date': today,
        })
    return pd.DataFrame(records, columns=COLUMN_ORDER)


# ---------------------------------------------------------------------- main
def find_input() -> Optional[Path]:
    conlists = sorted(RAW_DIR.glob('ConList*.csv'), key=lambda f: f.stat().st_mtime, reverse=True)
    if conlists:
        return conlists[0]
    ods = sorted(RAW_DIR.glob('*.ods'), key=lambda f: f.stat().st_mtime, reverse=True)
    return ods[0] if ods else None


def save_output(df: pd.DataFrame) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"uk_sanctions_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(out, index=False, encoding='utf-8', quoting=1)
    latest = OUT_DIR / 'uk_sanctions_latest.csv'
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out.name)
    logger.info(f"Saved {len(df)} records to {out}")
    return out


def main() -> int:
    src = find_input()
    if src is None:
        logger.error(f"No UK input found in {RAW_DIR} (expected ConList*.csv or *.ods)")
        return 1
    if src.suffix.lower() == '.csv':
        df = normalize_conlist(load_conlist(src), src.name)
    else:
        df = load_ods_fallback(src, src.name)
    if df.empty:
        logger.error("No UK records produced")
        return 1
    save_output(df)
    return 0


if __name__ == '__main__':
    sys.exit(main())
