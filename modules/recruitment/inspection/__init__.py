"""Recruitment vertical-slice inspection projections (read-only; no wiring)."""

from ..ingress import vertical_slice_primary_ingress_envelopes
from .catalog import resolve_vertical_slice_inspection_catalog
from .timeline import vertical_slice_timeline_text

__all__ = (
    "resolve_vertical_slice_inspection_catalog",
    "vertical_slice_primary_ingress_envelopes",
    "vertical_slice_timeline_text",
)
