"""
Backward-compatible shim; canonical module is ``modules.recruitment.bootstrap``.

``runtime/*`` vertical-slice modules are **compatibility shims** only. They re-export
canonical symbols from ``modules/recruitment`` during the modular monolith migration.
Removal is planned after multi-candidate stabilization (Stage B); new code should import
from ``modules.recruitment`` (or ``modules.recruitment.policies`` / ``ingress`` /
``inspection`` as appropriate), not from ``runtime.bootstrap_vertical_slice``.
"""

from modules.recruitment.bootstrap import (
    PRIMARY_VERTICAL_SLICE_EVENT_TYPES,
    VERTICAL_SLICE_DEFAULT_CANDIDATE_ID,
    VERTICAL_SLICE_DEFAULT_STATE_ID,
    VERTICAL_SLICE_INGRESS_EVENT_TYPES,
    VerticalSliceRuntimeBundle,
    drive_vertical_slice_primary_sequence,
    resolve_vertical_slice_inspection_catalog,
    run_vertical_slice_bootstrap,
    vertical_slice_primary_ingress_envelopes,
    vertical_slice_timeline_text,
    wire_vertical_slice_runtime,
)
from modules.recruitment.bootstrap import _skill_registry
from modules.recruitment.ingress import BOOT_NS as _BOOT_NS
from modules.recruitment.ingress import FIXED_CLOCK as _FIXED_CLOCK
from modules.recruitment.ingress import build_ingress_envelope as _envelope

__all__ = (
    "PRIMARY_VERTICAL_SLICE_EVENT_TYPES",
    "VERTICAL_SLICE_DEFAULT_CANDIDATE_ID",
    "VERTICAL_SLICE_DEFAULT_STATE_ID",
    "VERTICAL_SLICE_INGRESS_EVENT_TYPES",
    "VerticalSliceRuntimeBundle",
    "_BOOT_NS",
    "_FIXED_CLOCK",
    "_envelope",
    "_skill_registry",
    "drive_vertical_slice_primary_sequence",
    "resolve_vertical_slice_inspection_catalog",
    "run_vertical_slice_bootstrap",
    "vertical_slice_primary_ingress_envelopes",
    "vertical_slice_timeline_text",
    "wire_vertical_slice_runtime",
)
