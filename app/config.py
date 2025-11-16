"""
Application configuration
"""
from pathlib import Path
from typing import List

# Audit logging
AUDIT_LOG_DIR = "./logs/audit"

# CORS
CORS_ORIGINS: List[str] = ["*"]

