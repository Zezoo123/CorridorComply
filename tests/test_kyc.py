#!/usr/bin/env python3
"""
Test script for KYC endpoint
Run this after starting the server: uvicorn app.main:app --reload
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_kyc_verify(payload, test_name):
    """Test KYC verify endpoint"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    print(f"Request: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/kyc/verify",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        result = response.json()
        
        print(f"\nResponse:")
        print(json.dumps(result, indent=2))
        print(f"\n✓ Status: {result.get('status')}")
        print(f"✓ Risk Score: {result.get('risk_score')}")
        print(f"✓ Risk Level: {result.get('risk_level')}")
        print(f"✓ Details: {len(result.get('details', []))} items")
        
        return result
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def main():
    """Run all test scenarios"""
    print("="*60)
    print("KYC Endpoint Test Suite")
    print("="*60)
    print(f"Testing against: {BASE_URL}")
    
    # Test 1: Basic valid KYC (should pass)
    test_kyc_verify(
        {
            "full_name": "Juan Dela Cruz",
            "dob": "1990-01-01",
            "nationality": "PH",
            "document_type": "passport",
            "document_number": "P1234567"
        },
        "1. Basic Valid KYC (Should Pass)"
    )
    
    # Test 2: Invalid document (short number)
    test_kyc_verify(
        {
            "full_name": "John Doe",
            "dob": "1985-05-15",
            "nationality": "US",
            "document_type": "passport",
            "document_number": "AB"  # Too short
        },
        "2. Invalid Document Number (Should Fail)"
    )
    
    # Test 3: Missing document number
    test_kyc_verify(
        {
            "full_name": "Jane Smith",
            "dob": "1992-03-20",
            "nationality": "GB",
            "document_type": "id_card",
            "document_number": ""  # Empty
        },
        "3. Empty Document Number (Should Fail)"
    )
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)
    print("\nTo test with curl, use:")
    print("""
curl -X 'POST' \\
  'http://127.0.0.1:8000/kyc/verify' \\
  -H 'accept: application/json' \\
  -H 'Content-Type: application/json' \\
  -d '{
  "full_name": "Juan Dela Cruz",
  "dob": "1990-01-01",
  "nationality": "PH",
  "document_type": "passport",
  "document_number": "P1234567"
}'
    """)

if __name__ == "__main__":
    main()

