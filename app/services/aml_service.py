from typing import Any, Dict, List, Optional

from .risk_engine import RiskEngine
from rapidfuzz import fuzz

from ..core.names import normalize
from .screening import SIMILARITY_THRESHOLD, get_index


NEAR_EXACT_VARIANT = 95


def _corroborated(c) -> bool:
    """Whether a hit found only through a shortened form of the name, scoring below the
    threshold on the full name, is worth showing.

    Date of birth agrees: yes. Date of birth differs (full dates on both sides): no, that is a
    namesake. No date of birth on the entry: no if the nationality differs; otherwise only if
    the shortened form matched the list name almost exactly."""
    if c.dob_agreement in ("exact", "year"):
        return True
    if c.dob_agreement == "mismatch" or c.nationality_agreement == "mismatch":
        return False
    return (c.variant_similarity or 0) >= NEAR_EXACT_VARIANT


class AMLService:

    @staticmethod
    def screen_sync(full_name: str, dob: Optional[str] = None, nationality: Optional[str] = None,
                    entity_type: str = "person", request_id: str = "", threshold: int = SIMILARITY_THRESHOLD,
                    use_variants: bool = True, id_numbers: Optional[List[str]] = None) -> Dict[str, Any]:
        index = get_index()
        # Population-aware name variants (Filipino middle names, patronymics) so a
        # listed person is not missed because the customer supplied a longer form.
        variants = [full_name]
        name_flags: List[str] = []
        if use_variants and entity_type == "person":
            from ..corridor.names import analyze
            info = analyze(full_name, nationality)
            name_flags = info.flags
            variants = info.variants or [full_name]
        best: Dict[str, Any] = {}
        q_full = normalize(full_name)
        for n, v in enumerate(variants):
            for c in index.screen(v, dob=dob, nationality=nationality, entity_type=entity_type, threshold=threshold,
                                  id_numbers=id_numbers if n == 0 else None):
                if c.match_type == "partial" and c.dob_agreement not in ("exact", "year"):
                    # Fewer names than the entry holds is only evidence together with the date of birth.
                    continue
                if n > 0 and c.match_type not in ("identifier", "partial"):
                    # A hit found through a shortened form of the name is scored on the name the
                    # customer actually supplied. "Muhammad Imran Khan" shortened to "Muhammad Khan"
                    # equals the alias "Khan Muhammad" exactly, but the person supplied three names.
                    c.screened_as, c.variant_similarity = v, c.similarity
                    c.similarity = fuzz.token_sort_ratio(q_full, normalize(c.matched_name))
                    if c.similarity < threshold and not _corroborated(c):
                        continue
                key = f"{c.entry.source}:{c.entry.dataid}"
                if key not in best or c.similarity > best[key].similarity:
                    best[key] = c
        candidates = sorted(best.values(), key=lambda c: (c.match_type != "identifier", -c.similarity, -(c.name_similarity or 0),
                                                           c.dob_agreement != "exact", c.entry.name))[:25]

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
            if any(m["match_type"] == "identifier" for m in matches):
                details.append("Customer identity number appears on a list")
            if any(m["match_type"] == "alias" for m in matches):
                details.append("Matched on a listed alias")
            if any(m["match_type"] == "partial" for m in matches):
                details.append("Name supplied is part of a listed name; date of birth agrees")
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
            "name_flags": name_flags,
            "screened_variants": variants,
        }

    @staticmethod
    async def screen(request_id: str, full_name: str, dob: Optional[str] = None,
                     nationality: Optional[str] = None, entity_type: str = "person") -> Dict[str, Any]:
        return AMLService.screen_sync(full_name, dob=dob, nationality=nationality,
                                      entity_type=entity_type, request_id=request_id)
