# Installing CorridorComply on the firm's own machine

The screening product runs entirely on one computer at the firm. Nothing is sent anywhere: the lists are inside the installed image, the customer file is read from disk, results and the reviewer's dispositions are stored in a folder next to the install, and the web page is reachable only from that computer.

## What you need

- A Mac, Windows or Linux machine with 8 GB of memory and 3 GB of free disk.
- Docker Desktop (Mac, Windows) or Docker Engine (Linux): https://docs.docker.com/desktop/
- Internet for the install itself (it downloads the lists). Not needed afterwards.

## Install

```bash
git clone https://github.com/Zezoo123/CorridorComply.git
cd CorridorComply
scripts/shadow_run.sh install
```

On Windows, run the same commands in Git Bash (installed with Git) or in WSL. The script:

1. writes `.env` with a random login and API key (change them there if you like);
2. builds the image with the lists current that day (UN, Qatar NCTC, OFAC SDN and consolidated, UK OFSI, EU);
3. starts the service on http://127.0.0.1:8010 and opens the screening page.

Log in with the user and password printed by the script (also in `.env`).

## Day to day

| Task | Command |
|---|---|
| Start / stop | `scripts/shadow_run.sh start` / `stop` |
| Is it running | `scripts/shadow_run.sh status` |
| Refresh the lists and re-screen everyone on file | `scripts/shadow_run.sh update` (needs internet for a minute) |
| Start clean (moves the data folder aside, keeps it) | `scripts/shadow_run.sh reset` |
| Logs | `scripts/shadow_run.sh logs` |

Refresh the lists at least weekly, and on the day of any run whose result will be relied on. The list version on every report tells you which day's lists were used.

## Where the data is

Everything the firm produces is in `cc-data/` next to the install: the database (`cc-data/corridorcomply.db`, screenings, dispositions, customers, alerts), the lists (`cc-data/sanctions/`), and the audit log (`cc-data/logs/audit/`). Back up that folder. Deleting it removes every record, so do not, unless the firm's retention rules say so; Law No. 20 of 2019 asks for ten years.

## Setting the firm's name

The printable summary says "Prepared for <name>". Set it once (use the API key from `.env`):

```bash
curl -X PUT -H "X-API-Key: <key>" -H "Content-Type: application/json" \
  -d '{"name": "Firm name as it should appear"}' http://127.0.0.1:8010/api/v1/tenant
```

## Without Docker

For a developer machine: Python 3.10 or newer, then `pip install -r requirements.txt`, `python scripts/update_sanctions.py`, and `UI_USERNAME=... UI_PASSWORD=... uvicorn app.main:app --port 8010`. The same folders apply (`data/` and `app/data/sanctions/` inside the checkout).
