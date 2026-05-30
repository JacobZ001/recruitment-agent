"""
Ingress idempotency governance flags (R-013.1).

Separates fresh in-progress ingress from stale abandoned records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import UUID

from .idempotency_store import IdempotencyRecord, IdempotencyRecordStatus

ORPHAN_INGRESS_STALE_SECONDS = 86400


@dataclass(frozen=True)
class IngressGovernanceFlags:
    ingress_in_progress: bool = False
    orphan_ingress: bool = False


def ingress_governance_by_candidate_id(
    in_progress_records: list[IdempotencyRecord],
    *,
    now: Optional[datetime] = None,
    stale_seconds: int = ORPHAN_INGRESS_STALE_SECONDS,
) -> Dict[UUID, IngressGovernanceFlags]:
    """
    Map candidate_id -> governance flags for IN_PROGRESS idempotency rows.

    Fresh (within threshold): ingress_in_progress only.
    Stale (beyond threshold): orphan_ingress only (mutually exclusive per record).
    """
    ts = now or datetime.now(timezone.utc)
    threshold = timedelta(seconds=stale_seconds)
    out: Dict[UUID, IngressGovernanceFlags] = {}
    for rec in in_progress_records:
        if rec.status != IdempotencyRecordStatus.IN_PROGRESS or not rec.candidate_id:
            continue
        cid = UUID(rec.candidate_id)
        created = rec.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = ts - created
        if age > threshold:
            out[cid] = IngressGovernanceFlags(
                ingress_in_progress=False,
                orphan_ingress=True,
            )
        else:
            out[cid] = IngressGovernanceFlags(
                ingress_in_progress=True,
                orphan_ingress=False,
            )
    return out
