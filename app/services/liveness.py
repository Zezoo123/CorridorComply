"""
Liveness: is the selfie a live person, not a photo of a photo or a screen?

We do not build liveness or forgery detection in-house before revenue. This
module defines the interface, a NullProvider that says "not checked", and an
HTTP provider that calls a vendor endpoint configured by environment variables.
The KYC result carries the answer and RiskEngine scores it; the API docs must
say exactly what is and is not detected.

Configuration:
    LIVENESS_PROVIDER = none | http            (default none)
    LIVENESS_URL      = https://vendor/api/liveness
    LIVENESS_API_KEY  = ...
    LIVENESS_TIMEOUT  = 15
"""
from __future__ import annotations

import base64
import io
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class LivenessResult:
    checked: bool                      # False when no provider ran
    live: Optional[bool] = None        # None when not checked or the provider could not decide
    score: Optional[float] = None      # provider's confidence 0-1 when given
    provider: str = "none"
    error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"checked": self.checked, "live": self.live, "score": self.score, "provider": self.provider, "error": self.error}


class LivenessProvider:
    name = "base"

    def check(self, selfie_image) -> LivenessResult:  # PIL.Image.Image
        raise NotImplementedError


class NullProvider(LivenessProvider):
    """No liveness check. The result says so explicitly rather than pretending."""
    name = "none"

    def check(self, selfie_image) -> LivenessResult:
        return LivenessResult(checked=False, provider=self.name)


class HttpProvider(LivenessProvider):
    """Generic vendor adapter: POST {"image": <base64 jpeg>} with a bearer key,
    expect {"live": bool, "score": float}. Adjust `parse` for a specific vendor."""
    name = "http"

    def __init__(self, url: str, api_key: str = "", timeout: float = 15.0):
        self.url, self.api_key, self.timeout = url, api_key, timeout

    def parse(self, payload: Dict[str, Any]) -> LivenessResult:
        live = payload.get("live")
        if live is None and "is_live" in payload:
            live = payload["is_live"]
        score = payload.get("score", payload.get("confidence"))
        return LivenessResult(checked=True, live=bool(live) if live is not None else None,
                              score=float(score) if score is not None else None, provider=self.name, raw=payload)

    def check(self, selfie_image) -> LivenessResult:
        import requests
        buf = io.BytesIO()
        selfie_image.convert("RGB").save(buf, format="JPEG", quality=90)
        body = {"image": base64.b64encode(buf.getvalue()).decode()}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            r = requests.post(self.url, json=body, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            return self.parse(r.json())
        except Exception as e:
            logger.warning(f"Liveness provider failed: {e}")
            return LivenessResult(checked=True, live=None, provider=self.name, error=str(e))


def get_provider() -> LivenessProvider:
    kind = (os.getenv("LIVENESS_PROVIDER") or "none").lower()
    if kind == "http":
        url = os.getenv("LIVENESS_URL", "")
        if not url:
            logger.warning("LIVENESS_PROVIDER=http but LIVENESS_URL is not set; liveness disabled")
            return NullProvider()
        return HttpProvider(url, os.getenv("LIVENESS_API_KEY", ""), float(os.getenv("LIVENESS_TIMEOUT", "15")))
    return NullProvider()
