"""
Deterministic candidate deduplication evaluation (R-013).

Programs own match rules; recruiters own link/keep-separate decisions.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set
from uuid import UUID

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")


class DedupOutcome(str, Enum):
    NONE = "none"
    HIGH_CONFIDENCE_DUPLICATE = "high_confidence_duplicate"
    SUSPECTED_FINGERPRINT = "suspected_fingerprint"


@dataclass(frozen=True)
class DedupIngressSignals:
    normalized_email: Optional[str]
    normalized_phone: Optional[str]
    cv_content_fingerprint: Optional[str]


@dataclass(frozen=True)
class DedupMatch:
    candidate_id: UUID
    match_kinds: List[str]
    full_name: Optional[str] = None


@dataclass(frozen=True)
class DedupEvaluation:
    outcome: DedupOutcome
    matches: List[DedupMatch] = field(default_factory=list)
    signals: Optional[DedupIngressSignals] = None


def normalize_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    s = value.strip().lower()
    return s or None


def normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def cv_content_fingerprint(cv_text: str) -> str:
    normalized = " ".join(line.strip().lower() for line in cv_text.splitlines() if line.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_ingress_signals_from_cv_text(cv_text: str) -> DedupIngressSignals:
    """Best-effort deterministic extraction before canonical Candidate exists."""
    text = cv_text.strip()
    email = None
    phone = None
    for match in _EMAIL_RE.finditer(text):
        email = normalize_email(match.group(0))
        if email:
            break
    for match in _PHONE_RE.finditer(text):
        phone = normalize_phone(match.group(0))
        if phone and len(phone) >= 8:
            break
    fingerprint = cv_content_fingerprint(text) if text else None
    return DedupIngressSignals(
        normalized_email=email,
        normalized_phone=phone,
        cv_content_fingerprint=fingerprint,
    )


def _match_row(
    candidate_id: UUID,
    *,
    full_name: Optional[str],
    kind: str,
    by_id: Dict[UUID, DedupMatch],
) -> None:
    if candidate_id in by_id:
        existing = by_id[candidate_id]
        kinds = list(existing.match_kinds)
        if kind not in kinds:
            kinds.append(kind)
        by_id[candidate_id] = DedupMatch(
            candidate_id=candidate_id,
            match_kinds=kinds,
            full_name=existing.full_name or full_name,
        )
    else:
        by_id[candidate_id] = DedupMatch(
            candidate_id=candidate_id,
            match_kinds=[kind],
            full_name=full_name,
        )


def evaluate_dedup(
    candidate_store: Any,
    signals: DedupIngressSignals,
    *,
    exclude_candidate_ids: Optional[Sequence[UUID]] = None,
) -> DedupEvaluation:
    """
    Balanced/hybrid matrix (R-013 default):
    - email or phone hit => high-confidence duplicate (block create)
    - fingerprint-only hit => suspected duplicate (allow create, flag)
    """
    excluded: Set[UUID] = set(exclude_candidate_ids or ())
    high: Dict[UUID, DedupMatch] = {}
    fingerprint_only: Dict[UUID, DedupMatch] = {}

    for cid in candidate_store.list_candidate_ids():
        uid = UUID(str(cid)) if not isinstance(cid, UUID) else cid
        if uid in excluded:
            continue
        got = candidate_store.get(uid)
        if not got.ok or got.candidate is None:
            continue
        cand = got.candidate
        sig = cand.dedup_signals
        name = cand.identity.full_name
        email_hit = (
            signals.normalized_email is not None
            and sig.normalized_email is not None
            and sig.normalized_email == signals.normalized_email
        )
        phone_hit = (
            signals.normalized_phone is not None
            and sig.normalized_phone is not None
            and sig.normalized_phone == signals.normalized_phone
        )
        fp_hit = (
            signals.cv_content_fingerprint is not None
            and sig.cv_content_fingerprint is not None
            and sig.cv_content_fingerprint == signals.cv_content_fingerprint
        )
        if email_hit:
            _match_row(uid, full_name=name, kind="normalized_email", by_id=high)
        if phone_hit:
            _match_row(uid, full_name=name, kind="normalized_phone", by_id=high)
        if fp_hit and uid not in high:
            _match_row(uid, full_name=name, kind="cv_content_fingerprint", by_id=fingerprint_only)

    if high:
        return DedupEvaluation(
            outcome=DedupOutcome.HIGH_CONFIDENCE_DUPLICATE,
            matches=sorted(high.values(), key=lambda m: str(m.candidate_id)),
            signals=signals,
        )
    if fingerprint_only:
        return DedupEvaluation(
            outcome=DedupOutcome.SUSPECTED_FINGERPRINT,
            matches=sorted(fingerprint_only.values(), key=lambda m: str(m.candidate_id)),
            signals=signals,
        )
    return DedupEvaluation(outcome=DedupOutcome.NONE, matches=[], signals=signals)


def dedup_matches_to_json(matches: Sequence[DedupMatch]) -> List[Dict[str, Any]]:
    return [
        {
            "candidate_id": str(m.candidate_id),
            "match_kinds": list(m.match_kinds),
            "full_name": m.full_name,
        }
        for m in matches
    ]


def governance_flags_from_candidate(
    candidate: Any,
    *,
    orphan_ingress: bool = False,
) -> Dict[str, Any]:
    dedup = dict((candidate.extensions or {}).get("dedup") or {})
    flags: Dict[str, Any] = {
        "orphan_ingress": bool(orphan_ingress),
        "dedup_status": dedup.get("status"),
        "dedup_pending_resolution": bool(dedup.get("pending_resolution")),
        "dedup_linked_to_candidate_id": dedup.get("linked_to_candidate_id"),
    }
    matches = dedup.get("matches")
    if isinstance(matches, list) and matches:
        flags["dedup_match_count"] = len(matches)
    return flags
