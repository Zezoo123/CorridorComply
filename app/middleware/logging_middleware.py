from fastapi import Request, Response
import time
import uuid
import logging
from typing import Callable

logger = logging.getLogger(__name__)


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:8]}"


async def log_requests_middleware(request: Request, call_next: Callable) -> Response:
    """Log every request and response without recording bodies or headers.

    Request payloads contain identity documents and personal data, so only
    metadata is logged here. The audit log records a sanitized payload.
    """
    request_id = request.headers.get("X-Request-ID") or new_request_id()
    request.state.request_id = request_id

    logger.info(
        "Incoming request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown",
        },
    )

    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(
            f"Request failed: {str(e)}",
            extra={"request_id": request_id, "method": request.method, "path": request.url.path},
            exc_info=True,
        )
        raise

    process_time = time.time() - start_time
    logger.info(
        "Request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time * 1000, 1),
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response
