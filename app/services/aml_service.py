from typing import Dict, Any, List
import pandas as pd
from .sanctions_loader import SanctionsLoader
from .risk_engine import RiskEngine
from ..core.fuzzy_match import fuzzy_name_match
from ..core.logger import log_audit_event

SIMILARITY_THRESHOLD = 85  # adjustable

class AMLService:

    @staticmethod
    async def screen(request_id: str, full_name: str, dob: str, nationality: str) -> Dict[str, Any]:
        sanctions_df = SanctionsLoader.load_sanctions()

        matches = []

        # Only iterate if DataFrame is not empty and has data
        if not sanctions_df.empty and "name" in sanctions_df.columns:
            for _, row in sanctions_df.iterrows():
                # Check if name column exists and has a value
                if pd.isna(row.get("name")):
                    continue
                    
                score = fuzzy_name_match(full_name, row["name"])
                if score >= SIMILARITY_THRESHOLD:
                    # Get confidence level for this match
                    confidence = RiskEngine.get_confidence_level(score)
                    
                    # Additional validation: check DOB if available
                    dob_match = False
                    if dob and row.get("dob"):
                        dob_match = dob.strip() == str(row.get("dob")).strip()
                    
                    # Check nationality if available
                    country_match = False
                    if nationality and row.get("country"):
                        country_match = nationality.strip().upper() == str(row.get("country")).strip().upper()
                    
                    matches.append({
                        "sanctioned_name": row["name"],
                        "source": row.get("source", "unknown"),
                        "similarity": score,
                        "confidence": confidence,
                        "dob": row.get("dob", None),
                        "dob_match": dob_match if dob else None,
                        "country": row.get("country", None),
                        "country_match": country_match if nationality else None,
                    })

        # Determine match types
        sanctions_match = len(matches) > 0
        pep_match = False  # TODO: Implement separate PEP screening
        
        # Calculate risk using RiskEngine
        risk_result = RiskEngine.calculate_aml_risk_score(
            matches=matches,
            has_sanctions_match=sanctions_match,
            has_pep_match=pep_match
        )
        
        # Build details list
        details = []
        if matches:
            details.append(f"Found {len(matches)} similar name(s)")
            high_conf_matches = [m for m in matches if m.get("confidence") == "high"]
            if high_conf_matches:
                details.append(f"{len(high_conf_matches)} high confidence match(es)")
            if any(m.get("dob_match") for m in matches if m.get("dob_match") is not None):
                details.append("DOB match found")
            if any(m.get("country_match") for m in matches if m.get("country_match") is not None):
                details.append("Country match found")
        else:
            details.append("No matches found")
        
        # Add risk factor descriptions
        for factor in risk_result.get("risk_factors", []):
            if isinstance(factor, dict):
                details.append(f"{factor.get('description', 'Risk factor detected')}")
            else:
                details.append(f"Risk factor: {factor}")

        result = {
            "request_id": request_id,
            "sanctions_match": sanctions_match,
            "pep_match": pep_match,
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
            "details": details,
            "matches": matches,
        }
        
        # Log audit event
        log_audit_event(
            event_type="aml_screening",
            data={
                "status": "success",
                "request_id": request_id,
                "full_name": full_name,
                "nationality": nationality,
                "sanctions_match": sanctions_match,
                "pep_match": pep_match,
                "risk_score": risk_result["risk_score"],
                "risk_level": risk_result["risk_level"].value,
                "match_count": len(matches)
            },
            request=None  # No request object available in the service layer
        )
        
        return result
