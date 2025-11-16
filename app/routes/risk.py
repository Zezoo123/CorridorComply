"""
Combined risk assessment endpoint
"""
from fastapi import APIRouter, HTTPException
from ..models.risk import CombinedRiskRequest, CombinedRiskResponse
from ..services.risk_engine import RiskEngine
from ..services.aml_service import AMLService
from ..services.kyc_service import KYCService
from ..core.utils import generate_request_id
from ..core.logger import log_audit_event

router = APIRouter()


@router.post("/combined", response_model=CombinedRiskResponse)
async def get_combined_risk(payload: CombinedRiskRequest):
    """
    Calculate combined risk score from both AML and KYC checks.
    
    You can provide:
    - Raw data (aml_data and/or kyc_data) - will compute risk scores
    - Pre-calculated risk scores (aml_risk and/or kyc_risk) - will use directly
    - Mix of both
    
    The combined risk score weights AML at 60% and KYC at 40% when both are provided.
    """
    request_id = generate_request_id()
    
    aml_risk_data = None
    kyc_risk_data = None
    details = []
    
    # Process AML risk
    if payload.aml_risk:
        # Use pre-calculated AML risk
        aml_risk_data = {
            "risk_score": payload.aml_risk.risk_score,
            "risk_level": payload.aml_risk.risk_level,
            "risk_factors": payload.aml_risk.risk_factors
        }
        details.append(f"Using pre-calculated AML risk: {payload.aml_risk.risk_score}")
    elif payload.aml_data:
        # Calculate AML risk from raw data using the service
        aml_result = AMLService.screen(
            request_id=request_id,
            full_name=payload.aml_data.full_name,
            dob=payload.aml_data.dob,
            nationality=payload.aml_data.nationality
        )
        # We need to get the full risk data with factors, so we'll call the risk engine directly
        # This is a bit of duplication but ensures we get all risk factors
        from ..services.sanctions_loader import SanctionsLoader
        from ..core.fuzzy_match import fuzzy_name_match
        import pandas as pd
        
        sanctions_df = SanctionsLoader.load_sanctions()
        matches = []
        
        if not sanctions_df.empty and "name" in sanctions_df.columns:
            for _, row in sanctions_df.iterrows():
                if pd.isna(row.get("name")):
                    continue
                score = fuzzy_name_match(payload.aml_data.full_name, row["name"])
                if score >= 85:  # SIMILARITY_THRESHOLD
                    confidence = RiskEngine.get_confidence_level(score)
                    dob_match = False
                    if payload.aml_data.dob and row.get("dob"):
                        dob_match = payload.aml_data.dob.strip() == str(row.get("dob")).strip()
                    country_match = False
                    if payload.aml_data.nationality and row.get("country"):
                        country_match = payload.aml_data.nationality.strip().upper() == str(row.get("country")).strip().upper()
                    
                    matches.append({
                        "sanctioned_name": row["name"],
                        "source": row.get("source", "unknown"),
                        "similarity": score,
                        "confidence": confidence,
                        "dob": row.get("dob", None),
                        "dob_match": dob_match if payload.aml_data.dob else None,
                        "country": row.get("country", None),
                        "country_match": country_match if payload.aml_data.nationality else None,
                    })
        
        sanctions_match = len(matches) > 0
        aml_risk_data = RiskEngine.calculate_aml_risk_score(
            matches=matches,
            has_sanctions_match=sanctions_match,
            has_pep_match=False
        )
        details.append(f"AML risk calculated: {aml_risk_data['risk_score']} ({aml_risk_data['risk_level'].value})")
    
    # Process KYC risk
    if payload.kyc_risk:
        # Use pre-calculated KYC risk
        kyc_risk_data = {
            "risk_score": payload.kyc_risk.risk_score,
            "risk_level": payload.kyc_risk.risk_level,
            "risk_factors": payload.kyc_risk.risk_factors
        }
        details.append(f"Using pre-calculated KYC risk: {payload.kyc_risk.risk_score}")
    elif payload.kyc_data:
        # Calculate KYC risk from raw data
        kyc_result = KYCService.verify(
            request_id=request_id,
            full_name=payload.kyc_data.full_name,
            dob=payload.kyc_data.dob,
            nationality=payload.kyc_data.nationality,
            document_type=payload.kyc_data.document_type,
            document_number=payload.kyc_data.document_number,
            face_match_score=payload.kyc_data.face_match_score,
            face_match_result=payload.kyc_data.face_match_result,
            ocr_quality=payload.kyc_data.ocr_quality,
            document_expired=payload.kyc_data.document_expired,
            document_expiring_soon=payload.kyc_data.document_expiring_soon,
            missing_fields=payload.kyc_data.missing_fields,
            data_quality_issues=payload.kyc_data.data_quality_issues
        )
        # Extract risk data from KYC result
        kyc_risk_data = {
            "risk_score": kyc_result.get("risk_score", 0),
            "risk_level": kyc_result.get("risk_level"),
            "risk_factors": []  # Will be populated from risk engine
        }
        # Recalculate to get full risk factors
        document_valid = bool(payload.kyc_data.document_number and len(payload.kyc_data.document_number) > 3)
        kyc_risk_data = RiskEngine.calculate_kyc_risk_score(
            document_valid=document_valid,
            face_match_score=payload.kyc_data.face_match_score,
            face_match_result=payload.kyc_data.face_match_result,
            ocr_quality=payload.kyc_data.ocr_quality,
            document_expired=payload.kyc_data.document_expired,
            document_expiring_soon=payload.kyc_data.document_expiring_soon,
            missing_fields=payload.kyc_data.missing_fields or [],
            data_quality_issues=payload.kyc_data.data_quality_issues or []
        )
        details.append(f"KYC risk calculated: {kyc_risk_data['risk_score']} ({kyc_risk_data['risk_level'].value})")
    
    # Validate that at least one risk type is provided
    if not aml_risk_data and not kyc_risk_data:
        raise HTTPException(
            status_code=400,
            detail="At least one of aml_data, kyc_data, aml_risk, or kyc_risk must be provided"
        )
    
    # Calculate combined risk
    combined_result = RiskEngine.calculate_combined_risk_score(
        aml_risk_data=aml_risk_data,
        kyc_risk_data=kyc_risk_data
    )
    
    # Build response details
    if aml_risk_data:
        details.append(f"AML: {aml_risk_data.get('risk_score', 0)} ({aml_risk_data.get('risk_level', 'unknown')})")
    if kyc_risk_data:
        details.append(f"KYC: {kyc_risk_data.get('risk_score', 0)} ({kyc_risk_data.get('risk_level', 'unknown')})")
    details.append(f"Combined: {combined_result['risk_score']} ({combined_result['risk_level'].value})")
    
    # Add risk factor summaries
    aml_factors = [f for f in combined_result.get("risk_factors", []) if isinstance(f, dict) and f.get("type", "").startswith("aml_")]
    kyc_factors = [f for f in combined_result.get("risk_factors", []) if isinstance(f, dict) and f.get("type", "").startswith("kyc_")]
    
    if aml_factors:
        details.append(f"AML risk factors: {len(aml_factors)}")
    if kyc_factors:
        details.append(f"KYC risk factors: {len(kyc_factors)}")
    
    response = CombinedRiskResponse(
        request_id=request_id,
        combined_risk_score=combined_result["risk_score"],
        combined_risk_level=combined_result["risk_level"],
        risk_factors=combined_result["risk_factors"],
        aml_risk_score=aml_risk_data.get("risk_score") if aml_risk_data else None,
        aml_risk_level=aml_risk_data.get("risk_level") if aml_risk_data else None,
        kyc_risk_score=kyc_risk_data.get("risk_score") if kyc_risk_data else None,
        kyc_risk_level=kyc_risk_data.get("risk_level") if kyc_risk_data else None,
        details=details
    )
    
    # Log audit event for combined risk
    log_audit_event(
        request_id=request_id,
        check_type="risk",
        action="combined",
        result={
            "combined_risk_score": combined_result["risk_score"],
            "combined_risk_level": combined_result["risk_level"].value,
            "aml_risk_score": aml_risk_data.get("risk_score") if aml_risk_data else None,
            "kyc_risk_score": kyc_risk_data.get("risk_score") if kyc_risk_data else None
        },
        metadata={
            "has_aml_data": payload.aml_data is not None or payload.aml_risk is not None,
            "has_kyc_data": payload.kyc_data is not None or payload.kyc_risk is not None
        }
    )
    
    return response

