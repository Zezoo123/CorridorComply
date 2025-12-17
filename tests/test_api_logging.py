"""
Test suite for API logging functionality.

This test suite verifies that all API endpoints generate the expected log entries
and that the logging format is consistent.
"""
import json
import re
import time
import pytest
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import requests

# Configure test logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = "http://localhost:8000"
LOGS_DIR = Path("logs")  # Using relative path to match the application's log directory
AUDIT_LOG_DIR = LOGS_DIR / "audit"

# Sample test data
TEST_USER = {
    "full_name": "Test User",
    "dob": "1990-01-01",
    "nationality": "US",
    "document_type": "passport",
    "document_number": "A12345678",
    "document_image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",  # 1x1 transparent pixel
    "selfie_image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="   # 1x1 transparent pixel
}

def get_log_entries(log_file: Path, timeout: int = 5) -> List[str]:
    """Read log entries from the log file."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if not log_file.exists():
            time.sleep(0.1)
            continue
            
        try:
            with open(log_file, 'r') as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except (FileNotFoundError, PermissionError) as e:
            logger.error(f"Error reading log file {log_file}: {e}")
            time.sleep(0.1)
    
    logger.warning(f"Timeout waiting for log file: {log_file}")
    return []

def find_matching_log_entry(log_entries: List[str], search_text: str) -> Optional[Dict[str, Any]]:
    """Find a log entry containing the search text and parse it."""
    for entry in reversed(log_entries):
        if search_text.lower() in entry.lower():
            # Parse the log entry (this is a simplified parser)
            # Format: "timestamp - logger - level - message"
            parts = re.split(r'\s+-\s+', entry, maxsplit=3)
            if len(parts) >= 4:
                timestamp, logger_name, level, message = parts
                return {
                    'timestamp': timestamp,
                    'logger': logger_name,
                    'level': level,
                    'message': message
                }
    return None

def test_health_check():
    """Test that the health check endpoint is logged correctly."""
    # Get current log entries before making the request
    log_file = LOGS_DIR / f"app-{datetime.now().strftime('%Y-%m-%d')}.log"
    initial_logs = get_log_entries(log_file)
    
    # Make the request
    logger.info(f"Making health check request to {BASE_URL}/health")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    # Get the request ID from the response
    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None, "Response missing X-Request-ID header"
    logger.info(f"Request ID: {request_id}")
    
    # Get updated log entries
    time.sleep(1)  # Give some time for logs to be written
    updated_logs = get_log_entries(log_file)
    
    # Find new log entries
    new_entries = updated_logs[len(initial_logs):] if initial_logs else updated_logs
    
    # Debug: Print new log entries
    logger.info(f"New log entries ({len(new_entries)}):")
    for i, entry in enumerate(new_entries, 1):
        logger.info(f"  {i}. {entry}")
    
    # Check if we have any new log entries
    assert len(new_entries) > 0, "No new log entries found after health check request"
    
    # Look for the health check log entry
    health_check_found = any("/health" in entry for entry in new_entries)
    assert health_check_found, "No log entry found for health check request"

def test_kyc_verification_logging():
    """Test that KYC verification requests are logged correctly."""
    # Get current log entries before making the request
    log_file = LOGS_DIR / f"app-{datetime.now().strftime('%Y-%m-%d')}.log"
    initial_logs = get_log_entries(log_file)
    
    # Make the request
    logger.info(f"Making KYC verification request to {BASE_URL}/api/v1/kyc/verify")
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/kyc/verify",
            json=TEST_USER,
            headers={"Content-Type": "application/json"}
        )
        logger.info(f"Response status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise
    
    # Basic response validation
    assert response.status_code in [200, 400, 422], f"Unexpected status code: {response.status_code}"
    
    # Get the request ID from the response
    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None, "Response missing X-Request-ID header"
    logger.info(f"Request ID: {request_id}")
    
    # Get updated log entries
    time.sleep(1)  # Give some time for logs to be written
    updated_logs = get_log_entries(log_file)
    
    # Find new log entries
    new_entries = updated_logs[len(initial_logs):] if initial_logs else updated_logs
    
    # Debug: Print new log entries
    logger.info(f"New log entries ({len(new_entries)}):")
    for i, entry in enumerate(new_entries, 1):
        logger.info(f"  {i}. {entry}")
    
    # Check if we have any new log entries
    assert len(new_entries) > 0, "No new log entries found after KYC verification request"
    
    # Look for the KYC verification log entry
    kyc_log_found = any("/api/v1/kyc/verify" in entry for entry in new_entries)
    assert kyc_log_found, "No log entry found for KYC verification request"

def test_invalid_endpoint_logging():
    """Test that requests to non-existent endpoints are logged correctly."""
    # Get current log entries before making the request
    log_file = LOGS_DIR / f"app-{datetime.now().strftime('%Y-%m-%d')}.log"
    initial_logs = get_log_entries(log_file)
    
    # Make a request to a non-existent endpoint
    non_existent_endpoint = f"{BASE_URL}/non-existent-endpoint-{int(time.time())}"
    logger.info(f"Making request to non-existent endpoint: {non_existent_endpoint}")
    
    try:
        response = requests.get(non_existent_endpoint)
        logger.info(f"Response status: {response.status_code}")
        assert response.status_code == 404, f"Expected status code 404, got {response.status_code}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise
    
    # Get the request ID from the response
    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None, "Response missing X-Request-ID header"
    logger.info(f"Request ID: {request_id}")
    
    # Get updated log entries
    time.sleep(1)  # Give some time for logs to be written
    updated_logs = get_log_entries(log_file)
    
    # Find new log entries
    new_entries = updated_logs[len(initial_logs):] if initial_logs else updated_logs
    
    # Debug: Print new log entries
    logger.info(f"New log entries ({len(new_entries)}):")
    for i, entry in enumerate(new_entries, 1):
        logger.info(f"  {i}. {entry}")
    
    # Check if we have any new log entries
    assert len(new_entries) > 0, "No new log entries found after 404 request"
    
    # Look for the 404 log entry
    not_found_log_found = any("404" in entry for entry in new_entries)
    assert not_found_log_found, "No 404 log entry found for non-existent endpoint"

def test_error_handling_logging():
    """Test that server errors are logged correctly."""
    # Get current log entries before making the request
    log_file = LOGS_DIR / f"app-{datetime.now().strftime('%Y-%m-%d')}.log"
    initial_logs = get_log_entries(log_file)
    
    # Make a malformed request to the KYC endpoint
    logger.info("Making malformed KYC verification request to trigger validation error")
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/kyc/verify",
            json={"invalid": "data"},  # Missing required fields
            headers={"Content-Type": "application/json"}
        )
        logger.info(f"Response status: {response.status_code}")
        # We expect a 422 Unprocessable Entity for invalid data
        assert response.status_code == 422, f"Expected status code 422, got {response.status_code}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise
    
    # Get the request ID from the response
    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None, "Response missing X-Request-ID header"
    logger.info(f"Request ID: {request_id}")
    
    # Get updated log entries
    time.sleep(1)  # Give some time for logs to be written
    updated_logs = get_log_entries(log_file)
    
    # Find new log entries
    new_entries = updated_logs[len(initial_logs):] if initial_logs else updated_logs
    
    # Debug: Print new log entries
    logger.info(f"New log entries ({len(new_entries)}):")
    for i, entry in enumerate(new_entries, 1):
        logger.info(f"  {i}. {entry}")
    
    # Check if we have any new log entries
    assert len(new_entries) > 0, "No new log entries found after error request"
    
    # Look for the error log entry
    error_log_found = any("422" in entry or "error" in entry.lower() for entry in new_entries)
    assert error_log_found, "No error log entry found for malformed request"

# This allows running the tests directly with python -m pytest tests/test_api_logging.py -v
if __name__ == "__main__":
    import requests
    pytest.main([__file__, "-v"])
