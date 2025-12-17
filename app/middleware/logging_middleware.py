from fastapi import Request, Response
import time
import logging
from typing import Callable
import json

logger = logging.getLogger(__name__)

async def log_requests_middleware(request: Request, call_next: Callable) -> Response:
    """Middleware to log all API requests and responses"""
    # Generate a unique request ID
    request_id = request.headers.get('X-Request-ID') or f"req_{str(id(request))[-6:]}"
    
    # Log request details
    request_body = {}
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            request_body = await request.json()
        except:
            request_body = {"info": "Could not parse request body as JSON"}
    
    # Log the request
    logger.info(
        "Incoming request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client": f"{request.client.host}:{request.client.port}" if request.client else "unknown",
            "headers": dict(request.headers),
            "body": request_body
        }
    )
    
    # Process the request and time it
    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        # Log the exception
        logger.error(
            f"Request failed: {str(e)}",
            extra={
                "request_id": request_id,
                "error": str(e),
                "traceback": str(e.__traceback__) if hasattr(e, '__traceback__') else None
            },
            exc_info=True
        )
        raise
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log the response
    logger.info(
        "Request completed",
        extra={
            "request_id": request_id,
            "status_code": response.status_code,
            "process_time": f"{process_time:.4f}s",
            "response_headers": dict(response.headers)
        }
    )
    
    # Add the request ID to the response headers
    response.headers["X-Request-ID"] = request_id
    return response