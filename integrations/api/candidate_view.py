"""Backward-compatible shim; canonical implementation is ``modules.recruitment.projection``."""

from modules.recruitment.projection import (
    CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER,
    build_candidate_view,
)

__all__ = ("CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER", "build_candidate_view")
