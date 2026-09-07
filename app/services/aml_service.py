from typing import Any, Dict, List, Optional

from .risk_engine import RiskEngine
from .screening import SIMILARITY_THRESHOLD, get_index


class AMLService:

    @staticmethod
    def screen_sync(full_name: str, dob: Optional[str] = None, nationality: Optional[str] = None,
                    entity_type: str = "person", request_id: str = "") -> Dict[str, Any]:
        index = get_index()
        candidates = index.screen(full_name, dob=dob, nationality=nationality, entity_type=entity_type,
                                  threshold=SIMILARITY_THRESHOLD)

        matches: List[Dict[str, Any]] = []
        for c in candidates:
            m = c.to_dict()
            m["confidence"] = RiskEngine.get_confidence_level(c.similarity)
            matches.append(m)

        sanctions_match = len(matches) > 0
        pep_match = False  # TODO: PEP screening needs a licensed data source

        risk_result = RiskEngine.calculate_aml_risk_score(
            matches=matches, has_sanctions_match=sanctions_match, has_pep_match=pep_match
        )

        details: List[str] = []
        if matches:
            details.append(f"Found {len(matches)} similar name(s)")
            high = [m for m in matches if m["confidence"] == "high"]
            if high:
                details.append(f"{len(high)} high confidence match(es)")
            if any(m["match_type"] == "alias" for m in matches):
                details.append("Matched on a listed alias")
            if any(m["dob_agreement"] == "exact" for m in matches):
                details.append("DOB match found")
            elif any(m["dob_agreement"] == "year" for m in matches):
                details.append("Year of birth matches")
            if any(m["country_match"] for m in matches):
                details.append("Nationality match found")
        else:
            details.append("No matches found")
        for factor in risk_result.get("risk_factors", []):
            details.append(factor.get("description", "Risk factor detected") if isinstance(factor, dict) else f"Risk factor: {factor}")

        return {
            "request_id": request_id,
            "sanctions_match": sanctions_match,
            "pep_match": pep_match,
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
            "risk_factors": risk_result["risk_factors"],
            "details": details,
            "matches": matches,
            "list_version": index.list_version,
        }

    @staticmethod
    async def screen(request_id: str, full_name: str, dob: Optional[str] = None,
                     nationality: Optional[str] = None, entity_type: str = "person") -> Dict[str, Any]:
        return AMLService.screen_sync(full_name, dob=dob, nationality=nationality,
                                      entity_type=entity_type, request_id=request_id)
