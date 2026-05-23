"""
Merge envelope streams for vertical-slice inspection (read-only assembly).

Does not define workflow rules, ranking, ingress policy, or envelope construction —
those live in ``policies``, ``ranking``, and ``ingress`` respectively.
"""

from __future__ import annotations

from typing import Any, List, Protocol

from interfaces.event_bus_interface import EventEnvelope

from ..ingress import vertical_slice_primary_ingress_envelopes


class _InspectionBundle(Protocol):
    """Minimal bundle surface for catalog merge."""

    bus: Any


def resolve_vertical_slice_inspection_catalog(bundle: _InspectionBundle) -> List[EventEnvelope]:
    """
    Unified envelope catalog: scripted primary ingress merged with any envelopes on
    ``bundle.bus`` (e.g. ``recorded_envelopes`` on a recording bus).
    """
    from runtime.inspection import merge_catalog_streams

    primary = vertical_slice_primary_ingress_envelopes(bundle)
    recorded = getattr(bundle.bus, "recorded_envelopes", None)
    if recorded:
        return merge_catalog_streams(primary, recorded)
    return list(primary)
