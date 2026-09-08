"""
Pytest configuration and shared fixtures.
"""
import pytest
from datetime import datetime
from pathlib import Path


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run slow integration tests that download real data or load ML models",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-slow"):
        return
    skip = pytest.mark.skip(reason="use --run-slow to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


# A small combined sanctions list in the exact schema produced by
# scripts/combine_sanctions.py. Enough variety to exercise matching.
SAMPLE_COMBINED_CSV = """source,source_file,dataid,reference_number,list_type,record_type,name,first_name,middle_name,last_name,aliases,nationalities,gender,pob_cities,pob_countries,dob_dates,dob_years,addresses,id_numbers,program,comments,listed_on,last_updated,processing_date
UN,consolidated.xml,1,QDi.001,UN List,individual,ABDUL RAHMAN YASIN,ABDUL RAHMAN,,YASIN,ABDUL RAHMAN SAID YASIN; TAHA ABDUL RAHMAN,IRAQ,MALE,BLOOMINGTON,UNITED STATES OF AMERICA,1960-04-10,1960,,,AL-QAIDA,,2001-10-17,2020-01-01,2026-01-04
OFAC,sdn.csv,2,SDN-1,SDN,individual,MOHAMMAD REZA NAQDI,MOHAMMAD REZA,,NAQDI,MOHAMMAD REZA NAGHDI; NAQDI MOHAMMAD-REZA,IRAN,MALE,,,1953-03-11,1953,,,IRAN,,2011-02-23,2024-06-01,2026-01-04
OFAC,sdn.csv,3,SDN-2,SDN,entity,BANK MELLAT,,,,MELLAT BANK; BANK-E MELLAT,IRAN,,,,,,TEHRAN,,IRAN,,2007-10-25,2024-06-01,2026-01-04
UK,uk.ods,4,UK-1,UK List,vessel,GRACE 1,,,,ADRIAN DARYA 1,,,,,,,,,SYRIA,,2019-07-04,2024-06-01,2026-01-04
EU,eu.csv,5,EU-1,EU List,individual,MARIA SANTOS,MARIA,,SANTOS,,PHILIPPINES,FEMALE,,,1985-02-14,1985,,,TERRORISM,,2015-01-01,2024-06-01,2026-01-04
"""


@pytest.fixture
def sanctions_data_dir(tmp_path, monkeypatch):
    """Point the loader at a temporary sanctions dataset and clear its cache."""
    from app import config
    from app.services.sanctions_loader import SanctionsLoader

    data_dir = tmp_path / "sanctions"
    combined = data_dir / "combined"
    combined.mkdir(parents=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (combined / f"combined_sanctions_{stamp}.csv").write_text(SAMPLE_COMBINED_CSV)

    monkeypatch.setattr(config, "SANCTIONS_DATA_DIR", data_dir)
    SanctionsLoader.clear_cache()
    yield data_dir
    SanctionsLoader.clear_cache()


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh SQLite database for the test, with the schema created."""
    from app.db import database
    from app.services import records

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    database.reset_db()
    records._version_cache.clear()
    database.init_db()
    yield database
    database.reset_db()
    records._version_cache.clear()


@pytest.fixture
def client(sanctions_data_dir, db, monkeypatch):
    """FastAPI test client with auto-update disabled, test sanctions data and a fresh database."""
    monkeypatch.setenv("SANCTIONS_AUTO_UPDATE_ENABLED", "false")
    from app import config
    monkeypatch.setattr(config, "SANCTIONS_AUTO_UPDATE_ENABLED", False)
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


def add_list_entry(data_dir, *, name, aliases="", record_type="individual", dob="", nationality="", dataid="999"):
    """Write a new combined file containing the sample list plus one extra entry, and drop the cache."""
    import time
    from app.services.sanctions_loader import SanctionsLoader

    time.sleep(0.01)
    row = f"OFAC,sdn.csv,{dataid},SDN-{dataid},SDN,{record_type},{name},,,,{aliases},{nationality},,,,{dob},{dob[:4] if dob else ''},,,TEST,,2026-09-08,2026-09-08,2026-09-08\n"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = data_dir / "combined" / f"combined_sanctions_{stamp}.csv"
    path.write_text(SAMPLE_COMBINED_CSV + row)
    SanctionsLoader.clear_cache()
    return path


AUDIT_LOG = Path("logs/audit/audit.log")


def read_audit_entries():
    """Parse the JSON-lines audit log (empty list if it does not exist yet)."""
    import json

    if not AUDIT_LOG.exists():
        return []
    entries = []
    for line in AUDIT_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries
