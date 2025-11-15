"""
KYC (Know Your Customer) service
"""
from typing import Dict, Any, Optional, List
from .risk_engine import RiskEngine


class KYCService:
    """KYC verification service"""
    
    @staticmethod
    def verify(
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
        # TODO: Implement actual document validation, OCR, face matching
        # For now, using placeholder logic
        
        # Basic document validation (stub)
        document_valid = bool(document_number and len(document_number) > 3)
        
        # Calculate risk using RiskEngine
        risk_result = RiskEngine.calculate_kyc_risk_score(
            document_valid=document_valid,
            face_match_score=face_match_score,
            face_match_result=face_match_result,
            ocr_quality=ocr_quality,
            document_expired=document_expired,
            document_expiring_soon=document_expiring_soon,
            missing_fields=missing_fields or [],
            data_quality_issues=data_quality_issues or []
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
        if document_valid:
            details.append("Document format valid")
        else:
            details.append("Document format invalid")
        
        if face_match_result is True:
            details.append("Face match passed")
        elif face_match_result is False:
            details.append("Face match failed")
        
        if document_expired:
            details.append("Document expired")
        elif document_expiring_soon:
            details.append("Document expiring soon")
        
        if missing_fields:
            details.append(f"Missing fields: {', '.join(missing_fields)}")
        
        # Add risk factor descriptions
        for factor in risk_result.get("risk_factors", []):
            if isinstance(factor, dict):
                details.append(factor.get("description", "Risk factor detected"))
        
        return {
            "status": status,
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
            "details": details
        }

