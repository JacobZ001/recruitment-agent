"""Backward-compatible shim; canonical implementation is ``modules.recruitment.projection``."""

from __future__ import annotations

from typing import Any, Dict

from runtime.bootstrap_vertical_slice import VerticalSliceRuntimeBundle

from modules.recruitment.projection import demo_skill_summaries


def vertical_slice_demo_skill_summaries(bundle: VerticalSliceRuntimeBundle) -> Dict[str, Any]:
    return demo_skill_summaries(bundle)
