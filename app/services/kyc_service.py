"""
KYC (Know Your Customer) service
"""
from typing import Dict, Any, Optional, List
from .risk_engine import RiskEngine
from ..core.validation import FieldValidator
from ..core.logger import log_audit_event


class KYCService:
    """KYC verification service"""
    
    @staticmethod
    def verify(
        request_id: str,
        full_name: str,
        dob: str,
        nationality: str,
        document_type: str,
        document_number: str,
        # Future: document_image, selfie_image
        face_match_score: Optional[float] = None,
        face_match_result: Optional[bool] = None,
        ocr_quality: Optional[float] = None,
        document_expired: bool = False,
        document_expiring_soon: bool = False,
        missing_fields: Optional[List[str]] = None,
        data_quality_issues: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Perform KYC verification
        
        Args:
            full_name: Full name from document
            dob: Date of birth
            nationality: Nationality code
            document_type: Type of document (passport, id_card, etc.)
            document_number: Document number
            face_match_score: Face match similarity (0.0-1.0)
            face_match_result: Whether face match passed
            ocr_quality: OCR extraction quality (0.0-1.0)
            document_expired: Whether document is expired
            document_expiring_soon: Whether document expires soon
            missing_fields: List of missing required fields
            data_quality_issues: List of data quality issues
            
        Returns:
            Dictionary with status, risk_score, risk_level, and details
        """
        # Validate all KYC fields
        validation_result = FieldValidator.validate_kyc_fields(
            full_name=full_name,
            dob=dob,
            nationality=nationality,
            document_type=document_type,
            document_number=document_number
        )
        
        # Combine validation errors with any provided data quality issues
        all_data_quality_issues = (data_quality_issues or []) + validation_result.get("data_quality_issues", [])
        
        # Use detected missing fields if not provided
        detected_missing_fields = validation_result.get("missing_fields", [])
        if missing_fields:
            # Merge provided missing fields with detected ones
            all_missing_fields = list(set((missing_fields or []) + detected_missing_fields))
        else:
            all_missing_fields = detected_missing_fields
        
        # Document is valid if validation passes and document number is valid
        document_valid = (
            validation_result["is_valid"] and
            len(validation_result.get("validation_errors", [])) == 0 and
            bool(document_number and len(document_number) > 3)
        )
        
        # Calculate risk using RiskEngine
        risk_result = RiskEngine.calculate_kyc_risk_score(
            document_valid=document_valid,
            face_match_score=face_match_score,
            face_match_result=face_match_result,
            ocr_quality=ocr_quality,
            document_expired=document_expired,
            document_expiring_soon=document_expiring_soon,
            missing_fields=all_missing_fields,
            data_quality_issues=all_data_quality_issues
        )
        
        # Determine status based on risk level
        risk_level = risk_result["risk_level"]
        if risk_level.value == "high":
            status = "fail"
        elif risk_level.value == "medium":
            status = "review"
        else:
            status = "pass"
        
        # Build details list
        details = []
        
        # Validation results
        if validation_result["is_valid"]:
            details.append("All fields validated successfully")
        else:
            if validation_result.get("validation_errors"):
                for error in validation_result["validation_errors"]:
                    details.append(f"Validation error: {error}")
            if validation_result.get("missing_fields"):
                details.append(f"Missing required fields: {', '.join(validation_result['missing_fields'])}")
        
        # Document validation
        if document_valid:
            details.append("Document format valid")
        else:
            details.append("Document format invalid")
        
        # Face match
        if face_match_result is True:
            details.append("Face match passed")
        elif face_match_result is False:
            details.append("Face match failed")
        
        # Document expiry
        if document_expired:
            details.append("Document expired")
        elif document_expiring_soon:
            details.append("Document expiring soon")
        
        # Missing fields
        if all_missing_fields:
            details.append(f"Missing fields: {', '.join(all_missing_fields)}")
        
        # Data quality issues
        if all_data_quality_issues:
            for issue in all_data_quality_issues:
                details.append(f"Data quality: {issue}")
        
        # Add risk factor descriptions
        for factor in risk_result.get("risk_factors", []):
            if isinstance(factor, dict):
                details.append(factor.get("description", "Risk factor detected"))
        
        result = {
            "request_id": request_id,
            "status": status,
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
            "details": details
        }
        
        # Log audit event
        log_audit_event(
            request_id=request_id,
            check_type="kyc",
            action="verify",
            result={
                "status": status,
                "risk_score": risk_result["risk_score"],
                "risk_level": risk_result["risk_level"].value
            },
            metadata={
                "document_type": document_type,
                "nationality": nationality,
                "has_face_match": face_match_result is not None
            }
        )
        
        return result

