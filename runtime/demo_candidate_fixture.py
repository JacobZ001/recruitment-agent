"""
Backward-compatible shim; canonical module is ``modules.recruitment.fixtures``.

Import from ``modules.recruitment.fixtures`` in new code.
"""

from modules.recruitment.fixtures import (
    TESTING_DESKTOP_CANDIDATE_ID,
    merge_demo_profile_into_skill_payload,
)

__all__ = ("TESTING_DESKTOP_CANDIDATE_ID", "merge_demo_profile_into_skill_payload")
