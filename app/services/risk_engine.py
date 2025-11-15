"""
Risk scoring and level calculation engine
"""
from typing import Dict, Any, List
from ..models.risk import RiskLevel


class RiskEngine:
    """Centralized risk calculation logic"""
    
    # Risk score thresholds
    HIGH_RISK_THRESHOLD = 70
    MEDIUM_RISK_THRESHOLD = 40
    
    # Similarity confidence levels
    HIGH_CONFIDENCE_THRESHOLD = 95  # 95-100% = high confidence
    MEDIUM_CONFIDENCE_THRESHOLD = 85  # 85-94% = medium confidence
    # Below 85% = low confidence (but still above match threshold)
    
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
        has_pep_match: bool
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive AML risk score
        
        Args:
            matches: List of match results
            has_sanctions_match: Whether sanctions match was found
            has_pep_match: Whether PEP match was found
            
        Returns:
            Dictionary with risk_score, risk_level, and details
        """
        risk_score = 0
        risk_factors = []
        
        if has_sanctions_match:
            # Sanctions matches are highest risk
            risk_score += 50
            risk_factors.append("sanctions_match")
            
            # Boost risk based on match confidence
            if matches:
                max_similarity = max(m.get("similarity", 0) for m in matches)
                if max_similarity >= cls.HIGH_CONFIDENCE_THRESHOLD:
                    risk_score += 30  # Exact/high confidence match
                    risk_factors.append("high_confidence_match")
                elif max_similarity >= cls.MEDIUM_CONFIDENCE_THRESHOLD:
                    risk_score += 15  # Medium confidence match
                    risk_factors.append("medium_confidence_match")
                else:
                    risk_score += 5  # Low confidence match
                    risk_factors.append("low_confidence_match")
        
        if has_pep_match and not has_sanctions_match:
            # PEP matches are medium risk
            risk_score += 30
            risk_factors.append("pep_match")
        
        # Multiple matches increase risk
        if len(matches) > 1:
            risk_score += min(20, len(matches) * 5)
            risk_factors.append(f"multiple_matches_{len(matches)}")
        
        # Cap at 100
        risk_score = min(100, risk_score)
        
        risk_level = cls.calculate_risk_level(risk_score)
        
        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors
        }

