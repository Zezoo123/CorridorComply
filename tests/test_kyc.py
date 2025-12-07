# test_kyc_api.py
import base64
import requests
from pathlib import Path

def image_to_base64(image_path: str) -> str:
    """Convert image file to base64 string"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Your API URL (update if different)
API_URL = "http://localhost:8000/kyc/verify"

# Prepare the request
payload = {
    "full_name": "Test User",
    "dob": "1990-01-01",
    "nationality": "US",
    "document_type": "id_card",
    "document_number": "A12345678",
    "document_image_base64": image_to_base64("app/data/sample_docs/zyad/passport.jpg"),
    "selfie_image_base64": image_to_base64("app/data/sample_docs/zyad/selfie.jpg")
}

try:
    response = requests.post(API_URL, json=payload)
    result = response.json()
    print("KYC Verification Result:")
    print(f"Status: {result.get('status')}")
    print(f"Risk Score: {result.get('risk_score')}")
    print(f"Risk Level: {result.get('risk_level')}")
    if 'details' in result:
        print("Details:", "\n- ".join([""] + result['details']))
        
except Exception as e:
    print(f"Error calling API: {str(e)}")