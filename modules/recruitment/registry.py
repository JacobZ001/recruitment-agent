"""
Stateless candidate → orchestration state id mapping (application layer only).

Deterministic: ``uuid5(BOOT_NS, f"candidate:{candidate_id}")``. No in-memory registry.
"""

from __future__ import annotations

from uuid import UUID, uuid5

from .ingress import BOOT_NS


def get_state_id(candidate_id: UUID) -> UUID:
    """Return the deterministic orchestration state id for ``candidate_id``."""
    return uuid5(BOOT_NS, f"candidate:{candidate_id}")
