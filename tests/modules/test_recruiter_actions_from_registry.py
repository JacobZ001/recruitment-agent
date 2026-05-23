"""Recruiter actions derived only from transition_engine registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from schemas.state_schema import PipelinePhase
from state_machine.transition_engine import TransitionRegistry, default_pipeline_registry

from modules.recruitment.policies import (
    ACTION_DESCRIPTORS,
    event_type_from_manual_trigger,
    get_allowed_transitions_for_phase,
    get_available_actions_for_phase,
    label_for_recruiter_action,
    label_from_event_type,
    validate_recruiter_event_for_phase,
)
from modules.recruitment.exceptions import InvalidCandidateActionError


def test_policies_has_no_legacy_mapping_tables() -> None:
    text = Path(__file__).resolve().parents[2] / "modules" / "recruitment" / "policies.py"
    body = text.read_text(encoding="utf-8")
    assert "_MANUAL_TRIGGER_TO_EVENT_TYPE" not in body
    assert "EVENT_TYPE_TO_ACTION_KEY" not in body
    assert "_ACTION_LABELS" not in body
    assert "RECRUITER_ACTION_KEYS" not in body
    assert "_REJECT_WILDCARD_PHASES" not in body


def test_label_from_event_type() -> None:
    assert label_from_event_type("recruiter_schedule_interview") == "Schedule Interview"
    assert label_from_event_type("recruiter_send_offer") == "Send Offer"
    assert label_from_event_type("recruiter_reject_candidate") == "Reject Candidate"


def test_action_descriptor_label_override() -> None:
    assert label_for_recruiter_action("recruiter_schedule_interview") == (
        ACTION_DESCRIPTORS["recruiter_schedule_interview"]["label"]
    )
    actions = get_available_actions_for_phase(PipelinePhase.SHORTLISTED.value)
    schedule = next(a for a in actions if a["event_type"] == "recruiter_schedule_interview")
    assert schedule["label"] == "Schedule Interview"
    assert schedule["label"] == ACTION_DESCRIPTORS["recruiter_schedule_interview"]["label"]


def test_action_descriptor_fallback() -> None:
    assert "recruiter_shortlist_candidate" not in ACTION_DESCRIPTORS
    assert label_for_recruiter_action("recruiter_shortlist_candidate") == "Shortlist Candidate"
    actions = get_available_actions_for_phase(PipelinePhase.DEEP_SCORED.value)
    shortlist = next(a for a in actions if a["event_type"] == "recruiter_shortlist_candidate")
    assert shortlist["label"] == label_from_event_type("recruiter_shortlist_candidate")


def test_event_type_from_manual_trigger_uses_governance_vocabulary() -> None:
    assert event_type_from_manual_trigger("manual_recruiter_schedule_interview") == (
        "recruiter_schedule_interview"
    )
    assert event_type_from_manual_trigger("manual_recruiter_reject") == "recruiter_reject_candidate"
    assert event_type_from_manual_trigger("manual_recruiter_approve") == "recruiter_approve_candidate"


def _registry_without_rule(rule_id: str) -> TransitionRegistry:
    reg = default_pipeline_registry()
    rules = tuple(r for r in reg.rules if r.rule_id != rule_id)
    return TransitionRegistry(rules=rules, terminal_states=reg.terminal_states)


def test_shortlisted_actions_from_transition_rules() -> None:
    rules = get_allowed_transitions_for_phase(PipelinePhase.SHORTLISTED.value)
    assert any(r.rule_id == "pipeline.shortlisted_to_interview_pending" for r in rules)
    actions = get_available_actions_for_phase(PipelinePhase.SHORTLISTED.value)
    event_types = {a["event_type"] for a in actions}
    assert all(a["key"] == a["event_type"] for a in actions)
    assert "recruiter_schedule_interview" in event_types
    assert "recruiter_reject_candidate" in event_types
    assert actions[0]["label"] == label_for_recruiter_action(actions[0]["event_type"])


def test_removing_transition_rule_removes_action() -> None:
    full = {a["event_type"] for a in get_available_actions_for_phase(PipelinePhase.SHORTLISTED.value)}
    assert "recruiter_schedule_interview" in full

    subset = _registry_without_rule("pipeline.shortlisted_to_interview_pending")
    reduced = {a["event_type"] for a in get_available_actions_for_phase(PipelinePhase.SHORTLISTED.value, registry=subset)}
    assert "recruiter_schedule_interview" not in reduced
    assert "recruiter_reject_candidate" in reduced


def test_adding_manual_edge_introduces_action() -> None:
    actions = get_available_actions_for_phase(PipelinePhase.DEEP_SCORED.value)
    assert "recruiter_shortlist_candidate" in {a["event_type"] for a in actions}


def test_reject_only_when_registry_edge_to_inactive() -> None:
    """Reject appears when a rule has ``to_state=inactive`` and ``manual_recruiter_reject``."""
    actions = get_available_actions_for_phase(PipelinePhase.NEW.value)
    assert "recruiter_reject_candidate" in {a["event_type"] for a in actions}
    hired_actions = get_available_actions_for_phase(PipelinePhase.HIRED.value)
    assert "recruiter_reject_candidate" not in {a["event_type"] for a in hired_actions}


def test_inactive_includes_reconsider_and_wildcard_reject() -> None:
    actions = get_available_actions_for_phase(PipelinePhase.INACTIVE.value)
    event_types = [a["event_type"] for a in actions]
    assert event_types == [
        "recruiter_reconsider_candidate",
        "recruiter_reject_candidate",
    ]


def test_hired_terminal_has_no_actions() -> None:
    assert get_available_actions_for_phase(PipelinePhase.HIRED.value) == []


def test_validate_recruiter_event_for_phase() -> None:
    validate_recruiter_event_for_phase(
        "recruiter_schedule_interview",
        PipelinePhase.SHORTLISTED.value,
    )


def test_invalid_event_type_for_phase_raises() -> None:
    with pytest.raises(InvalidCandidateActionError):
        validate_recruiter_event_for_phase(
            "recruiter_schedule_interview",
            PipelinePhase.NEW.value,
        )
