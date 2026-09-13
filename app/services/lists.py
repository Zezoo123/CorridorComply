"""
List management inside the app: the firm's internal watchlist and rebuilding
the combined file. Mirrors scripts/combine_sanctions.py but honours
SANCTIONS_DATA_DIR so it works in tests and on any deployment.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from ..core.dates import parse_dob_text
from .sanctions_loader import SanctionsLoader

logger = logging.getLogger(__name__)

COLUMN_ORDER = [
    'source', 'source_file', 'dataid', 'reference_number', 'list_type', 'record_type', 'name',
    'first_name', 'middle_name', 'last_name', 'aliases', 'nationalities', 'gender', 'pob_cities',
    'pob_countries', 'dob_dates', 'dob_years', 'addresses', 'id_numbers', 'program', 'comments',
    'listed_on', 'last_updated', 'processing_date',
]
TYPES = {'person': 'individual', 'individual': 'individual', 'entity': 'entity', 'company': 'entity',
         'organisation': 'entity', 'organization': 'entity', 'vessel': 'vessel', 'ship': 'vessel'}


def data_dir() -> Path:
    from ..config import SANCTIONS_DATA_DIR
    return Path(SANCTIONS_DATA_DIR)


# ------------------------------------------------------------ internal list
def parse_internal_csv(content: bytes) -> List[Dict[str, str]]:
    text = content.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = []
    for raw in reader:
        rows.append({(k or "").strip().lower().replace(" ", "_"): (v or "").strip() for k, v in raw.items() if k is not None})
    return rows


def internal_rows_to_frame(rows: List[Dict[str, str]], source_file: str) -> pd.DataFrame:
    today = datetime.now().strftime('%Y-%m-%d')
    out = []
    for i, r in enumerate(rows, 1):
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
    return pd.DataFrame(out, columns=COLUMN_ORDER)


def install_internal_watchlist(content: bytes, filename: str = "internal.csv") -> Dict[str, object]:
    """Store the firm's watchlist, normalise it, rebuild the combined list, reload the screener."""
    rows = parse_internal_csv(content)
    if not rows or not any((r.get("name") or r.get("full_name")) for r in rows):
        raise ValueError("The file needs a header row with a 'name' column and at least one row")
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    raw_dir = data_dir() / "raw" / "internal"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"internal_{stamp}.csv"
    raw_path.write_bytes(content)
    df = internal_rows_to_frame(rows, raw_path.name)
    out_dir = data_dir() / "normalized" / "internal"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"internal_sanctions_{stamp}.csv"
    df.to_csv(out, index=False, encoding='utf-8', quoting=1)
    latest = out_dir / "internal_sanctions_latest.csv"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out.name)
    combined = rebuild_combined()
    return {"entries": int(len(df)), "file": raw_path.name, "combined_file": combined.name if combined else None,
            "list_version": SanctionsLoader.current_version()}


def internal_watchlist_status() -> Dict[str, object]:
    latest = data_dir() / "normalized" / "internal" / "internal_sanctions_latest.csv"
    if not latest.exists():
        return {"present": False, "entries": 0}
    df = pd.read_csv(latest, dtype=str, keep_default_na=False)
    return {"present": True, "entries": int(len(df)), "file": latest.resolve().name,
            "updated": datetime.fromtimestamp(latest.resolve().stat().st_mtime).isoformat()}


# ------------------------------------------------------------ combine
def rebuild_combined(keep: int = 3) -> Optional[Path]:
    """Concatenate every normalized/*/*_latest.csv into a new combined file and reload."""
    base = data_dir()
    normalized = base / "normalized"
    frames = []
    if normalized.exists():
        for source_dir in sorted(normalized.iterdir()):
            if not source_dir.is_dir():
                continue
            latest = next(source_dir.glob("*_latest.csv"), None)
            if latest is None:
                continue
            df = pd.read_csv(latest, dtype=str, keep_default_na=False, encoding="utf-8")
            df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
            if "source" not in df.columns:
                df["source"] = source_dir.name.upper()
            frames.append(df)
    # If the only normalized source is the internal list (or none), keep the public
    # lists from the current combined file rather than dropping them.
    public_sources = {str(f["source"].iloc[0]) for f in frames if len(f) and str(f["source"].iloc[0]) != "INTERNAL"}
    if not public_sources:
        try:
            current = SanctionsLoader.load(SanctionsLoader.current_path()) if SanctionsLoader.current_path() else None
        except Exception:
            current = None
        if current is not None and len(current):
            keep_cols = [c for c in current.columns if c not in ("updated_at", "search_name", "search_aliases")]
            frames.insert(0, current[current["source"] != "INTERNAL"][keep_cols].astype(str))
    if not frames:
        logger.warning("rebuild_combined: no lists found")
        return None
    combined = pd.concat(frames, ignore_index=True)
    combined["id"] = combined.index + 1
    out_dir = base / "combined"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"combined_sanctions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    combined.to_csv(out, index=False, encoding="utf-8", quoting=1)
    latest = out_dir / "combined_sanctions_latest.csv"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out.name)
    files = sorted((f for f in out_dir.glob("combined_sanctions_*.csv") if not f.is_symlink()),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        old.unlink(missing_ok=True)
    SanctionsLoader.clear_cache()
    logger.info(f"Combined list rebuilt: {len(combined)} rows -> {out.name}")
    return out
