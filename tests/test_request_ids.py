#!/usr/bin/env python3
"""
Test script to verify request IDs and audit logging
Run this after starting the server: uvicorn app.main:app --reload
"""
import requests
import json
from pathlib import Path
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
AUDIT_LOG_DIR = Path("./logs/audit")

def print_section(title):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_endpoint(name, url, payload):
    """Test an endpoint and return the response"""
    print(f"Testing {name}...")
    print(f"Request: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        result = response.json()
        
        print(f"\n✓ Response received")
        print(f"✓ Request ID: {result.get('request_id', 'NOT FOUND')}")
        
        if 'request_id' in result:
            print(f"  → UUID format: {'✓ Valid' if len(result['request_id']) == 36 else '✗ Invalid'}")
        
        print(f"\nFull Response:")
        print(json.dumps(result, indent=2))
        
        return result
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def check_audit_logs():
    """Check if audit logs are being created"""
    print_section("Checking Audit Logs")
    
    if not AUDIT_LOG_DIR.exists():
        print(f"✗ Audit log directory does not exist: {AUDIT_LOG_DIR}")
        print("  → Logs will be created on first request")
        return
    
    # Find today's log file
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = AUDIT_LOG_DIR / f"audit_{today}.jsonl"
    
    if not log_file.exists():
        print(f"✗ Today's log file does not exist: {log_file}")
        print("  → Logs will be created on first request")
        return
    
    print(f"✓ Found log file: {log_file}")
    
    # Read and display recent entries
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        print(f"✓ Found {len(lines)} log entries")
        
        if lines:
            print(f"\nMost recent entry:")
            latest = json.loads(lines[-1])
            print(json.dumps(latest, indent=2))
            
            # Check for request_id in log
            if 'request_id' in latest:
                print(f"\n✓ Request ID found in log: {latest['request_id']}")
            else:
                print(f"\n✗ Request ID NOT found in log")
    except Exception as e:
        print(f"✗ Error reading log file: {e}")

def main():
    """Run all tests"""
    print_section("Request ID & Audit Logging Test")
    print(f"Testing against: {BASE_URL}")
    print(f"Audit log directory: {AUDIT_LOG_DIR.absolute()}")
    
    # Test 1: KYC endpoint
    print_section("Test 1: KYC Endpoint")
    kyc_result = test_endpoint(
        "KYC /verify",
        f"{BASE_URL}/kyc/verify",
        {
            "full_name": "John Doe",
            "dob": "1990-01-01",
            "nationality": "US",
            "document_type": "passport",
            "document_number": "P1234567"
        }
    )
    
    # Test 2: AML endpoint
    print_section("Test 2: AML Endpoint")
    aml_result = test_endpoint(
        "AML /screen",
        f"{BASE_URL}/aml/screen",
        {
            "full_name": "Ahmed Ali",
            "dob": "1989-03-12",
            "nationality": "QA"
        }
    )
    
    # Test 3: Combined Risk endpoint
    print_section("Test 3: Combined Risk Endpoint")
    risk_result = test_endpoint(
        "Risk /combined",
        f"{BASE_URL}/risk/combined",
        {
            "aml_data": {
                "full_name": "Jane Smith",
                "dob": "1992-05-15",
                "nationality": "GB"
            },
            "kyc_data": {
                "full_name": "Jane Smith",
                "dob": "1992-05-15",
                "nationality": "GB",
                "document_type": "passport",
                "document_number": "GB123456"
            }
        }
    )
    
    # Check audit logs
    check_audit_logs()
    
    # Summary
    print_section("Test Summary")
    print("Request IDs in responses:")
    print(f"  KYC: {'✓' if kyc_result and 'request_id' in kyc_result else '✗'}")
    print(f"  AML: {'✓' if aml_result and 'request_id' in aml_result else '✗'}")
    print(f"  Risk: {'✓' if risk_result and 'request_id' in risk_result else '✗'}")
    
    print("\n" + "="*60)
    print("To view audit logs manually:")
    print(f"  cat {AUDIT_LOG_DIR.absolute()}/audit_*.jsonl")
    print("="*60)

if __name__ == "__main__":
    main()

