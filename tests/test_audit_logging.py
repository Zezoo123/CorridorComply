"""
Test suite for audit logging functionality.

This test suite verifies that all API endpoints generate audit logs with:
- Request payload
- Risk score
- Match summary
- Timestamp
"""
import json
import time
import pytest
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import requests
import base64
from PIL import Image
from io import BytesIO

# Configure test logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = "http://localhost:8000"
AUDIT_LOG_DIR = Path("logs/audit")
AUDIT_LOG_FILE = AUDIT_LOG_DIR / "audit.log"

# Create a minimal valid image (1x1 pixel PNG)
def create_test_image_base64() -> str:
    """Create a minimal valid base64-encoded image for testing."""
    # Create a 1x1 pixel image
    img = Image.new('RGB', (1, 1), color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode('utf-8')

TEST_IMAGE_BASE64 = create_test_image_base64()

def get_audit_log_entries(timeout: int = 5) -> List[Dict[str, Any]]:
    """Read and parse audit log entries from the audit log file."""
    start_time = time.time()
    entries = []
    
    while time.time() - start_time < timeout:
        if not AUDIT_LOG_FILE.exists():
            time.sleep(0.1)
            continue
        
        try:
            with open(AUDIT_LOG_FILE, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                for line in lines:
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        # Skip invalid JSON lines
                        continue
            break
        except (FileNotFoundError, PermissionError) as e:
            logger.error(f"Error reading audit log file {AUDIT_LOG_FILE}: {e}")
            time.sleep(0.1)
    
    return entries

def find_audit_entry_by_request_id(entries: List[Dict[str, Any]], request_id: str) -> Optional[Dict[str, Any]]:
    """Find an audit log entry by request ID."""
    for entry in reversed(entries):
        if entry.get('request_id') == request_id:
            return entry
    return None

def find_audit_entry_by_event_type(entries: List[Dict[str, Any]], event_type: str, request_id: str = None) -> Optional[Dict[str, Any]]:
    """Find an audit log entry by event type and optionally request ID."""
    for entry in reversed(entries):
        if entry.get('event_type') == event_type:
            if request_id is None or entry.get('request_id') == request_id:
                return entry
    return None

def verify_audit_entry_fields(entry: Dict[str, Any], required_fields: List[str]) -> tuple[bool, List[str]]:
    """Verify that an audit entry contains all required fields."""
    missing_fields = []
    for field in required_fields:
        if field not in entry:
            missing_fields.append(field)
    return len(missing_fields) == 0, missing_fields

class TestAuditLogging:
    """Test class for audit logging functionality."""
    
    def setup_method(self):
        """Setup method called before each test."""
        # Get initial audit log entries count
        self.initial_entries = get_audit_log_entries()
        self.initial_count = len(self.initial_entries)
        logger.info(f"Initial audit log entries count: {self.initial_count}")
    
    def test_kyc_verify_audit_logging(self):
        """Test that KYC verify endpoint logs audit events with all required fields."""
        # Prepare test payload
        payload = {
            "document_data": {
                "document_type": "passport",
                "document_number": "TEST123456",
                "first_name": "John",
                "last_name": "Doe",
                "date_of_birth": "1990-01-01",
                "nationality": "US",
                "issuing_country": "US",
                "expiry_date": "2030-01-01"
            },
            "document_image_base64": TEST_IMAGE_BASE64,
            "selfie_image_base64": TEST_IMAGE_BASE64
        }
        
        # Make the request
        logger.info(f"Making KYC verify request to {BASE_URL}/api/v1/kyc/verify")
        response = requests.post(
            f"{BASE_URL}/api/v1/kyc/verify",
            json=payload,
            headers={"Content-Type": "application/json", "X-Request-ID": f"test_kyc_{int(time.time())}"}
        )
        
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None, "Response missing X-Request-ID header"
        logger.info(f"Request ID: {request_id}")
        
        # Wait for audit log to be written
        time.sleep(2)
        
        # Get audit log entries
        entries = get_audit_log_entries()
        new_entries = entries[self.initial_count:]
        
        # Find the audit entry for this request
        audit_entry = find_audit_entry_by_event_type(new_entries, "kyc_verification", request_id)
        
        assert audit_entry is not None, f"No audit log entry found for KYC verification with request_id {request_id}"
        logger.info(f"Found audit entry: {json.dumps(audit_entry, indent=2)}")
        
        # Verify required fields
        required_fields = ['timestamp', 'event_type', 'request_id', 'status']
        has_all_fields, missing = verify_audit_entry_fields(audit_entry, required_fields)
        assert has_all_fields, f"Missing required fields in audit entry: {missing}"
        
        # Verify specific fields for KYC
        assert audit_entry['event_type'] == 'kyc_verification', "Incorrect event type"
        assert 'risk_score' in audit_entry['data'], "Missing risk_score in audit data"
        assert 'risk_level' in audit_entry['data'], "Missing risk_level in audit data"
        
        # Verify match summary (verification_result)
        if audit_entry['data'].get('status') == 'success':
            assert 'verification_result' in audit_entry['data'], "Missing verification_result in audit data"
            assert 'document_verified' in audit_entry['data'], "Missing document_verified in audit data"
            assert 'face_match' in audit_entry['data'], "Missing face_match in audit data"
        
        # Verify request payload is logged
        assert 'request_payload' in audit_entry, "Missing request_payload in audit entry"
        assert 'document_data' in audit_entry['request_payload'], "Missing document_data in request_payload"
        
        logger.info("✓ KYC verify audit logging test passed")
    
    def test_aml_screen_audit_logging(self):
        """Test that AML screen endpoint logs audit events with all required fields."""
        # Prepare test payload
        payload = {
            "full_name": "John Doe",
            "dob": "1990-01-01",
            "nationality": "US"
        }
        
        # Make the request
        logger.info(f"Making AML screen request to {BASE_URL}/api/v1/aml/screen")
        response = requests.post(
            f"{BASE_URL}/api/v1/aml/screen",
            json=payload,
            headers={"Content-Type": "application/json", "X-Request-ID": f"test_aml_{int(time.time())}"}
        )
        
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None, "Response missing X-Request-ID header"
        logger.info(f"Request ID: {request_id}")
        
        # Wait for audit log to be written
        time.sleep(2)
        
        # Get audit log entries
        entries = get_audit_log_entries()
        new_entries = entries[self.initial_count:]
        
        # Find the audit entry for this request
        audit_entry = find_audit_entry_by_event_type(new_entries, "aml_screening", request_id)
        
        assert audit_entry is not None, f"No audit log entry found for AML screening with request_id {request_id}"
        logger.info(f"Found audit entry: {json.dumps(audit_entry, indent=2)}")
        
        # Verify required fields
        required_fields = ['timestamp', 'event_type', 'request_id', 'status']
        has_all_fields, missing = verify_audit_entry_fields(audit_entry, required_fields)
        assert has_all_fields, f"Missing required fields in audit entry: {missing}"
        
        # Verify specific fields for AML
        assert audit_entry['event_type'] == 'aml_screening', "Incorrect event type"
        assert 'risk_score' in audit_entry['data'], "Missing risk_score in audit data"
        assert 'risk_level' in audit_entry['data'], "Missing risk_level in audit data"
        
        # Verify match summary
        if audit_entry['data'].get('status') == 'success':
            assert 'sanctions_match' in audit_entry['data'], "Missing sanctions_match in audit data"
            assert 'pep_match' in audit_entry['data'], "Missing pep_match in audit data"
            assert 'match_count' in audit_entry['data'], "Missing match_count in audit data"
        
        # Verify request payload is logged
        assert 'request_payload' in audit_entry, "Missing request_payload in audit entry"
        assert 'full_name' in audit_entry['request_payload'], "Missing full_name in request_payload"
        assert 'nationality' in audit_entry['request_payload'], "Missing nationality in request_payload"
        
        logger.info("✓ AML screen audit logging test passed")
    
    def test_risk_combined_audit_logging(self):
        """Test that Risk combined endpoint logs audit events with all required fields."""
        # Prepare test payload
        payload = {
            "aml_data": {
                "full_name": "John Doe",
                "dob": "1990-01-01",
                "nationality": "US"
            },
            "kyc_data": {
                "document_data": {
                    "document_type": "passport",
                    "document_number": "TEST123456",
                    "first_name": "John",
                    "last_name": "Doe",
                    "date_of_birth": "1990-01-01",
                    "nationality": "US",
                    "issuing_country": "US",
                    "expiry_date": "2030-01-01"
                },
                "document_image_base64": TEST_IMAGE_BASE64,
                "selfie_image_base64": TEST_IMAGE_BASE64
            }
        }
        
        # Make the request
        logger.info(f"Making Risk combined request to {BASE_URL}/api/v1/risk/combined")
        response = requests.post(
            f"{BASE_URL}/api/v1/risk/combined",
            json=payload,
            headers={"Content-Type": "application/json", "X-Request-ID": f"test_risk_{int(time.time())}"}
        )
        
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None, "Response missing X-Request-ID header"
        logger.info(f"Request ID: {request_id}")
        
        # Wait for audit log to be written
        time.sleep(2)
        
        # Get audit log entries
        entries = get_audit_log_entries()
        new_entries = entries[self.initial_count:]
        
        # Find the audit entry for this request
        audit_entry = find_audit_entry_by_event_type(new_entries, "combined_risk_assessment", request_id)
        
        assert audit_entry is not None, f"No audit log entry found for combined risk assessment with request_id {request_id}"
        logger.info(f"Found audit entry: {json.dumps(audit_entry, indent=2)}")
        
        # Verify required fields
        required_fields = ['timestamp', 'event_type', 'request_id', 'status']
        has_all_fields, missing = verify_audit_entry_fields(audit_entry, required_fields)
        assert has_all_fields, f"Missing required fields in audit entry: {missing}"
        
        # Verify specific fields for Risk
        assert audit_entry['event_type'] == 'combined_risk_assessment', "Incorrect event type"
        assert 'combined_risk_score' in audit_entry['data'], "Missing combined_risk_score in audit data"
        assert 'combined_risk_level' in audit_entry['data'], "Missing combined_risk_level in audit data"
        
        # Verify match summary
        if audit_entry['data'].get('status') == 'success':
            assert 'aml_sanctions_match' in audit_entry['data'], "Missing aml_sanctions_match in audit data"
            assert 'kyc_document_verified' in audit_entry['data'], "Missing kyc_document_verified in audit data"
            assert 'kyc_face_match' in audit_entry['data'], "Missing kyc_face_match in audit data"
        
        # Verify request payload is logged
        assert 'request_payload' in audit_entry, "Missing request_payload in audit entry"
        assert 'aml_data' in audit_entry['request_payload'] or 'kyc_data' in audit_entry['request_payload'], \
            "Missing aml_data or kyc_data in request_payload"
        
        logger.info("✓ Risk combined audit logging test passed")
    
    def test_audit_log_timestamp_format(self):
        """Test that audit logs have proper ISO format timestamps."""
        # Make a simple request to generate an audit log
        payload = {
            "full_name": "Test User",
            "dob": "1990-01-01",
            "nationality": "US"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/aml/screen",
            json=payload,
            headers={"Content-Type": "application/json", "X-Request-ID": f"test_timestamp_{int(time.time())}"}
        )
        
        request_id = response.headers.get("X-Request-ID")
        time.sleep(2)
        
        entries = get_audit_log_entries()
        audit_entry = find_audit_entry_by_event_type(entries, "aml_screening", request_id)
        
        assert audit_entry is not None, "No audit entry found"
        assert 'timestamp' in audit_entry, "Missing timestamp field"
        
        # Verify timestamp is in ISO format
        try:
            datetime.fromisoformat(audit_entry['timestamp'].replace('Z', '+00:00'))
        except ValueError:
            pytest.fail(f"Timestamp is not in ISO format: {audit_entry['timestamp']}")
        
        logger.info("✓ Timestamp format test passed")
    
    def test_audit_log_file_location(self):
        """Test that audit logs are written to the correct location."""
        assert AUDIT_LOG_DIR.exists(), f"Audit log directory does not exist: {AUDIT_LOG_DIR}"
        assert AUDIT_LOG_FILE.exists() or any(AUDIT_LOG_DIR.glob("audit.log*")), \
            f"Audit log file does not exist: {AUDIT_LOG_FILE}"
        logger.info("✓ Audit log file location test passed")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

