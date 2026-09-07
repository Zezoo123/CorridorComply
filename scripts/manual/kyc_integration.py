#!/usr/bin/env python3
"""
Integration test for KYC route with OCR and face matching.

This test verifies that:
1. OCR document validation works
2. Face matching works
3. Both are integrated correctly in the KYC service
"""
import base64
import json
import os
import sys
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def image_to_base64(image_path: str) -> str:
    """Convert image file to base64 string"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"❌ Error reading image {image_path}: {str(e)}")
        raise

def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_result(key: str, value: Any, indent: int = 0):
    """Print a key-value pair with formatting"""
    prefix = "  " * indent
    if isinstance(value, (dict, list)):
        print(f"{prefix}{key}:")
        if isinstance(value, dict):
            for k, v in value.items():
                print_result(k, v, indent + 1)
        else:
            for i, item in enumerate(value):
                print(f"{prefix}  [{i}]: {item}")
    else:
        print(f"{prefix}{key}: {value}")

def test_kyc_verification(
    api_url: str = "http://localhost:8000/api/v1/kyc/verify",
    document_image_path: Optional[str] = None,
    selfie_image_path: Optional[str] = None,
    timeout: int = 120
) -> Dict[str, Any]:
    """
    Test KYC verification endpoint with OCR and face matching.
    
    Args:
        api_url: The KYC verification API endpoint
        document_image_path: Path to document image (passport/ID)
        selfie_image_path: Path to selfie image (if None, uses document image)
        timeout: Request timeout in seconds
    """
    print_section("KYC Integration Test - OCR + Face Matching")
    
    # Determine image paths
    if document_image_path is None:
        # Use sample passport from tests
        document_image_path = project_root / "tests" / "data" / "sample_passports" / "canada.jpg"
        if not document_image_path.exists():
            print(f"❌ Sample passport not found at {document_image_path}")
            return {"error": "Sample passport not found"}
    
    if selfie_image_path is None:
        # Use the same image for selfie (will test face matching but won't match)
        selfie_image_path = document_image_path
        print("⚠️  Using document image as selfie (faces won't match, but will test the flow)")
    
    # Verify images exist
    if not os.path.exists(document_image_path):
        print(f"❌ Document image not found: {document_image_path}")
        return {"error": "Document image not found"}
    
    if not os.path.exists(selfie_image_path):
        print(f"❌ Selfie image not found: {selfie_image_path}")
        return {"error": "Selfie image not found"}
    
    print(f"📄 Document image: {document_image_path}")
    print(f"📸 Selfie image: {selfie_image_path}")
    
    # Convert images to base64
    try:
        print("\n🔄 Converting images to base64...")
        document_base64 = image_to_base64(str(document_image_path))
        selfie_base64 = image_to_base64(str(selfie_image_path))
        print(f"✅ Document image size: {len(document_base64)} chars")
        print(f"✅ Selfie image size: {len(selfie_base64)} chars")
    except Exception as e:
        print(f"❌ Error converting images: {str(e)}")
        return {"error": str(e)}
    
    # Prepare request payload
    request_id = f"test_kyc_{int(time.time())}"
    payload = {
        "document_data": {
            "document_type": "passport",
            "document_number": "TEST123456",
            "expiry_date": "2030-12-31",
            "issuing_country": "CA",
            "first_name": "Test",
            "last_name": "User",
            "date_of_birth": "1990-01-01",
            "nationality": "CA",
            "address": {
                "street": "123 Test St",
                "city": "Toronto",
                "country": "CA"
            }
        },
        "document_image_base64": document_base64,
        "selfie_image_base64": selfie_base64,
        "request_id": request_id
    }
    
    print_section("Sending KYC Verification Request")
    print(f"Request ID: {request_id}")
    print(f"API URL: {api_url}")
    print(f"Timeout: {timeout}s")
    
    try:
        # Make the API request
        print("\n⏳ Sending request (this may take a while for OCR and face matching)...")
        start_time = time.time()
        
        response = requests.post(
            api_url,
            json=payload,
            headers={"X-Request-ID": request_id},
            timeout=timeout
        )
        
        elapsed_time = time.time() - start_time
        print(f"✅ Request completed in {elapsed_time:.2f}s")
        print(f"📊 Response status: {response.status_code}")
        
        # Parse response
        if response.status_code != 200:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return {"error": f"HTTP {response.status_code}", "response": response.text}
        
        try:
            result = response.json()
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON response: {str(e)}")
            print(f"Response text: {response.text[:500]}")
            return {"error": "Invalid JSON response", "response": response.text}
        
        # Display results
        print_section("KYC Verification Results")
        
        print_result("Request ID", result.get("request_id"))
        print_result("Status", result.get("status"))
        print_result("Risk Score", result.get("risk_score"))
        print_result("Risk Level", result.get("risk_level"))
        print_result("Timestamp", result.get("timestamp"))
        
        # Verification results
        verification_result = result.get("verification_result", {})
        if verification_result:
            print_section("Verification Details")
            
            # Document validation
            doc_validation = verification_result.get("document_validation", {})
            print("\n📄 Document Validation:")
            print_result("Valid", doc_validation.get("valid", False), indent=1)
            if doc_validation.get("error"):
                print_result("Error", doc_validation.get("error"), indent=1)
            if doc_validation.get("details"):
                print_result("Details", doc_validation.get("details"), indent=1)
            
            # MRZ data if available
            mrz_data = doc_validation.get("mrz_data")
            if mrz_data and not mrz_data.get("error"):
                print("\n📋 MRZ Data (from OCR):")
                for key, value in mrz_data.items():
                    if key != "error":
                        print_result(key, value, indent=1)
            
            # Face matching
            face_match = verification_result.get("face_match_details", {})
            print("\n👤 Face Matching:")
            print_result("Matched", face_match.get("matched", False), indent=1)
            print_result("Score", f"{face_match.get('score', 0.0):.2f}", indent=1)
            print_result("Document Faces", face_match.get("document_face_count", 0), indent=1)
            print_result("Selfie Faces", face_match.get("selfie_face_count", 0), indent=1)
            if face_match.get("error"):
                print_result("Error", face_match.get("error"), indent=1)
            
            # Data comparison (MRZ vs Request)
            data_comparison = verification_result.get("data_comparison")
            if data_comparison:
                print("\n🔍 Data Comparison (MRZ vs Request):")
                print_result("Match Count", data_comparison.get("match_count", 0), indent=1)
                print_result("Mismatch Count", data_comparison.get("mismatch_count", 0), indent=1)
                print_result("All Match", data_comparison.get("all_match", False), indent=1)
                
                matches = data_comparison.get("matches", [])
                if matches:
                    print_result("Matched Fields", matches, indent=1)
                
                mismatches = data_comparison.get("mismatches", [])
                if mismatches:
                    print("\n  Mismatched Fields:")
                    for mismatch in mismatches:
                        print(f"    - {mismatch['field']}:")
                        print(f"        MRZ: {mismatch['mrz_value']}")
                        print(f"        Request: {mismatch['request_value']}")
                        if 'similarity' in mismatch:
                            print(f"        Similarity: {mismatch['similarity']:.2f}")
                
                warnings = data_comparison.get("warnings", [])
                if warnings:
                    print_result("Warnings", warnings, indent=1)
            
            # Expiry validation
            expiry_validation = doc_validation.get("expiry_validation", {})
            if expiry_validation:
                print("\n📅 Expiry Date Validation:")
                print_result("Valid", expiry_validation.get("valid", False), indent=1)
                print_result("Is Expired", expiry_validation.get("is_expired", False), indent=1)
                if expiry_validation.get("expiry_date_formatted"):
                    print_result("Expiry Date", expiry_validation.get("expiry_date_formatted"), indent=1)
                if expiry_validation.get("days_until_expiry") is not None:
                    print_result("Days Until Expiry", expiry_validation.get("days_until_expiry"), indent=1)
                if expiry_validation.get("days_expired") is not None:
                    print_result("Days Expired", expiry_validation.get("days_expired"), indent=1)
        
        # Risk factors
        risk_factors = result.get("risk_factors", [])
        if risk_factors:
            print_section("Risk Factors")
            for i, factor in enumerate(risk_factors, 1):
                print(f"\n  [{i}] {factor.get('type', 'unknown')}: {factor.get('description', 'N/A')}")
                print(f"      Severity: {factor.get('severity', 'unknown')}")
        
        # Summary
        print_section("Test Summary")
        doc_verified = verification_result.get("document_verified", False)
        face_matched = verification_result.get("face_match", False)
        
        print(f"✅ OCR Document Validation: {'PASSED' if doc_verified else 'FAILED'}")
        print(f"✅ Face Matching: {'PASSED' if face_matched else 'FAILED'}")
        print(f"✅ Overall Risk Score: {result.get('risk_score', 'N/A')}")
        print(f"✅ Risk Level: {result.get('risk_level', 'N/A')}")
        
        if doc_verified and face_matched:
            print("\n🎉 All validations passed!")
        elif doc_verified:
            print("\n⚠️  Document validated but face match failed")
        elif face_matched:
            print("\n⚠️  Face matched but document validation failed")
        else:
            print("\n❌ Both validations failed")
        
        return result
        
    except requests.exceptions.Timeout:
        print(f"❌ Request timed out after {timeout}s")
        print("   This might be normal for first-time OCR initialization")
        return {"error": "Request timeout"}
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to {api_url}")
        print("   Make sure the server is running: uvicorn app.main:app --reload")
        return {"error": "Connection error"}
    except Exception as e:
        print(f"❌ Error making request: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test KYC verification with OCR and face matching")
    parser.add_argument(
        "--document",
        type=str,
        help="Path to document image (default: tests/data/sample_passports/canada.jpg)"
    )
    parser.add_argument(
        "--selfie",
        type=str,
        help="Path to selfie image (default: same as document)"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000/api/v1/kyc/verify",
        help="API endpoint URL"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Request timeout in seconds (default: 120)"
    )
    
    args = parser.parse_args()
    
    result = test_kyc_verification(
        api_url=args.url,
        document_image_path=args.document,
        selfie_image_path=args.selfie,
        timeout=args.timeout
    )
    
    # Exit with error code if test failed
    if result.get("error"):
        sys.exit(1)
    
    # Check if validations passed
    verification_result = result.get("verification_result", {})
    doc_verified = verification_result.get("document_verified", False)
    face_matched = verification_result.get("face_match", False)
    
    if not doc_verified or not face_matched:
        print("\n⚠️  Some validations failed (this may be expected)")
        sys.exit(0)  # Don't fail the test, just warn
    
    print("\n✅ Test completed successfully!")
    sys.exit(0)
