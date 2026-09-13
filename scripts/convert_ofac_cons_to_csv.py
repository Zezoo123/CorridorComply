#!/usr/bin/env python3
"""
Convert OFAC's Consolidated (non-SDN) Sanctions List to the normalized format.

The consolidated list carries persons and entities subject to programmes that
are not SDN designations: sectoral sanctions (SSI), Correspondent Account or
Payable-Through Account (CAPTA), Non-SDN Menu-Based (NS-MBS), Foreign Sanctions
Evaders (FSE) and others. Same three-file layout as the SDN list
(cons_prim.csv, cons_alt.csv, cons_add.csv), so the SDN converter is reused.

Input:  app/data/sanctions/raw/ofac_cons/{cons_prim,cons_alt,cons_add}.csv
Output: app/data/sanctions/normalized/ofac_cons/ofac_cons_sanctions_YYYYMMDD.csv (+ _latest symlink)
"""
from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import convert_ofac_to_csv as ofac  # noqa: E402

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "app" / "data" / "sanctions" / "raw" / "ofac_cons"
OUT_DIR = PROJECT_ROOT / "app" / "data" / "sanctions" / "normalized" / "ofac_cons"


def main() -> int:
    prim, alt, add = RAW_DIR / "cons_prim.csv", RAW_DIR / "cons_alt.csv", RAW_DIR / "cons_add.csv"
    if not prim.exists():
        logger.error(f"Input file not found: {prim}")
        return 1
    sdn_df = ofac.load_sdn_data(prim)
    alt_df = ofac.load_alt_data(alt) if alt.exists() else ofac.pd.DataFrame()
    add_df = ofac.load_add_data(add) if add.exists() else ofac.pd.DataFrame()
    if sdn_df.empty:
        logger.error("No records in cons_prim.csv")
        return 1
    df = ofac.create_normalized_ofac_data(sdn_df, alt_df, add_df)
    df["source"] = "OFAC_CONS"
    df["source_file"] = "cons_prim.csv"
    df["list_type"] = "OFAC Consolidated (non-SDN) List"
    today = date.today().isoformat()
    df["processing_date"] = today
    df["last_updated"] = today
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"ofac_cons_sanctions_{date.today().strftime('%Y%m%d')}.csv"
    ofac.save_output(df, out)
    latest = OUT_DIR / "ofac_cons_sanctions_latest.csv"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out.name)
    logger.info(f"OFAC consolidated list: {len(df)} records -> {out}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    sys.exit(main())
