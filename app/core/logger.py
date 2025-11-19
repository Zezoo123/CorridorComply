"""
Audit logging utilities
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from app import config


def ensure_audit_dir():
    """Ensure audit log directory exists"""
    Path(config.AUDIT_LOG_DIR).mkdir(parents=True, exist_ok=True)


def log_audit_event(
    request_id: str,
    check_type: str,
    action: str,
    result: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Log an audit event to JSON file
    
    Args:
        request_id: Unique request identifier
        check_type: Type of check (kyc, aml, risk)
        action: Action performed
        result: Result data
        metadata: Additional metadata
    """
    ensure_audit_dir()
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
        "check_type": check_type,
        "action": action,
        "result": result,
        "metadata": metadata if metadata != None else {}
    }
    
    # Write to daily log file
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = Path(config.AUDIT_LOG_DIR) / f"audit_{date_str}.jsonl"
    
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

