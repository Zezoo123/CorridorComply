#!/usr/bin/env python3
"""
Convert the firm's own watchlist to the normalized CSV format (source INTERNAL).

Input: app/data/sanctions/raw/internal/*.csv, newest first. Columns (header row,
case-insensitive; only `name` is required):

    name, aliases, type, dob, nationality, id_numbers, reason, reference, listed_on

- aliases, id_numbers: separate several with ';'
- type: person | entity | vessel (default person)
- dob: YYYY-MM-DD, or a year
- nationality: ISO code or country name

Output: app/data/sanctions/normalized/internal/internal_sanctions_YYYYMMDD.csv (+ _latest symlink)
"""
from __future__ import annotations

import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.dates import parse_dob_text  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / 'app' / 'data' / 'sanctions' / 'raw' / 'internal'
OUT_DIR = PROJECT_ROOT / 'app' / 'data' / 'sanctions' / 'normalized' / 'internal'

COLUMN_ORDER = [
    'source', 'source_file', 'dataid', 'reference_number', 'list_type', 'record_type', 'name',
    'first_name', 'middle_name', 'last_name', 'aliases', 'nationalities', 'gender', 'pob_cities',
    'pob_countries', 'dob_dates', 'dob_years', 'addresses', 'id_numbers', 'program', 'comments',
    'listed_on', 'last_updated', 'processing_date',
]
TYPES = {'person': 'individual', 'individual': 'individual', 'entity': 'entity', 'company': 'entity',
         'organisation': 'entity', 'organization': 'entity', 'vessel': 'vessel', 'ship': 'vessel'}


def _norm_header(h: str) -> str:
    return (h or '').strip().lower().replace(' ', '_')


def convert_rows(rows: List[Dict[str, str]], source_file: str) -> pd.DataFrame:
    today = datetime.now().strftime('%Y-%m-%d')
    out = []
    for i, raw in enumerate(rows, 1):
        r = {_norm_header(k): (v or '').strip() for k, v in raw.items() if k is not None}
        name = r.get('name') or r.get('full_name') or ''
        if not name:
            continue
        dates, years = parse_dob_text(r.get('dob', ''))
        nat = r.get('nationality') or r.get('country') or ''
        out.append({
            'source': 'INTERNAL', 'source_file': source_file, 'dataid': r.get('reference') or f'INT-{i}',
            'reference_number': r.get('reference') or f'INT-{i}', 'list_type': 'Internal watchlist',
            'record_type': TYPES.get((r.get('type') or 'person').lower(), 'individual'), 'name': name.upper(),
            'first_name': '', 'middle_name': '', 'last_name': '',
            'aliases': '; '.join(a.strip().upper() for a in (r.get('aliases') or '').split(';') if a.strip()),
            'nationalities': nat.upper(), 'gender': '', 'pob_cities': '', 'pob_countries': '',
            'dob_dates': '; '.join(d.isoformat() for d in sorted(dates)), 'dob_years': '; '.join(str(y) for y in sorted(years)),
            'addresses': '', 'id_numbers': '; '.join(x.strip() for x in (r.get('id_numbers') or '').split(';') if x.strip()),
            'program': 'INTERNAL', 'comments': (r.get('reason') or '')[:1000],
            'listed_on': r.get('listed_on') or today, 'last_updated': today, 'processing_date': today,
        })
    df = pd.DataFrame(out, columns=COLUMN_ORDER)
    logger.info(f"Internal watchlist: {len(df)} entries from {source_file}")
    return df


def convert_file(path: Path) -> pd.DataFrame:
    with open(path, newline='', encoding='utf-8-sig') as f:
        sample = f.read(4096); f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(f, dialect=dialect))
    return convert_rows(rows, path.name)


def save_output(df: pd.DataFrame) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"internal_sanctions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(out, index=False, encoding='utf-8', quoting=1)
    latest = OUT_DIR / 'internal_sanctions_latest.csv'
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out.name)
    for old in sorted(OUT_DIR.glob('internal_sanctions_2*.csv'), key=lambda f: f.stat().st_mtime, reverse=True)[3:]:
        old.unlink(missing_ok=True)
    return out


def main() -> int:
    files = sorted(RAW_DIR.glob('*.csv'), key=lambda f: f.stat().st_mtime, reverse=True) if RAW_DIR.exists() else []
    if not files:
        logger.info(f"No internal watchlist in {RAW_DIR}; nothing to do")
        return 0
    df = convert_file(files[0])
    save_output(df)
    return 0


if __name__ == '__main__':
    sys.exit(main())
