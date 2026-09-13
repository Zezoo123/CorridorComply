"""init_db upgrades an older create_all-managed SQLite database in place."""
import sqlite3


def test_init_db_adds_columns_missing_from_an_older_sqlite_database(tmp_path, monkeypatch):
    from app.db import database
    from app.services import records

    path = tmp_path / "old.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    database.reset_db()
    records._version_cache.clear()
    database.init_db()
    # Simulate a database created before migrations 0003/0004: rebuild the decisions
    # table without the newer columns (SQLite cannot drop a column named in a foreign key).
    con = sqlite3.connect(path)
    newer = {"beneficiary_screening_id", "disposition", "disposition_reason", "disposition_by", "disposition_at"}
    old_cols = [r[1] for r in con.execute("pragma table_info(decisions)") if r[1] not in newer]
    con.execute("ALTER TABLE decisions RENAME TO decisions_old")
    con.execute(f"CREATE TABLE decisions AS SELECT {', '.join(old_cols)} FROM decisions_old WHERE 0")
    con.execute("DROP TABLE decisions_old")
    con.commit()
    assert "beneficiary_screening_id" not in [r[1] for r in con.execute("pragma table_info(decisions)")]
    con.close()

    database.reset_db()
    database.init_db()
    con = sqlite3.connect(path)
    cols = [r[1] for r in con.execute("pragma table_info(decisions)")]
    con.close()
    assert "beneficiary_screening_id" in cols
    database.reset_db()
    records._version_cache.clear()
