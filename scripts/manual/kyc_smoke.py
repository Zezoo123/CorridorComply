# test_kyc.py
import base64
import json
import os
import sys
import time
import requests 
from pathlib import Path
from datetime import datetime, timedelta

def image_to_base64(image_path: str) -> str:
    """Convert image file to base64 string"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Error reading image {image_path}: {str(e)}", file=sys.stderr)
        raise

def get_latest_audit_log() -> dict:
    """Get the most recent audit log entry with debug info"""
    try:
        # Get the absolute path to the project root
        project_root = Path(__file__).parent.parent
        log_dir = project_root / "logs" / "audit"
        
        print(f"\nLooking for logs in: {log_dir}", file=sys.stderr)
        
        if not log_dir.exists():
            print(f"❌ Log directory does not exist: {log_dir}", file=sys.stderr)
            print(f"Current working directory: {os.getcwd()}", file=sys.stderr)
            print(f"Directory contents of {project_root}:", file=sys.stderr)
            try:
                for f in project_root.iterdir():
                    print(f"- {f.name} (dir: {f.is_dir()})", file=sys.stderr)
            except Exception as e:
                print(f"Error listing directory: {e}", file=sys.stderr)
            return None
        
        # Get today's log file
        today = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = log_dir / f"audit_{today}.jsonl"
        
        print(f"Checking for log file: {log_file}", file=sys.stderr)
        
        if not log_file.exists():
            print(f"Log file does not exist: {log_file}", file=sys.stderr)
            # List all log files for debugging
            log_files = list(log_dir.glob("audit_*.jsonl"))
            print(f"Available log files: {[f.name for f in log_files]}", file=sys.stderr)
            return None
        
        # Get the last line (most recent entry)
        with open(log_file, 'r') as f:
            lines = f.readlines()
            if not lines:
                print("Log file is empty", file=sys.stderr)
                return None
            
            try:
                last_line = lines[-1].strip()
                print(f"Last log entry: {last_line[:200]}...", file=sys.stderr)  # Print first 200 chars
                return json.loads(last_line)
            except json.JSONDecodeError as e:
                print(f"Error parsing log entry: {str(e)}", file=sys.stderr)
                print(f"Problematic line: {last_line}", file=sys.stderr)
                return None
                
    except Exception as e:
        print(f"Error in get_latest_audit_log: {str(e)}", file=sys.stderr)
        return None

# Your API URL (update if different)
API_URL = "http://localhost:8000/kyc/verify"

# Generate a unique request ID for this test
request_id = f"test_{int(time.time())}"

# Prepare the request
try:
    payload = {
        "request_id": request_id,
        "full_name": "Test User",
        "dob": "1990-01-01",
        "nationality": "US",
        "document_type": "id_card",
        "document_number": "A12345678",
        "document_image_base64": image_to_base64("app/data/sample_docs/zyad/passport.jpg"),
        "selfie_image_base64": image_to_base64("app/data/sample_docs/zyad/selfie.jpg")
    }
except Exception as e:
    print(f"Error preparing test data: {str(e)}", file=sys.stderr)
    sys.exit(1)

print("Sending KYC verification request...")
try:
    # Make the API call
    print(f"Request ID: {request_id}", file=sys.stderr)
    print(f"Request payload keys: {list(payload.keys())}", file=sys.stderr)
    
    response = requests.post(API_URL, json=payload, timeout=30)
    print(f"Response status: {response.status_code}", file=sys.stderr)
    
    try:
        result = response.json()
    except json.JSONDecodeError:
        print(f"Invalid JSON response: {response.text[:500]}", file=sys.stderr)
        result = {"error": "Invalid JSON response"}
    
    print("\nKYC Verification Result:")
    print("=" * 40)
    print(f"Status: {result.get('status')}")
    print(f"Risk Score: {result.get('risk_score')}")
    print(f"Risk Level: {result.get('risk_level')}")
    if 'details' in result:
        print("Details:", "\n- ".join([""] + result['details']))
    
    # Check audit log
    print("\nChecking audit log...")
    for attempt in range(5):  # Retry for up to 5 seconds
        log_entry = get_latest_audit_log()
        if log_entry and log_entry.get('request_id') == request_id:
            break
        time.sleep(1)
    else:
        print("❌ No audit log entry found after multiple attempts")
        sys.exit(1)
    
    print("✅ Audit log entry found")
    print(f"Request ID: {log_entry.get('request_id')}")
    print(f"Action: {log_entry.get('action')}")
    print(f"Status: {log_entry.get('result', {}).get('status')}")
    print(f"Risk Score: {log_entry.get('result', {}).get('risk_score')}")
    
    # Verify the log entry has the required fields
    required_fields = ['timestamp', 'request_id', 'action', 'result']
    missing_fields = [field for field in required_fields if field not in log_entry]
    
    if missing_fields:
        print(f"❌ Missing required fields in log: {', '.join(missing_fields)}")
    else:
        print("✅ All required fields present in log entry")
    
    # Print the full log entry for debugging
    print("\nFull log entry:")
    print(json.dumps(log_entry, indent=2))
    
except Exception as e:
    print(f"❌ Error making API request: {str(e)}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)