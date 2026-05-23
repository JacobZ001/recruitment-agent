"""
Backward-compatible shim; canonical module is ``modules.recruitment.fixtures``.

Compatibility shim — removal planned after multi-candidate stabilization. Import from
``modules.recruitment.fixtures`` in new code.
"""

from modules.recruitment.fixtures import (
    DEMO_CANDIDATE_DISPLAY,
    merge_demo_profile_into_skill_payload,
)

__all__ = ("DEMO_CANDIDATE_DISPLAY", "merge_demo_profile_into_skill_payload")
