# Sanctions data

Not tracked in git. `python scripts/update_sanctions.py` fills:

- `raw/{un,ofac,ofac_cons,uk,eu,qa_nctc}/` — files as published
- `raw/internal/` — the firm's own watchlist (uploaded through the app)
- `normalized/<source>/<source>_sanctions_<date>.csv` (+ `_latest` symlink) — common schema
- `combined/combined_sanctions_<timestamp>.csv` — what the screener loads; its checksum is the list version

Override the location with `SANCTIONS_DATA_DIR`.
