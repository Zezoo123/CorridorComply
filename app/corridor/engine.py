"""
Applies a corridor ruleset to a customer, a screening result and optional KYC
and beneficiary data, and returns a decision with every reason that fired.

All matching rules count. The outcome is the most severe one; the reasons are
all of them, so a reviewer sees the full picture and an auditor can replay it.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.dates import parse_iso_date
from .identifiers import check_id
from .names import analyze
from .schema import Condition, Rule, Ruleset, Severity, When

logger = logging.getLogger(__name__)

DEFAULT_RULES_DIR = Path(__file__).resolve().parent.parent.parent / "premium" / "corridor_rules"


# ------------------------------------------------------------- loading
class RulesetRegistry:
    def __init__(self, directory: Optional[Path] = None):
        self.directory = Path(os.getenv("CORRIDOR_RULES_DIR") or directory or DEFAULT_RULES_DIR)
        self._rulesets: Dict[str, Ruleset] = {}
        self._errors: Dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        self._rulesets, self._errors = {}, {}
        if not self.directory.exists():
            logger.warning(f"Corridor rules directory not found: {self.directory}")
            return
        for path in sorted(self.directory.glob("*.json")):
            if path.stat().st_size == 0 or path.name == "template.json":
                continue
            try:
                rs = Ruleset.model_validate(json.loads(path.read_text(encoding="utf-8")))
                self._rulesets[rs.id] = rs
                logger.info(f"Loaded corridor ruleset {rs.id} v{rs.version} ({rs.status}) from {path.name}")
            except Exception as e:
                self._errors[path.name] = str(e)
                logger.error(f"Invalid corridor ruleset {path.name}: {e}")

    def get(self, corridor_id: str) -> Ruleset:
        rs = self._rulesets.get(corridor_id.upper())
        if rs is None:
            raise KeyError(f"No ruleset for corridor {corridor_id}; loaded: {sorted(self._rulesets)}")
        return rs

    def list(self) -> List[Ruleset]:
        return list(self._rulesets.values())

    @property
    def errors(self) -> Dict[str, str]:
        return dict(self._errors)


_registry: Optional[RulesetRegistry] = None


def registry() -> RulesetRegistry:
    global _registry
    if _registry is None:
        _registry = RulesetRegistry()
    return _registry


def reset_registry() -> None:
    global _registry
    _registry = None


# ------------------------------------------------------------- facts
def _age(dob: Optional[str]) -> Optional[int]:
    d = parse_iso_date(dob)
    if not d:
        return None
    today = date.today()
    return today.year - d.year - ((today.month, today.day) < (d.month, d.day))


def build_facts(ruleset: Ruleset, customer: Dict[str, Any], screening: Dict[str, Any],
                kyc: Optional[Dict[str, Any]] = None, beneficiary: Optional[Dict[str, Any]] = None,
                transfer: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Flatten inputs into the dotted fields the rules reference."""
    kyc = kyc or {}
    beneficiary = beneficiary or {}
    transfer = transfer or {}
    ctype = customer.get("entity_type", "person")
    nat = (customer.get("nationality") or "").upper() or None

    # Identity number checks
    id_type = customer.get("document_type")
    id_check = check_id(id_type, customer.get("document_number", ""), nat) if id_type and customer.get("document_number") else None
    id_birth_ok = id_nat_ok = None
    if id_check and id_check.valid:
        by = id_check.facts.get("birth_year")
        d = parse_iso_date(customer.get("dob"))
        if by and d:
            id_birth_ok = (by == d.year)
        idn = id_check.facts.get("nationality")
        if idn and nat:
            id_nat_ok = (idn == nat)

    required = ruleset.sending.required_fields.get(ctype, [])
    missing = [f for f in required if not customer.get(f)]

    name_info = analyze(customer.get("full_name", ""), nat)

    best = (screening.get("matches") or [None])[0]
    ben_required = ruleset.receiving.required_fields.get("beneficiary", []) if beneficiary else []
    ben_missing = [f for f in ben_required if not beneficiary.get(f)]
    ben_id = None
    if beneficiary.get("id_type") and beneficiary.get("id_number"):
        ben_id = check_id(beneficiary["id_type"], beneficiary["id_number"], beneficiary.get("country"))

    facts = {
        "customer.entity_type": ctype,
        "customer.nationality": nat,
        "customer.residence_country": (customer.get("residence_country") or "").upper() or None,
        "customer.document_type": id_type,
        "customer.age": _age(customer.get("dob")),
        "customer.dob_present": bool(customer.get("dob")),
        "customer.id_valid": id_check.valid if id_check else None,
        "customer.id_birth_year_matches": id_birth_ok,
        "customer.id_nationality_matches": id_nat_ok,
        "customer.missing_fields": missing,
        "customer.name_flags": name_info.flags,
        "screening.match": bool(screening.get("sanctions_match")),
        "screening.match_count": len(screening.get("matches") or []),
        "screening.best_confidence": best.get("confidence") if best else None,
        "screening.best_similarity": best.get("similarity") if best else 0,
        "screening.best_dob_agreement": best.get("dob_agreement") if best else None,
        "screening.best_country_match": best.get("country_match") if best else None,
        "screening.best_match_type": best.get("match_type") if best else None,
        "screening.best_source": best.get("source") if best else None,
        "screening.risk_score": screening.get("risk_score", 0),
        "kyc.document_verified": kyc.get("document_verified"),
        "kyc.face_match": kyc.get("face_match"),
        "kyc.document_expired": kyc.get("document_expired"),
        "kyc.mrz_mismatches": kyc.get("mrz_mismatches"),
        "kyc.liveness": kyc.get("liveness"),
        "beneficiary.present": bool(beneficiary),
        "beneficiary.id_valid": ben_id.valid if ben_id else None,
        "beneficiary.country": (beneficiary.get("country") or "").upper() or None,
        "beneficiary.missing_fields": ben_missing,
        "transfer.amount": transfer.get("amount"),
        "transfer.purpose": transfer.get("purpose"),
        "_id_check": id_check.to_dict() if id_check else None,
        "_beneficiary_id_check": ben_id.to_dict() if ben_id else None,
        "_name_analysis": name_info.to_dict(),
    }
    return facts


