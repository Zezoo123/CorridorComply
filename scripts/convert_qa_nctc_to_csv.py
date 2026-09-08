#!/usr/bin/env python3
"""
Convert Qatar's NCTC "Unified Record of Persons and Entities on the Sanction
List" (Ministry of Interior JSON) to the normalized CSV format.

The unified record holds both the UN Security Council designations as applied
in Qatar (moiListType 0) and Qatar's domestic designations made by Public
Prosecutor order (moiListType 1, reference numbers QLDi/QLDe). QCB AML/CFT
Instructions 10.4 and 18(9) require every financial institution to check both
and to act within 24 hours on a listed person.

Input:  app/data/sanctions/raw/qa_nctc/nctc_*.json (newest)
Output: app/data/sanctions/normalized/qa_nctc/qa_nctc_sanctions_YYYYMMDD.csv (+ _latest symlink)
"""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.dates import parse_dob_text  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(), logging.FileHandler('sanctions_processing.log')])
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / 'app' / 'data' / 'sanctions' / 'raw' / 'qa_nctc'
OUT_DIR = PROJECT_ROOT / 'app' / 'data' / 'sanctions' / 'normalized' / 'qa_nctc'

COLUMN_ORDER = [
    'source', 'source_file', 'dataid', 'reference_number', 'list_type', 'record_type', 'name',
    'first_name', 'middle_name', 'last_name', 'aliases', 'nationalities', 'gender', 'pob_cities',
    'pob_countries', 'dob_dates', 'dob_years', 'addresses', 'id_numbers', 'program', 'comments',
    'listed_on', 'last_updated', 'processing_date',
]

# Nationalities appear in English for UN-derived rows and sometimes in Arabic for domestic ones.
ARABIC_NATIONALITY = {
    'يمني': 'YEMEN', 'قطري': 'QATAR', 'سعودي': 'SAUDI ARABIA', 'مصري': 'EGYPT', 'سوري': 'SYRIA', 'عراقي': 'IRAQ',
    'لبناني': 'LEBANON', 'أردني': 'JORDAN', 'اردني': 'JORDAN', 'فلسطيني': 'PALESTINE', 'سوداني': 'SUDAN',
    'صومالي': 'SOMALIA', 'ليبي': 'LIBYA', 'تونسي': 'TUNISIA', 'جزائري': 'ALGERIA', 'مغربي': 'MOROCCO',
    'باكستاني': 'PAKISTAN', 'هندي': 'INDIA', 'بنغالي': 'BANGLADESH', 'بنغلاديشي': 'BANGLADESH', 'فلبيني': 'PHILIPPINES',
    'أفغاني': 'AFGHANISTAN', 'افغاني': 'AFGHANISTAN', 'إيراني': 'IRAN', 'ايراني': 'IRAN', 'تركي': 'TURKEY',
    'كويتي': 'KUWAIT', 'بحريني': 'BAHRAIN', 'عماني': 'OMAN', 'إماراتي': 'UNITED ARAB EMIRATES', 'اماراتي': 'UNITED ARAB EMIRATES',
    'نيبالي': 'NEPAL', 'سريلانكي': 'SRI LANKA', 'إندونيسي': 'INDONESIA', 'اندونيسي': 'INDONESIA', 'كيني': 'KENYA',
    'نيجيري': 'NIGERIA', 'بريطاني': 'UNITED KINGDOM', 'أمريكي': 'UNITED STATES', 'امريكي': 'UNITED STATES',
}


def clean(v) -> str:
    if v is None:
        return ''
    return ' '.join(str(v).split()).strip()


def nationality(v: str) -> str:
    v = clean(v)
    if not v:
        return ''
    if re.search(r'[؀-ۿ]', v):
        return ARABIC_NATIONALITY.get(v, v)
    return v.upper()


def dob_fields(dob_format: str) -> tuple:
    """'EXACT_1963-07-15_X_X_X', 'APPROXIMATELY_X_1971_X_X', 'BETWEEN_X_X_1960_1965', 'EXACT_15/7/1963;1971___'."""
    text = clean(dob_format).replace('_', ' ').replace('X', ' ')
    dates, years = parse_dob_text(text)
    return '; '.join(d.isoformat() for d in sorted(dates)), '; '.join(str(y) for y in sorted(years))


