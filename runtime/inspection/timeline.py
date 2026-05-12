"""
Human-readable workflow timeline formatting from orchestration artifacts.

Inspects recorded facts only (runs, envelopes, decisions); does not plan or validate.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from interfaces.event_bus_interface import EventEnvelope
from interfaces.skill_interface import SkillExecutionResult
from orchestrator.orchestrator import (
    OrchestrationDecisionKind,
    OrchestrationExecutionResult,
)
from schemas.state_schema import OrchestrationState


def envelope_lookup(envelopes: Sequence[EventEnvelope]) -> Dict[str, EventEnvelope]:
    """Map ``event_id`` hex string → envelope (last wins if duplicates)."""
    out: Dict[str, EventEnvelope] = {}
    for env in envelopes:
        out[str(env.event_id)] = env
    return out


def render_vertical_slice_timeline_text(
    *,
    run_history: Sequence[OrchestrationExecutionResult],
    envelope_catalog: Sequence[EventEnvelope],
    final_state: Optional[OrchestrationState] = None,
) -> str:
    """
    Render a deterministic, multi-line timeline for developer/operator inspection.

    ``envelope_catalog`` should include every ``EventEnvelope`` whose ``event_id``
    appears as ``trace.ingested_event_id`` in ``run_history`` (typically all envelopes
    passed to ``InMemoryEventBus.publish``, e.g. from :class:`~tests.replay.recording_bus.RecordingInMemoryEventBus`).
    Missing ids still render with ``event_type`` omitted.
    """
    lines: List[str] = []
    by_id = envelope_lookup(envelope_catalog)

    lines.append("=== workflow timeline (inspection; deterministic order) ===")
    if final_state is not None:
        lines.append(
            f"final.pipeline.phase={final_state.pipeline.phase.value} "
            f"transitions={len(final_state.transitions)} state_id={final_state.id}"
        )

    for run_idx, run in enumerate(run_history, start=1):
        ingest_id = str(run.trace.ingested_event_id)
        ingest_env = by_id.get(ingest_id)
        etype = ingest_env.event_type if ingest_env else "<unknown_ingress_type>"
        lines.append("")
        lines.append(
            f"--- run {run_idx} | ingest.event_type={etype} | ingest.event_id={ingest_id} | ok={run.ok}"
        )
        lines.append(f"    orchestration_execution_id={run.trace.orchestration_execution_id}")

        if not run.ok:
            assert run.failure is not None
            fc = run.failure.code.value
            lines.append(f"    failure.code={fc}")
            lines.append(f"    failure.message={run.failure.message}")
            det = run.failure.details or {}
            if det:
                lines.append(f"    failure.details={det}")
        else:
            assert run.new_state is not None
            ns = run.new_state
            lines.append(
                f"    pipeline.phase.after={ns.pipeline.phase.value} "
                f"transitions.total={len(ns.transitions)}"
            )
            if ns.transitions:
                tr = ns.transitions[-1]
                lines.append(
                    f"    last_transition: domain={tr.state_domain.value} "
                    f"{tr.from_state!r} -> {tr.to_state!r} trigger={tr.trigger!r}"
                )

        tv = run.transition_result
        if tv is not None:
            lines.append(f"    transition_engine.ok={tv.ok}")
            if tv.ok and tv.matched_rule_id:
                lines.append(f"    transition_engine.matched_rule_id={tv.matched_rule_id}")
            if not tv.ok:
                for rj in tv.rejections:
                    rc = rj.code.value if hasattr(rj.code, "value") else str(rj.code)
                    rid = rj.rule_id or ""
                    lines.append(f"    transition_engine.rejection: code={rc} rule_id={rid} msg={rj.message}")

        for d in run.decisions:
            lines.append(
                f"    decision | {d.kind.value} | code={d.code!s} | {d.message}"
            )

        for sr in run.skill_results:
            lines.extend(_format_skill_block(sr))

        if run.produced_event_ids:
            emit_labels = _emission_types_from_decisions(run)
            for i, eid in enumerate(run.produced_event_ids):
                label = emit_labels[i] if i < len(emit_labels) else "?"
                lines.append(f"    emitted | event_type={label} | event_id={eid}")

    lines.append("")
    lines.append("=== end timeline ===")
    return "\n".join(lines)


def _emission_types_from_decisions(run: OrchestrationExecutionResult) -> List[str]:
    out: List[str] = []
    for d in run.decisions:
        if d.kind == OrchestrationDecisionKind.EMISSION_SCHEDULED and d.code:
            out.append(str(d.code))
    return out


def _format_skill_block(sr: SkillExecutionResult) -> List[str]:
    meta = sr.metadata
    lines = [f"    skill | {meta.skill_name} | status={sr.status.value}"]
    pl = sr.output.payload if sr.output else None
    if not pl:
        return lines
    if "filter.decision" in pl:
        lines.append(f"           filter.decision={pl.get('filter.decision')!r}")
    if "scoring.normalized_score" in pl:
        lines.append(f"           scoring.normalized_score={pl.get('scoring.normalized_score')!r}")
    if "scoring.deep.normalized_score" in pl:
        lines.append(f"           scoring.deep.normalized_score={pl.get('scoring.deep.normalized_score')!r}")
    if pl.get("stub") and pl.get("planner_path"):
        lines.append(f"           stub.planner_path={pl.get('planner_path')!r}")
    return lines
