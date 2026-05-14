"""Inspection timeline determinism and content smoke checks."""

from __future__ import annotations

from orchestrator.vertical_slice_planner import SKILL_LIGHT_SCORING
from runtime.bootstrap_vertical_slice import (
    vertical_slice_primary_ingress_envelopes,
    vertical_slice_timeline_text,
    wire_vertical_slice_runtime,
)
from runtime.bootstrap_vertical_slice import _skill_registry as bootstrap_skill_registry
from runtime.bootstrap_vertical_slice import drive_vertical_slice_primary_sequence

from tests.replay.recording_bus import RecordingInMemoryEventBus
from tests.replay.test_vertical_slice_negative_paths import (
    EVENTS_TO_CV_PARSED,
    InvalidHardFilterPassedPlanner,
    _publish,
    _publish_one_expect_rejected,
)


def test_happy_path_timeline_deterministic_twice_auto_catalog() -> None:
    """Timeline text is stable; primary path shows light scoring then questionnaire (no ranking ingest)."""
    bus_a = RecordingInMemoryEventBus()
    bus_b = RecordingInMemoryEventBus()
    bundle_a = wire_vertical_slice_runtime(bus=bus_a)
    bundle_b = wire_vertical_slice_runtime(bus=bus_b)
    drive_vertical_slice_primary_sequence(bundle_a, verbose=False)
    drive_vertical_slice_primary_sequence(bundle_b, verbose=False)

    text_a = vertical_slice_timeline_text(bundle_a)
    text_b = vertical_slice_timeline_text(bundle_b)
    assert text_a == text_b
    assert "shortlisted" in text_a
    assert "final.pipeline.phase=shortlisted" in text_a
    assert "ingest.event_type=light_scoring_completed" in text_a
    assert "ranking.branch=mid_m" in text_a
    assert "ranking.stage=light" in text_a
    assert "ranking_completed" not in text_a


def test_happy_path_explicit_recorded_stream_matches_auto_catalog() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle, verbose=False)
    auto = vertical_slice_timeline_text(bundle)
    explicit = vertical_slice_timeline_text(bundle, bus.recorded_envelopes)
    assert auto == explicit


def test_negative_path_timeline_includes_transition_failure_code() -> None:
    bundle = wire_vertical_slice_runtime(planner=InvalidHardFilterPassedPlanner())
    _publish(bundle, EVENTS_TO_CV_PARSED)
    _publish_one_expect_rejected(bundle, "hard_filter_passed", seq=4)

    text = vertical_slice_timeline_text(bundle, vertical_slice_primary_ingress_envelopes(bundle))
    assert "failure.code=transition_rejected" in text


def test_skill_not_registered_timeline_includes_failure_code() -> None:
    reg = dict(bootstrap_skill_registry())
    del reg[SKILL_LIGHT_SCORING]
    bundle = wire_vertical_slice_runtime(skills=reg)
    _publish(
        bundle,
        (
            "candidate_created",
            "cv_uploaded",
            "cv_parsed",
            "hard_filter_passed",
        ),
    )
    _publish_one_expect_rejected(bundle, "light_scoring_completed", seq=5)

    text = vertical_slice_timeline_text(bundle, vertical_slice_primary_ingress_envelopes(bundle))
    assert "failure.code=skill_not_registered" in text
