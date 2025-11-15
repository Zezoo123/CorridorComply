"""
Unified Risk Engine for both AML and KYC risk scoring
"""
from typing import Dict, Any, List, Optional
from enum import Enum
from ..models.risk import RiskLevel


class RiskFactorType(str, Enum):
    """Types of risk factors"""
    AML_SANCTIONS = "aml_sanctions"
    AML_PEP = "aml_pep"
    AML_WATCHLIST = "aml_watchlist"
    KYC_DOCUMENT = "kyc_document"
    KYC_FACE_MATCH = "kyc_face_match"
    KYC_OCR = "kyc_ocr"
    KYC_VALIDATION = "kyc_validation"
    KYC_EXPIRY = "kyc_expiry"
    GENERAL_DATA_QUALITY = "general_data_quality"


class RiskEngine:
    """Unified risk calculation engine for AML and KYC"""
    
    # Risk score thresholds
    HIGH_RISK_THRESHOLD = 70
    MEDIUM_RISK_THRESHOLD = 40
    
    # Similarity confidence levels
    HIGH_CONFIDENCE_THRESHOLD = 95  # 95-100% = high confidence
    MEDIUM_CONFIDENCE_THRESHOLD = 85  # 85-94% = medium confidence
    # Below 85% = low confidence (but still above match threshold)
    
    # KYC-specific thresholds
    FACE_MATCH_HIGH_THRESHOLD = 0.85  # 85%+ similarity = high confidence
    FACE_MATCH_MEDIUM_THRESHOLD = 0.70  # 70-84% = medium confidence
    
    @classmethod
    def calculate_risk_level(cls, risk_score: int) -> RiskLevel:
        """
        Calculate risk level based on risk score
        
        Args:
            risk_score: Risk score (0-100)
            
        Returns:
            RiskLevel enum value
        """
        if risk_score >= cls.HIGH_RISK_THRESHOLD:
            return RiskLevel.HIGH
        elif risk_score >= cls.MEDIUM_RISK_THRESHOLD:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    @classmethod
    def get_confidence_level(cls, similarity_score: int) -> str:
        """
        Get confidence level for a match based on similarity score
        
        Args:
            similarity_score: Similarity score (0-100)
            
        Returns:
            Confidence level: "high", "medium", or "low"
        """
        if similarity_score >= cls.HIGH_CONFIDENCE_THRESHOLD:
            return "high"
        elif similarity_score >= cls.MEDIUM_CONFIDENCE_THRESHOLD:
            return "medium"
        else:
            return "low"
    
    @classmethod
    def calculate_aml_risk_score(
        cls,
        matches: List[Dict[str, Any]],
        has_sanctions_match: bool,
        has_pep_match: bool = False,
        has_watchlist_match: bool = False
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive AML risk score
        
        Args:
            matches: List of match results
            has_sanctions_match: Whether sanctions match was found
            has_pep_match: Whether PEP match was found
            has_watchlist_match: Whether watchlist match was found
            
        Returns:
            Dictionary with risk_score, risk_level, and risk_factors
        """
        risk_score = 0
        risk_factors = []
        
        if has_sanctions_match:
            # Sanctions matches are highest risk
            risk_score += 50
            risk_factors.append({
                "type": RiskFactorType.AML_SANCTIONS.value,
                "severity": "high",
                "description": "Sanctions list match found"
            })
            
            # Boost risk based on match confidence
            if matches:
                max_similarity = max(m.get("similarity", 0) for m in matches)
                confidence = cls.get_confidence_level(max_similarity)
                
                if confidence == "high":
                    risk_score += 30  # Exact/high confidence match
                    risk_factors.append({
                        "type": RiskFactorType.AML_SANCTIONS.value,
                        "severity": "high",
                        "description": "High confidence sanctions match"
                    })
                elif confidence == "medium":
                    risk_score += 15  # Medium confidence match
                    risk_factors.append({
                        "type": RiskFactorType.AML_SANCTIONS.value,
                        "severity": "medium",
                        "description": "Medium confidence sanctions match"
                    })
                else:
                    risk_score += 5  # Low confidence match
                    risk_factors.append({
                        "type": RiskFactorType.AML_SANCTIONS.value,
                        "severity": "low",
                        "description": "Low confidence sanctions match"
                    })
                
                # Additional DOB/country match boosts
                if any(m.get("dob_match") for m in matches if m.get("dob_match") is not None):
                    risk_score += 10
                    risk_factors.append({
                        "type": RiskFactorType.AML_SANCTIONS.value,
                        "severity": "high",
                        "description": "DOB match with sanctions list"
                    })
                
                if any(m.get("country_match") for m in matches if m.get("country_match") is not None):
                    risk_score += 5
                    risk_factors.append({
                        "type": RiskFactorType.AML_SANCTIONS.value,
                        "severity": "medium",
                        "description": "Country match with sanctions list"
                    })
        
        if has_pep_match and not has_sanctions_match:
            # PEP matches are medium risk
            risk_score += 30
            risk_factors.append({
                "type": RiskFactorType.AML_PEP.value,
                "severity": "medium",
                "description": "PEP (Politically Exposed Person) match found"
            })
        
        if has_watchlist_match and not has_sanctions_match and not has_pep_match:
            # Watchlist matches are lower risk
            risk_score += 20
            risk_factors.append({
                "type": RiskFactorType.AML_WATCHLIST.value,
                "severity": "medium",
                "description": "Watchlist match found"
            })
        
        # Multiple matches increase risk
        if len(matches) > 1:
            additional_risk = min(20, len(matches) * 5)
            risk_score += additional_risk
            risk_factors.append({
                "type": RiskFactorType.AML_SANCTIONS.value,
                "severity": "high" if additional_risk >= 15 else "medium",
                "description": f"Multiple matches found ({len(matches)} matches)"
            })
        
        # Cap at 100
        risk_score = min(100, risk_score)
        
        risk_level = cls.calculate_risk_level(risk_score)
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors
        }
    
    @classmethod
    def calculate_kyc_risk_score(
        cls,
        document_valid: bool = True,
        face_match_score: Optional[float] = None,
        face_match_result: Optional[bool] = None,
        ocr_quality: Optional[float] = None,
        document_expired: bool = False,
        document_expiring_soon: bool = False,
        missing_fields: List[str] = None,
        data_quality_issues: List[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive KYC risk score
        
        Args:
            document_valid: Whether document format is valid
            face_match_score: Face match similarity score (0.0-1.0)
            face_match_result: Whether face match passed
            ocr_quality: OCR extraction quality score (0.0-1.0)
            document_expired: Whether document is expired
            document_expiring_soon: Whether document expires within 30 days
            missing_fields: List of missing required fields
            data_quality_issues: List of data quality issues
            
        Returns:
            Dictionary with risk_score, risk_level, and risk_factors
        """
        risk_score = 0
        risk_factors = []
        
        # Document validity
        if not document_valid:
            risk_score += 40
            risk_factors.append({
                "type": RiskFactorType.KYC_DOCUMENT.value,
                "severity": "high",
                "description": "Invalid document format"
            })
        
        # Face match risk
        if face_match_result is False:
            risk_score += 35
            risk_factors.append({
                "type": RiskFactorType.KYC_FACE_MATCH.value,
                "severity": "high",
                "description": "Face mismatch between document and selfie"
            })
        elif face_match_score is not None:
            if face_match_score < cls.FACE_MATCH_MEDIUM_THRESHOLD:
                risk_score += 20
                risk_factors.append({
                    "type": RiskFactorType.KYC_FACE_MATCH.value,
                    "severity": "medium",
                    "description": f"Low face match confidence ({face_match_score:.2%})"
                })
            elif face_match_score < cls.FACE_MATCH_HIGH_THRESHOLD:
                risk_score += 10
                risk_factors.append({
                    "type": RiskFactorType.KYC_FACE_MATCH.value,
                    "severity": "low",
                    "description": f"Moderate face match confidence ({face_match_score:.2%})"
                })
        
        # OCR quality
        if ocr_quality is not None:
            if ocr_quality < 0.5:
                risk_score += 25
                risk_factors.append({
                    "type": RiskFactorType.KYC_OCR.value,
                    "severity": "high",
                    "description": "Poor OCR extraction quality"
                })
            elif ocr_quality < 0.7:
                risk_score += 15
                risk_factors.append({
                    "type": RiskFactorType.KYC_OCR.value,
                    "severity": "medium",
                    "description": "Moderate OCR extraction quality"
                })
        
        # Document expiry
        if document_expired:
            risk_score += 30
            risk_factors.append({
                "type": RiskFactorType.KYC_EXPIRY.value,
                "severity": "high",
                "description": "Document has expired"
            })
        elif document_expiring_soon:
            risk_score += 10
            risk_factors.append({
                "type": RiskFactorType.KYC_EXPIRY.value,
                "severity": "low",
                "description": "Document expiring soon (within 30 days)"
            })
        
        # Missing fields
        if missing_fields:
            risk_score += min(20, len(missing_fields) * 5)
            risk_factors.append({
                "type": RiskFactorType.KYC_VALIDATION.value,
                "severity": "medium" if len(missing_fields) >= 2 else "low",
                "description": f"Missing required fields: {', '.join(missing_fields)}"
            })
        
        # Data quality issues
        if data_quality_issues:
            risk_score += min(15, len(data_quality_issues) * 3)
            risk_factors.append({
                "type": RiskFactorType.GENERAL_DATA_QUALITY.value,
                "severity": "low",
                "description": f"Data quality issues: {', '.join(data_quality_issues)}"
            })
        
        # Cap at 100
        risk_score = min(100, risk_score)
        
        risk_level = cls.calculate_risk_level(risk_score)
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors
        }
    
    @classmethod
    def calculate_combined_risk_score(
        cls,
        aml_risk_data: Optional[Dict[str, Any]] = None,
        kyc_risk_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate combined risk score from both AML and KYC checks
        
        Args:
            aml_risk_data: Result from calculate_aml_risk_score()
            kyc_risk_data: Result from calculate_kyc_risk_score()
            
        Returns:
            Dictionary with combined risk_score, risk_level, and risk_factors
        """
        combined_risk_score = 0
        all_risk_factors = []
        
        if aml_risk_data:
            aml_score = aml_risk_data.get("risk_score", 0)
            # AML risks are weighted more heavily
            combined_risk_score += aml_score * 0.6  # 60% weight
            all_risk_factors.extend(aml_risk_data.get("risk_factors", []))
        
        if kyc_risk_data:
            kyc_score = kyc_risk_data.get("risk_score", 0)
            # KYC risks are weighted less
            combined_risk_score += kyc_score * 0.4  # 40% weight
            all_risk_factors.extend(kyc_risk_data.get("risk_factors", []))
        
        # If only one type of risk data is provided, use it directly
        if aml_risk_data and not kyc_risk_data:
            combined_risk_score = aml_risk_data.get("risk_score", 0)
        elif kyc_risk_data and not aml_risk_data:
            combined_risk_score = kyc_risk_data.get("risk_score", 0)
        
        # Cap at 100
        combined_risk_score = min(100, int(combined_risk_score))
        
        risk_level = cls.calculate_risk_level(combined_risk_score)
        
        return {
            "risk_score": combined_risk_score,
            "risk_level": risk_level,
            "risk_factors": all_risk_factors,
            "aml_risk": aml_risk_data,
            "kyc_risk": kyc_risk_data
        }
