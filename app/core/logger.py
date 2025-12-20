# app/core/logger.py
import logging
import json
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
import json
from typing import Dict, Any, Optional
import os

def sanitize_request_payload(payload: Any, max_size: int = 1000) -> Dict[str, Any]:
    """
    Sanitize request payload for logging by removing large binary data.
    
    Args:
        payload: The request payload (can be dict, Pydantic model, etc.)
        max_size: Maximum size for string fields (larger fields will be truncated)
    
    Returns:
        Sanitized dictionary representation of the payload
    """
    if payload is None:
        return {}
    
    # Convert Pydantic models to dict
    if hasattr(payload, 'dict'):
        payload_dict = payload.dict()
    elif hasattr(payload, 'model_dump'):
        payload_dict = payload.model_dump()
    elif isinstance(payload, dict):
        payload_dict = payload
    else:
        # Try to convert to dict
        try:
            payload_dict = dict(payload)
        except (TypeError, ValueError):
            return {"_type": str(type(payload).__name__), "_value": str(payload)[:max_size]}
    
    sanitized = {}
    for key, value in payload_dict.items():
        # Skip large base64 image fields
        if key.endswith('_base64') or key.endswith('_image') or key == 'image':
            sanitized[key] = f"<base64_image_data: {len(str(value))} bytes>" if value else None
        elif isinstance(value, str) and len(value) > max_size:
            sanitized[key] = value[:max_size] + "... (truncated)"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_request_payload(value, max_size)
        elif isinstance(value, list):
            # Limit list size for logging
            if len(value) > 10:
                sanitized[key] = value[:10] + [f"... ({len(value) - 10} more items)"]
            else:
                sanitized[key] = [sanitize_request_payload(item, max_size) if isinstance(item, dict) else item for item in value]
        else:
            sanitized[key] = value
    
    return sanitized

class JsonFormatter(logging.Formatter):
    """Custom formatter that outputs JSON strings with timestamps in ISO format."""
    
    def format(self, record):
        # Create a dictionary with the log record data
        log_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add any extra fields from record.__dict__ that aren't standard log record attributes
        standard_attrs = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 
            'filename', 'funcName', 'levelname', 'levelno', 'lineno', 
            'module', 'msecs', 'message', 'msg', 'name', 'pathname', 
            'process', 'processName', 'relativeCreated', 'stack_info', 
            'thread', 'threadName'
        }
        
        # Add all non-standard attributes to the log record
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                log_record[key] = value
        
        # Handle exceptions
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_record, ensure_ascii=False, default=str)

def setup_logging():
    """Configure logging for the application with JSON formatting."""
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Set up the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Create formatters
    json_formatter = JsonFormatter()
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    
    # File handler for application logs (rotates when it reaches 5MB, keeps 3 backup files)
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(json_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to the root logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Set up audit log directory
    audit_dir = Path("logs/audit")
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a custom handler that ensures directory exists during rotation
    class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
        """TimedRotatingFileHandler that ensures directory exists before rotation."""
        
        def doRollover(self):
            """Override to ensure directory exists before rotation."""
            # Ensure directory exists
            dir_name = os.path.dirname(self.baseFilename)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
            # Call parent rollover
            super().doRollover()
    
    # Configure audit logger with daily rotation
    audit_handler = SafeTimedRotatingFileHandler(
        'logs/audit/audit.log',
        when='midnight',
        interval=1,
        backupCount=30,  # Keep audit logs for 30 days
        encoding='utf-8'
    )
    audit_handler.setFormatter(json_formatter)
    audit_handler.setLevel(logging.INFO)
    
    # Configure the audit logger
    audit_logger = logging.getLogger('audit')
    audit_logger.setLevel(logging.INFO)
    # Remove any existing handlers to prevent duplicate logs
    if audit_logger.handlers:
        audit_logger.handlers.clear()
    audit_logger.addHandler(audit_handler)
    audit_logger.propagate = False
    
    # Configure uvicorn loggers to use our formatter
    for name in ['uvicorn', 'uvicorn.error', 'uvicorn.access']:
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
    
    logging.info("Logging setup complete", extra={'service': 'corridorcomply'})

def log_audit_event(event_type: str, data: Dict[str, Any], request: Any = None, request_payload: Optional[Any] = None):
    """
    Log an audit event with structured data.
    
    Args:
        event_type: Type of event (e.g., 'kyc_verification', 'aml_screening')
        data: Dictionary containing event-specific data (risk score, match summary, etc.)
        request: Optional FastAPI request object for request metadata
        request_payload: Optional request payload to include in audit log (will be sanitized)
    """
    audit_logger = logging.getLogger('audit')
    
    log_data = {
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        **data
    }
    
    # Add sanitized request payload if provided
    if request_payload is not None:
        log_data['request_payload'] = sanitize_request_payload(request_payload)
    
    # Add request metadata if available
    if request:
        log_data.update({
            'request_id': request.headers.get('X-Request-ID'),
            'client_ip': request.client.host if request.client else None,
            'user_agent': request.headers.get('user-agent'),
            'method': request.method,
            'url': str(request.url),
        })
    
    audit_logger.info("Audit event", extra=log_data)