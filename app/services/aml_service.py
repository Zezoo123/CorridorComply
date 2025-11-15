from typing import Dict, Any
from .sanctions_loader import SanctionsLoader
from ..core.fuzzy_match import fuzzy_name_match

SIMILARITY_THRESHOLD = 85  # adjustable

class AMLService:

    @staticmethod
    def screen(full_name: str, dob: str, nationality: str) -> Dict[str, Any]:
        sanctions_df = SanctionsLoader.load_sanctions()

        matches = []

        for _, row in sanctions_df.iterrows():
            score = fuzzy_name_match(full_name, row["name"])
            if score >= SIMILARITY_THRESHOLD:
                matches.append({
                    "sanctioned_name": row["name"],
                    "source": row["source"],
                    "similarity": score,
                    "dob": row.get("dob", None),
                    "country": row.get("country", None),
                })

        # Basic risk scoring logic:
        if matches:
            risk_score = min(100, 50 + len(matches) * 10)
            pep_match = True  # treat as PEP-like if fuzzy match
            sanctions_match = True
        else:
            risk_score = 5
            pep_match = False
            sanctions_match = False

        return {
            "sanctions_match": sanctions_match,
            "pep_match": pep_match,
            "risk_score": risk_score,
            "details": [
                f"Found {len(matches)} similar names" if matches else "No matches found",
            ],
            "matches": matches,
        }
