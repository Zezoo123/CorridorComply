"""
API-key authentication.

Keys live in the database (api_keys table) and can also be configured with
the API_KEYS environment variable as "tenant_a:key1,tenant_b:key2" or with
API_KEYS_FILE pointing at a JSON file of {"tenant": "key", ...}. Keys are
compared by SHA-256 digest; the plain key is never stored. When no key is
configured anywhere the API runs open, for local development only, and logs
a warning at startup.

Generate and store a key:   python -m app.auth new-key <tenant> [label]
Revoke a key:               python -m app.auth revoke <prefix>
List keys:                  python -m app.auth list
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import sys
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_digests: Optional[Dict[str, str]] = None  # sha256(key) -> tenant
_configured: bool = False                   # any key ever configured (env, file or DB, including revoked)


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _db_keys() -> tuple:
    """(active keys from the api_keys table as digest -> tenant slug, whether any key row exists)."""
    try:
        from sqlalchemy import func, select
        from .db.database import init_db, session_scope
        from .db.models import ApiKey, Tenant
        init_db()
        with session_scope() as s:
            rows = s.execute(select(ApiKey.key_hash, Tenant.slug).join(Tenant).where(ApiKey.revoked_at.is_(None))).all()
            total = s.scalar(select(func.count(ApiKey.id))) or 0
        return {h: slug for h, slug in rows}, total > 0
    except Exception as e:  # pragma: no cover - DB unavailable
        logger.warning(f"Could not read API keys from the database: {e}")
        return {}, False


def load_keys() -> Dict[str, str]:
    """All active keys (digest -> tenant). Cached after the first call; reset_keys() refreshes."""
    global _digests, _configured
    if _digests is not None:
        return _digests
    db_mapping, db_has_rows = _db_keys()
    mapping: Dict[str, str] = dict(db_mapping)
    raw = os.getenv("API_KEYS", "")
    for part in raw.split(","):
        if ":" in part:
            tenant, key = part.split(":", 1)
            if tenant.strip() and key.strip():
                mapping[_digest(key.strip())] = tenant.strip()
    path = os.getenv("API_KEYS_FILE")
    if path and os.path.exists(path):
        with open(path) as f:
            for tenant, key in json.load(f).items():
                mapping[_digest(str(key))] = str(tenant)
    _configured = bool(mapping) or db_has_rows
    _digests = mapping
    if not _configured:
        logger.warning("No API keys configured (API_KEYS / API_KEYS_FILE / api_keys table): the API is OPEN. "
                       "Create one with: python -m app.auth new-key <tenant>")
    return mapping


def is_open() -> bool:
    """True only when no key has ever been configured anywhere."""
    load_keys()
    return not _configured


def reset_keys() -> None:
    global _digests, _configured
    _digests, _configured = None, False


async def require_api_key(request: Request, key: Optional[str] = Depends(_header)) -> str:
    """Dependency: resolves the tenant for a request, or raises 401."""
    keys = load_keys()
    if is_open():
        from .config import DEFAULT_TENANT
        request.state.tenant = DEFAULT_TENANT
        return DEFAULT_TENANT
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    tenant = keys.get(_digest(key))
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    request.state.tenant = tenant
    return tenant


def new_key() -> str:
    return "cc_" + secrets.token_urlsafe(32)


def create_key(tenant_slug: str, label: str = "", sandbox: bool = False) -> str:
    """Create a tenant if needed, store a new key's hash, return the plain key once."""
    from .db.database import init_db, session_scope
    from .db.models import ApiKey
    from .services.records import get_or_create_tenant
    init_db()
    key = new_key()
    with session_scope() as s:
        tenant = get_or_create_tenant(s, tenant_slug)
        s.add(ApiKey(tenant_id=tenant.id, key_hash=_digest(key), prefix=key[:10], label=label, sandbox=sandbox))
    reset_keys()
    return key


def revoke_key(prefix: str) -> int:
    from datetime import datetime
    from sqlalchemy import select
    from .db.database import init_db, session_scope
    from .db.models import ApiKey
    init_db()
    with session_scope() as s:
        rows = list(s.scalars(select(ApiKey).where(ApiKey.prefix == prefix, ApiKey.revoked_at.is_(None))))
        for r in rows:
            r.revoked_at = datetime.utcnow()
    reset_keys()
    return len(rows)


def _cli(argv) -> int:
    if len(argv) >= 2 and argv[0] == "new-key":
        k = create_key(argv[1], label=argv[2] if len(argv) > 2 else "")
        print(f"API key for tenant '{argv[1]}' (shown once; only its hash is stored):\n{k}")
        return 0
    if len(argv) == 2 and argv[0] == "revoke":
        n = revoke_key(argv[1])
        print(f"revoked {n} key(s) with prefix {argv[1]}")
        return 0 if n else 1
    if argv and argv[0] == "list":
        from sqlalchemy import select
        from .db.database import init_db, session_scope
        from .db.models import ApiKey, Tenant
        init_db()
        with session_scope() as s:
            for k, slug in s.execute(select(ApiKey, Tenant.slug).join(Tenant)).all():
                state = "revoked" if k.revoked_at else "active"
                print(f"{k.prefix}…  {slug:20s} {state:8s} {k.label}")
        return 0
    print("usage: python -m app.auth new-key <tenant> [label] | revoke <prefix> | list")
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
