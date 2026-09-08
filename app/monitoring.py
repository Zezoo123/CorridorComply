"""
Re-screen monitored customers against the current list and raise alerts.

Run after each list update, e.g. from cron:
    0 3 * * *  cd /srv && python scripts/update_sanctions.py && python -m app.monitoring rescreen
"""
import json
import sys

from .db.database import init_db, session_scope
from .services.records import rescreen_all, rescreen_tenant


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] != "rescreen":
        print("usage: python -m app.monitoring rescreen [tenant-slug] [--force]")
        return 2
    force = "--force" in argv
    tenants = [a for a in argv[1:] if not a.startswith("--")]
    init_db()
    with session_scope() as s:
        if tenants:
            out = [rescreen_tenant(s, t, only_if_new_version=not force) for t in tenants]
        else:
            out = rescreen_all(s) if not force else [rescreen_tenant(s, r["tenant"], only_if_new_version=False) for r in rescreen_all(s)]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