# ------------------------------------------------------------- evaluation
def _test(cond: Condition, facts: Dict[str, Any]) -> bool:
    v = facts.get(cond.field)
    op, target = cond.op, cond.value
    if op == "is_true":
        return v is True
    if op == "is_false":
        return v is False
    if op == "is_null":
        return v is None
    if op == "not_null":
        return v is not None
    if op == "eq":
        return v == target
    if op == "ne":
        return v != target
    if op == "in":
        return v in (target or [])
    if op == "not_in":
        return v not in (target or [])
    if op == "contains":
        return isinstance(v, (list, str)) and target in v
    if v is None:
        return False
    try:
        if op == "gte":
            return v >= target
        if op == "lte":
            return v <= target
        if op == "gt":
            return v > target
        if op == "lt":
            return v < target
    except TypeError:
        return False
    return False


def _when(w: When, facts: Dict[str, Any]) -> bool:
    if w.all and not all(_test(c, facts) for c in w.all):
        return False
    if w.any and not any(_test(c, facts) for c in w.any):
        return False
    return True


def decide(ruleset: Ruleset, customer: Dict[str, Any], screening: Dict[str, Any],
           kyc: Optional[Dict[str, Any]] = None, beneficiary: Optional[Dict[str, Any]] = None,
           transfer: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    facts = build_facts(ruleset, customer, screening, kyc, beneficiary, transfer)
    fired: List[Rule] = [r for r in ruleset.rules if _when(r.when, facts)]

    outcome = "approve"
    for r in fired:
        if Severity[r.outcome] > Severity[outcome]:
            outcome = r.outcome
    base = int(screening.get("risk_score", 0) or 0)
    risk = max(0, min(100, base + sum(r.risk_add for r in fired)))
    actions: List[str] = []
    for r in fired:
        for a in r.actions:
            if a not in actions:
                actions.append(a)

    public_facts = {k: v for k, v in facts.items() if not k.startswith("_")}
    return {
        "corridor": ruleset.id,
        "ruleset_version": ruleset.version,
        "ruleset_status": ruleset.status,
        "outcome": outcome,
        "risk_score": risk,
        "reasons": [{"rule": r.id, "title": r.title, "outcome": r.outcome, "reason": r.reason,
                     "risk_add": r.risk_add, "basis": r.basis} for r in fired],
        "actions": actions,
        "facts": public_facts,
        "id_check": facts.get("_id_check"),
        "beneficiary_id_check": facts.get("_beneficiary_id_check"),
        "name_analysis": facts.get("_name_analysis"),
    }
