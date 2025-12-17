# app/core/logger.py
import logging
import json
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
import json
from typing import Dict, Any

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
    
    # Configure audit logger with daily rotation
    audit_handler = TimedRotatingFileHandler(
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

def log_audit_event(event_type: str, data: Dict[str, Any], request: Any = None):
    """
    Log an audit event with structured data.
    
    Args:
        event_type: Type of event (e.g., 'kyc_verification', 'aml_screening')
        data: Dictionary containing event-specific data
        request: Optional FastAPI request object for request metadata
    """
    audit_logger = logging.getLogger('audit')
    
    log_data = {
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        **data
    }
    
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