def convert(items: List[Dict], source_file: str) -> pd.DataFrame:
    today = datetime.now().strftime('%Y-%m-%d')
    rows = []
    for it in items:
        name_en = clean(it.get('fullNameEn'))
        name_ar = clean(it.get('fullNameAr'))
        name = name_en or name_ar
        if not name:
            continue
        aliases: List[str] = []
        for a in re.split(r'[;|]', clean(it.get('aliases', ''))):
            a = clean(a)
            if a and a.upper() != name.upper():
                aliases.append(a)
        if name_ar and name_ar != name and name_ar not in aliases:
            aliases.append(name_ar)  # Arabic-script form; the screener transliterates it
        dob_dates, dob_years = dob_fields(it.get('dobFormat', ''))
        ids = []
        if clean(it.get('qid')):
            ids.append(f"QID: {clean(it.get('qid'))}")
        if clean(it.get('passportNo')):
            ids.append(f"Passport: {clean(it.get('passportNo'))}")
        record_type = 'individual' if str(it.get('typ')) == '1' else 'entity'
        domestic = str(it.get('moiListType')) == '1'
        desig = it.get('designationDTO') or {}
        regime = clean((it.get('sanctionsDTO') or {}).get('sanctionRegimeEn'))
        basis = clean(desig.get('legalBasisAr')) if re.search(r'[A-Za-z]', clean(desig.get('legalBasisAr'))) else clean(desig.get('legalBasisEn'))
        rows.append({
            'source': 'QA_NCTC', 'source_file': source_file, 'dataid': clean(it.get('dataId')),
            'reference_number': clean(it.get('referenceNumber')),
            'list_type': 'Qatar NCTC domestic designation' if domestic else 'Qatar NCTC unified record (UNSC)',
            'record_type': record_type, 'name': name.upper(),
            'first_name': clean(it.get('firstNameEN')).upper() if record_type == 'individual' else '',
            'middle_name': ' '.join(p for p in (clean(it.get('secondNameEN')).upper(), clean(it.get('thirdNameEN')).upper()) if p) if record_type == 'individual' else '',
            'last_name': clean(it.get('fourthNameEN')).upper() if record_type == 'individual' else '',
            'aliases': '; '.join(aliases), 'nationalities': nationality(it.get('nationality')), 'gender': '',
            'pob_cities': '', 'pob_countries': '', 'dob_dates': dob_dates, 'dob_years': dob_years, 'addresses': '',
            'id_numbers': '; '.join(ids), 'program': regime or ('Qatar domestic designation' if domestic else ''),
            'comments': '; '.join(p for p in (basis, clean(desig.get('linkDecEn'))) if p)[:1000],
            'listed_on': clean(it.get('listedOn')), 'last_updated': today, 'processing_date': today,
        })
    df = pd.DataFrame(rows, columns=COLUMN_ORDER)
    logger.info(f"Created {len(df)} NCTC records: {df['record_type'].value_counts().to_dict()}; "
                f"domestic: {(df['list_type'].str.contains('domestic')).sum()}; with QID: {(df['id_numbers'].str.contains('QID')).sum()}")
    return df


def find_input() -> Optional[Path]:
    files = sorted(RAW_DIR.glob('nctc_*.json'), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None


def save_output(df: pd.DataFrame) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"qa_nctc_sanctions_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(out, index=False, encoding='utf-8', quoting=1)
    latest = OUT_DIR / 'qa_nctc_sanctions_latest.csv'
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out.name)
    logger.info(f"Saved {len(df)} records to {out}")
    return out


def main() -> int:
    src = find_input()
    if src is None:
        logger.error(f"No NCTC JSON found in {RAW_DIR}")
        return 1
    data = json.loads(src.read_text(encoding='utf-8'))
    items = data.get('content') if isinstance(data, dict) else data
    if not items:
        logger.error("NCTC file has no 'content' records")
        return 1
    df = convert(items, src.name)
    if df.empty:
        return 1
    save_output(df)
    return 0


if __name__ == '__main__':
    sys.exit(main())
