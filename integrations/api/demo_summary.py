"""Read-only demo projections from the wired vertical-slice bundle (no policy)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from orchestrator.vertical_slice_planner import (
    SKILL_DEEP_SCORING,
    SKILL_HARD_FILTER,
    SKILL_LIGHT_SCORING,
)
from runtime.bootstrap_vertical_slice import VerticalSliceRuntimeBundle
from runtime.inspection import skill_decision_summary_parts


def vertical_slice_demo_skill_summaries(bundle: VerticalSliceRuntimeBundle) -> Dict[str, Any]:
    """Last successful summaries for hard filter / light / deep scoring from run history."""
    hard: Optional[Dict[str, Any]] = None
    light: Optional[Dict[str, Any]] = None
    deep: Optional[Dict[str, Any]] = None
    for run in bundle.subscriber.run_history:
        if not run.ok:
            continue
        for sr in run.skill_results:
            name = sr.metadata.skill_name
            parts = skill_decision_summary_parts(sr)
            if name == SKILL_HARD_FILTER:
                hard = parts
            elif name == SKILL_LIGHT_SCORING:
                light = parts
            elif name == SKILL_DEEP_SCORING:
                deep = parts
    return {
        "hard_filter": hard,
        "light_scoring": light,
        "deep_scoring": deep,
    }
