# In app/services/kyc_service.py
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from PIL import Image
import io
import base64

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
            # Heavy ML dependencies are imported lazily so the API (and the
            # screening-only deployment) can start without TensorFlow/EasyOCR.
            from app.core.ocr import validate_document_ocr
            from app.services.face_match import FaceMatchingService

            logger.info(f"Starting KYC processing for request {request_id}")
            
            # Process document and selfie images
            # Calculate approximate size by saving to bytes
            # Handle cases where image can't be fully loaded (e.g., 1x1 test images)
            try:
                doc_bytes = io.BytesIO()
                document_image.save(doc_bytes, format='JPEG')
                doc_size_kb = len(doc_bytes.getvalue()) / 1024
            except (OSError, IOError, Exception) as e:
                # If image can't be saved (e.g., broken data stream), estimate size from dimensions
                logger.warning(f"Could not calculate document image size by saving: {str(e)}. Estimating from dimensions.")
                # Estimate: width * height * 3 bytes (RGB) / 1024
                doc_size_kb = (document_image.width * document_image.height * 3) / 1024 if hasattr(document_image, 'width') and hasattr(document_image, 'height') else 0
            
            try:
                selfie_bytes = io.BytesIO()
                selfie_image.save(selfie_bytes, format='JPEG')
                selfie_size_kb = len(selfie_bytes.getvalue()) / 1024
            except (OSError, IOError, Exception) as e:
                # If image can't be saved (e.g., broken data stream), estimate size from dimensions
                logger.warning(f"Could not calculate selfie image size by saving: {str(e)}. Estimating from dimensions.")
                # Estimate: width * height * 3 bytes (RGB) / 1024
                selfie_size_kb = (selfie_image.width * selfie_image.height * 3) / 1024 if hasattr(selfie_image, 'width') and hasattr(selfie_image, 'height') else 0
            
            # Get image properties safely
            document_info = {
                "width": getattr(document_image, 'width', 0),
                "height": getattr(document_image, 'height', 0),
                "format": getattr(document_image, 'format', None) or "JPEG",
                "mode": getattr(document_image, 'mode', 'RGB'),
                "size_kb": doc_size_kb
            }
            
            selfie_info = {
                "width": getattr(selfie_image, 'width', 0),
                "height": getattr(selfie_image, 'height', 0),
                "format": getattr(selfie_image, 'format', None) or "JPEG",
                "mode": getattr(selfie_image, 'mode', 'RGB'),
                "size_kb": selfie_size_kb
            }
            
            # Log image information
            logger.info(f"Document image: {document_info}")
            logger.info(f"Selfie image: {selfie_info}")
            
            # Perform document OCR validation
            logger.info(f"Starting document OCR validation for request {request_id}")
            document_validation = validate_document_ocr(
                document_image,
                document_type=document_type,
                country_code=issuing_country or nationality
            )
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
            
            # Risk score comes from the shared RiskEngine so KYC, AML and the
            # combined endpoint can never disagree about thresholds.
            from app.services.risk_engine import RiskEngine

            doc_valid = document_validation.get("valid", False)
            expiry_validation = document_validation.get("expiry_validation", {}) or {}
            face_matched = face_match_result.get("matched", False)
            risk = RiskEngine.calculate_kyc_risk_score(
                document_valid=doc_valid,
                face_match_score=face_match_result.get("score") if not face_match_result.get("error") else None,
                face_match_result=face_matched,
                ocr_quality=document_validation.get("ocr_confidence"),
                document_expired=bool(expiry_validation.get("is_expired")),
                mrz_mismatches=(data_comparison or {}).get("mismatches") if data_comparison else None,
            )
            risk_score = risk["risk_score"]
            risk_level = risk["risk_level"].value
            risk_factors = list(risk["risk_factors"])
            if doc_valid:
                risk_factors.append({"description": "Document validation passed", "severity": "low", "type": "document_validation"})
            if face_matched:
                risk_factors.append({"description": "Face match passed", "severity": "low", "type": "face_match"})
            if data_comparison and data_comparison.get("all_match"):
                risk_factors.append({"description": "All MRZ data matches request data", "severity": "low", "type": "data_verification"})
            
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