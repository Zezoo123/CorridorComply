"""
API-key authentication.

Keys are configured with the API_KEYS environment variable as
"tenant_a:key1,tenant_b:key2" or with API_KEYS_FILE pointing at a JSON file
of {"tenant": "key", ...}. Keys are compared by SHA-256 digest. When nothing
is configured the API runs open, for local development only, and logs a
warning at startup.

Generate a key:  python -m app.auth new-key <tenant>
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


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def load_keys() -> Dict[str, str]:
    """Read configured keys (digest -> tenant). Cached after the first call."""
    global _digests
    if _digests is not None:
        return _digests
    mapping: Dict[str, str] = {}
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
    _digests = mapping
    if not mapping:
        logger.warning("No API keys configured (API_KEYS / API_KEYS_FILE): the API is OPEN. Do not run like this outside development.")
    return mapping


def reset_keys() -> None:
    global _digests
    _digests = None


async def require_api_key(request: Request, key: Optional[str] = Depends(_header)) -> str:
    """Dependency: resolves the tenant for a request, or raises 401."""
    keys = load_keys()
    if not keys:
        request.state.tenant = "dev"
        return "dev"
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key header")
    tenant = keys.get(_digest(key))
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    request.state.tenant = tenant
    return tenant


def new_key() -> str:
    return "cc_" + secrets.token_urlsafe(32)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "new-key":
        k = new_key()
        print(f"API key for tenant '{sys.argv[2]}' (store it now; only its hash is kept):\n{k}\n")
        print(f'Configure with:  export API_KEYS="{sys.argv[2]}:{k}"')
    else:
        print("usage: python -m app.auth new-key <tenant>")
