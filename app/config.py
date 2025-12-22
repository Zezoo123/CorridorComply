"""
Application configuration
"""
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

# Base directories
BASE_DIR = Path(__file__).parent.parent

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Audit logging
AUDIT_LOG_DIR = BASE_DIR / "logs/audit"
AUDIT_LOG_RETENTION_DAYS = 30  # Number of days to keep audit logs
AUDIT_LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB per log file
AUDIT_LOG_BACKUP_COUNT = 5  # Number of backup files to keep

# CORS
CORS_ORIGINS: List[str] = ["*"]

# Application Settings
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Sanctions Update Settings
SANCTIONS_UPDATE_INTERVAL_DAYS = int(os.getenv("SANCTIONS_UPDATE_INTERVAL_DAYS", "7"))  # Update weekly by default
SANCTIONS_AUTO_UPDATE_ENABLED = os.getenv("SANCTIONS_AUTO_UPDATE_ENABLED", "true").lower() == "true"

class AppConfig:
    """Application configuration with type hints"""
    
    @staticmethod
    def get_audit_log_config() -> Dict[str, Any]:
        """Get audit log configuration"""
        return {
            "level": LOG_LEVEL,
            "format": LOG_FORMAT,
            "dir": str(AUDIT_LOG_DIR),
            "retention_days": AUDIT_LOG_RETENTION_DAYS,
            "max_size": AUDIT_LOG_MAX_SIZE,
            "backup_count": AUDIT_LOG_BACKUP_COUNT
        }
