"""
Deterministic demo skill-context defaults for vertical-slice demos (no parsing, no LLM).

Merged into planner-built skill inputs when ``VerticalSlicePlanner`` is wired with
``demo_skill_context=True`` (e.g. API runtime). Bootstrap/replay defaults omit this merge.
"""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID, uuid5

from modules.recruitment.ingress import BOOT_NS

# Stable id for PDF-seeded testing candidate (see scripts/seed_testing_candidate_from_pdf.py).
TESTING_DESKTOP_CANDIDATE_ID: UUID = uuid5(BOOT_NS, "vertical_slice.testing_candidate_desktop_cv")


def _skill_payload_defaults() -> Dict[str, Any]:
    """Keys understood by ``fake_*`` vertical-slice skills (setdefault merge)."""
    skills_kw = "python django postgresql rest api design testing"
    present: List[str] = [
        "email",
        "full_name",
        "work_auth",
        "skills",
        "summary",
        "education",
        "location",
    ]
    return {
        "declared.years_experience": 9,
        "declared.work_authorization": "authorized",
        "declared.skill_keywords": skills_kw,
        "declared.present_fields": present,
        "declared.profile_completeness_ratio": 0.88,
        "declared.profile_field_slots": 8,
        "declared.questionnaire_available": True,
        "declared.questionnaire_readiness": 0.92,
        "declared.questionnaire_completed": True,
        "declared.evidence_item_count": 6,
        "declared.evidence_max_slots": 12,
        "declared.communication_quality": 0.82,
        "declared.project_depth_score": 0.79,
        "filter.min_years_experience": 3,
        "filter.required_keywords": ["python", "api"],
        "filter.mandatory_fields": ["email", "full_name", "work_auth"],
        "scoring.required_keywords": ["python", "django"],
    }


def merge_demo_profile_into_skill_payload(payload: Dict[str, Any]) -> None:
    """Mutates ``payload`` in place: demo keys only fill gaps (planner ``extras`` win)."""
    for k, v in _skill_payload_defaults().items():
        payload.setdefault(k, v)
