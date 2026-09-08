#!/usr/bin/env python3
"""
Test script for /risk/combined endpoint
Run this after starting the server: uvicorn app.main:app --reload
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_combined_risk(payload, test_name):
    """Test combined risk endpoint"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    print(f"Request: {json.dumps(payload, indent=2, default=str)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/risk/combined",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        result = response.json()
        
        print(f"\nResponse:")
        print(json.dumps(result, indent=2, default=str))
        print(f"\n✓ Combined Risk Score: {result.get('combined_risk_score')}")
        print(f"✓ Combined Risk Level: {result.get('combined_risk_level')}")
        if result.get('aml_risk_score') is not None:
            print(f"✓ AML Risk: {result.get('aml_risk_score')} ({result.get('aml_risk_level')})")
        if result.get('kyc_risk_score') is not None:
            print(f"✓ KYC Risk: {result.get('kyc_risk_score')} ({result.get('kyc_risk_level')})")
        print(f"✓ Risk Factors: {len(result.get('risk_factors', []))}")
        
        return result
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def main():
    """Run all test scenarios"""
    print("="*60)
    print("Combined Risk Endpoint Test Suite")
    print("="*60)
    print(f"Testing against: {BASE_URL}")
    
    # Test 1: Both AML and KYC data
    test_combined_risk(
        {
            "aml_data": {
                "full_name": "Ahmed Ali",
                "dob": "1989-03-12",
                "nationality": "QA"
            },
            "kyc_data": {
                "full_name": "Ahmed Ali",
                "dob": "1989-03-12",
                "nationality": "QA",
                "document_type": "passport",
                "document_number": "P1234567"
            }
        },
        "1. Both AML and KYC Data (Full Assessment)"
    )
    
    # Test 2: Only AML data
    test_combined_risk(
        {
            "aml_data": {
                "full_name": "John Doe",
                "dob": "1990-01-01",
                "nationality": "US"
            }
        },
        "2. Only AML Data"
    )
    
    # Test 3: Only KYC data
    test_combined_risk(
        {
            "kyc_data": {
                "full_name": "Juan Dela Cruz",
                "dob": "1990-01-01",
                "nationality": "PH",
                "document_type": "passport",
                "document_number": "P1234567"
            }
        },
        "3. Only KYC Data"
    )
    
    # Test 4: Pre-calculated risks
    test_combined_risk(
        {
            "aml_risk": {
                "risk_score": 50,
                "risk_level": "medium",
                "risk_factors": [
                    {
                        "type": "aml_sanctions",
                        "severity": "medium",
                        "description": "Sanctions match found"
                    }
                ]
            },
            "kyc_risk": {
                "risk_score": 30,
                "risk_level": "low",
                "risk_factors": [
                    {
                        "type": "kyc_document",
                        "severity": "low",
                        "description": "Document format valid"
                    }
                ]
            }
        },
        "4. Pre-calculated Risks"
    )
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)
    print("\nTo test with curl, use:")
    print("""
curl -X 'POST' \\
  'http://127.0.0.1:8000/risk/combined' \\
  -H 'accept: application/json' \\
  -H 'Content-Type: application/json' \\
  -d '{
  "aml_data": {
    "full_name": "Ahmed Ali",
    "dob": "1989-03-12",
    "nationality": "QA"
  },
  "kyc_data": {
    "full_name": "Ahmed Ali",
    "dob": "1989-03-12",
    "nationality": "QA",
    "document_type": "passport",
    "document_number": "P1234567"
  }
}'
    """)

if __name__ == "__main__":
    main()

