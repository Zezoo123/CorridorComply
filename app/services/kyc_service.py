# In app/services/kyc_service.py
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from PIL import Image
import io
import base64

from app.core.ocr import validate_document_ocr
from app.services.face_match import FaceMatchingService

logger = logging.getLogger(__name__)

class KYCService:
    @classmethod
    async def process_kyc(
        cls,
        request_id: str,
        full_name: str,
        dob: str,
        nationality: str,
        document_type: str,
        document_number: str,
        document_image: Image.Image,
        selfie_image: Image.Image,
        expiry_date: Optional[str] = None,
        issuing_country: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process KYC verification with document and selfie images.
        
        Args:
            request_id: Unique request identifier
            full_name: Full name of the person
            dob: Date of birth (YYYY-MM-DD)
            nationality: Nationality (ISO 2-letter code)
            document_type: Type of document (e.g., 'passport', 'id_card')
            document_number: Document number
            document_image: PIL Image of the document
            selfie_image: PIL Image of the selfie
            expiry_date: Optional expiry date (YYYY-MM-DD)
            issuing_country: Optional issuing country code
            
        Returns:
            Dict with verification results
        """
        try:
            logger.info(f"Starting KYC processing for request {request_id}")
            
            # Process document and selfie images
            # Calculate approximate size by saving to bytes
            doc_bytes = io.BytesIO()
            document_image.save(doc_bytes, format='JPEG')
            doc_size_kb = len(doc_bytes.getvalue()) / 1024
            
            selfie_bytes = io.BytesIO()
            selfie_image.save(selfie_bytes, format='JPEG')
            selfie_size_kb = len(selfie_bytes.getvalue()) / 1024
            
            document_info = {
                "width": document_image.width,
                "height": document_image.height,
                "format": document_image.format or "JPEG",
                "mode": document_image.mode,
                "size_kb": doc_size_kb
            }
            
            selfie_info = {
                "width": selfie_image.width,
                "height": selfie_image.height,
                "format": selfie_image.format or "JPEG",
                "mode": selfie_image.mode,
                "size_kb": selfie_size_kb
            }
            
            # Log image information
            logger.info(f"Document image: {document_info}")
            logger.info(f"Selfie image: {selfie_info}")
            
            # Perform document OCR validation
            logger.info(f"Starting document OCR validation for request {request_id}")
            document_validation = validate_document_ocr(document_image)
            logger.info(f"Document validation result: valid={document_validation.get('valid', False)}")
            
            # Compare MRZ data with request data
            mrz_data = document_validation.get("mrz_data")
            data_comparison = None
            if mrz_data and "error" not in mrz_data:
                from app.core.ocr import compare_mrz_with_request_data
                # Parse full name into first and last
                name_parts = full_name.split() if full_name else []
                request_doc_data = {
                    "document_number": document_number,
                    "first_name": name_parts[0] if len(name_parts) > 0 else "",
                    "last_name": " ".join(name_parts[1:]) if len(name_parts) > 1 else (name_parts[0] if name_parts else ""),
                    "date_of_birth": dob,
                    "nationality": nationality,
                    "expiry_date": expiry_date or "",
                    "issuing_country": issuing_country or ""
                }
                data_comparison = compare_mrz_with_request_data(mrz_data, request_doc_data)
                logger.info(f"Data comparison: {data_comparison.get('match_count')} matches, {data_comparison.get('mismatch_count')} mismatches")
            
            # Perform face matching
            logger.info(f"Starting face matching for request {request_id}")
            face_match_result_raw = FaceMatchingService.verify_faces(
                document_image=document_image,
                selfie_image=selfie_image
            )
            
            # Format face match result
            face_match_result = {
                "matched": face_match_result_raw.get("face_match_result", False),
                "score": face_match_result_raw.get("face_match_score", 0.0),
                "document_face_count": face_match_result_raw.get("document_face_count", 0),
                "selfie_face_count": face_match_result_raw.get("selfie_face_count", 0),
                "error": face_match_result_raw.get("error"),
                "details": []
            }
            
            if face_match_result["error"]:
                face_match_result["details"].append(f"Face matching error: {face_match_result['error']}")
            elif face_match_result["matched"]:
                face_match_result["details"].append(f"Face match successful (score: {face_match_result['score']:.2f})")
            else:
                face_match_result["details"].append(f"Face match failed (score: {face_match_result['score']:.2f})")
            
            logger.info(f"Face matching result: matched={face_match_result['matched']}, score={face_match_result['score']:.2f}")
            
            # Calculate risk score based on validations
            risk_score = 0  # Default to 0 (lowest risk)
            risk_factors = []
            
            # Check document validation
            doc_valid = document_validation.get("valid", False)
            expiry_validation = document_validation.get("expiry_validation", {})
            
            # Check if document is expired
            if expiry_validation.get("is_expired", False):
                risk_score += 30
                risk_factors.append({
                    "description": f"Document expired on {expiry_validation.get('expiry_date_formatted', 'unknown')}",
                    "severity": "high",
                    "type": "document_expired",
                    "days_expired": expiry_validation.get("days_expired")
                })
            
            if not doc_valid:
                risk_score += 50
                risk_factors.append({
                    "description": "Document validation failed",
                    "severity": "high",
                    "type": "document_validation"
                })
            
            # Check data comparison (MRZ vs request data)
            if data_comparison:
                if not data_comparison.get("all_match", False):
                    mismatch_count = data_comparison.get("mismatch_count", 0)
                    risk_score += mismatch_count * 10  # 10 points per mismatch
                    for mismatch in data_comparison.get("mismatches", []):
                        risk_factors.append({
                            "description": f"MRZ data mismatch: {mismatch['field']} (MRZ: {mismatch['mrz_value']}, Request: {mismatch['request_value']})",
                            "severity": "medium" if mismatch.get("similarity", 0) > 0.7 else "high",
                            "type": "data_mismatch",
                            "field": mismatch["field"]
                        })
                else:
                    risk_factors.append({
                        "description": "All MRZ data matches request data",
                        "severity": "low",
                        "type": "data_verification"
                    })
            
            # Check face match
            face_matched = face_match_result.get("matched", False)
            if not face_matched:
                risk_score += 50
                risk_factors.append({
                    "description": "Face match failed",
                    "severity": "high",
                    "type": "face_match"
                })
            
            # Cap the risk score at 100
            risk_score = min(100, risk_score)
            
            # Determine risk level
            if risk_score >= 70:
                risk_level = "high"
            elif risk_score >= 30:
                risk_level = "medium"
            else:
                risk_level = "low"
            
            # Add passed validations as low severity factors
            if doc_valid:
                risk_factors.append({
                    "description": "Document validation passed",
                    "severity": "low",
                    "type": "document_validation"
                })
                
            if face_matched:
                risk_factors.append({
                    "description": "Face match passed",
                    "severity": "low",
                    "type": "face_match"
                })
            
            # Prepare verification result structure matching KYCResponse model
            verification_result = {
                "document_verified": doc_valid,
                "face_match": face_match_result["matched"],
                "document_validation": {
                    "valid": doc_valid,
                    "error": document_validation.get("error"),
                    "details": document_validation.get("details", []),
                    "mrz_data": document_validation.get("mrz_data"),
                    "expiry_validation": expiry_validation
                },
                "data_comparison": data_comparison,
                "face_match_details": {
                    "matched": face_match_result["matched"],
                    "score": face_match_result["score"],
                    "document_face_count": face_match_result["document_face_count"],
                    "selfie_face_count": face_match_result["selfie_face_count"],
                    "error": face_match_result.get("error"),
                    "details": face_match_result.get("details", [])
                }
            }
            
            # Prepare response
            result = {
                "request_id": request_id,
                "status": "completed",
                "risk_score": risk_score,
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "timestamp": datetime.utcnow().isoformat(),
                "verification_result": verification_result,
                "metadata": {
                    "document": document_info,
                    "selfie": selfie_info
                }
            }
            
            # Log successful processing
            logger.info(f"KYC processing completed for request {request_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in KYC processing: {str(e)}", exc_info=True)
            raise