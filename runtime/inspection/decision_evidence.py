"""
Deterministic decision and evidence summaries for operator inspection.

Read-only projections from orchestration artifacts—no orchestration policy,
no LLM, no mutation of runtime state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from interfaces.event_bus_interface import EventEnvelope
from interfaces.skill_interface import EvidenceRef, SkillExecutionResult
from orchestrator.orchestrator import OrchestrationExecutionResult
from orchestrator.vertical_slice_planner import (
    SKILL_DEEP_SCORING,
    SKILL_HARD_FILTER,
    SKILL_LIGHT_SCORING,
)
from schemas.state_schema import OrchestrationState, StateTransitionRecord

from runtime.inspection.decision_explainer import (
    evidence_refs_from_snapshot,
    format_deep_scoring_from_snapshot,
    format_hard_filter_from_snapshot,
    format_light_scoring_from_snapshot,
)


_MAX_RATIONALE_CHARS = 200
_MAX_REASON_CODES = 6
_MAX_EVIDENCE_REFS = 6
_MAX_SIGNAL_CODES = 8


def truncate_for_inspection(value: Optional[str], *, max_chars: int = _MAX_RATIONALE_CHARS) -> str:
    """Deterministic single-line truncation for timeline/navigation (no ellipsis logic drift)."""
    if value is None:
        return ""
    s = str(value).replace("\n", " ").replace("\r", " ").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 3] + "..."


def _evidence_ref_strings(refs: Optional[Sequence[EvidenceRef]], *, limit: int) -> List[str]:
    out: List[str] = []
    if not refs:
        return out
    for r in refs[:limit]:
        out.append(str(r.ref))
    return out


def _decision_summary_from_snapshot(
    sr: SkillExecutionResult, state_snapshot: OrchestrationState
) -> Optional[Dict[str, Any]]:
    """If the snapshot holds persisted evaluation data for this skill, build summary."""
    name = sr.metadata.skill_name
    parts: Dict[str, Any] = {
        "skill_name": name,
        "status": sr.status.value,
    }
    if name == SKILL_HARD_FILTER:
        summary = format_hard_filter_from_snapshot(state_snapshot)
        if summary is None:
            return None
        parts["decision.summary"] = summary
        refs = evidence_refs_from_snapshot(state_snapshot)
        if refs is not None:
            parts["evidence.refs"] = refs
        return parts

    if name == SKILL_LIGHT_SCORING:
        summary = format_light_scoring_from_snapshot(state_snapshot)
        if summary is None:
            return None
        parts["score.summary"] = summary
        refs = evidence_refs_from_snapshot(state_snapshot)
        if refs is not None:
            parts["evidence.refs"] = refs
        return parts

    if name in (SKILL_DEEP_SCORING, "recruitment.vertical_slice.cv_parse_and_score"):
        summary = (
            format_light_scoring_from_snapshot(state_snapshot)
            if name == "recruitment.vertical_slice.cv_parse_and_score"
            else format_deep_scoring_from_snapshot(state_snapshot)
        )
        if summary is None:
            return None
        parts["score.summary"] = summary
        refs = evidence_refs_from_snapshot(state_snapshot)
        if refs is not None:
            parts["evidence.refs"] = refs
        return parts

    return None


def skill_decision_summary_parts(
    sr: SkillExecutionResult,
    *,
    state_snapshot: Optional[OrchestrationState] = None,
) -> Dict[str, Any]:
    """
    Compact, stable key/value summary for one skill execution (for navigation APIs).

    Keys are inspection-oriented strings; values are JSON-serializable where possible.
    When ``state_snapshot`` is set, reads persisted typed evaluation data first,
    then falls back to skill output shape.
    """
    if state_snapshot is not None:
        from_snap = _decision_summary_from_snapshot(sr, state_snapshot)
        if from_snap is not None:
            return from_snap

    name = sr.metadata.skill_name
    parts: Dict[str, Any] = {
        "skill_name": name,
        "status": sr.status.value,
    }
    out = sr.output
    if out is None:
        return parts
    pl = out.payload or {}
    refs = _evidence_ref_strings(out.evidence_refs, limit=_MAX_EVIDENCE_REFS)
    if refs:
        parts["evidence.refs"] = refs

    if "filter.decision" in pl:
        parts["decision.summary"] = (
            f"filter decision={pl.get('filter.decision')!r} "
            f"computed_pass={pl.get('filter.computed_pass')!r}"
        )
        rc = pl.get("filter.rejection.reason_codes")
        if isinstance(rc, list) and rc:
            preview = ",".join(str(x) for x in rc[:_MAX_REASON_CODES])
            if len(rc) > _MAX_REASON_CODES:
                preview += ",..."
            parts["filter.reason_codes"] = preview
        return parts

    if pl.get("scoring.kind") == "light" or "scoring.normalized_score" in pl:
        score = pl.get("scoring.normalized_score")
        kind = pl.get("scoring.kind", "light")
        sig = pl.get("scoring.signal_codes")
        sig_preview = ""
        if isinstance(sig, list) and sig:
            sig_preview = ",".join(str(x) for x in sig[:_MAX_SIGNAL_CODES])
        conf_lvl = None
        if out.confidence is not None and out.confidence.level is not None:
            lv = out.confidence.level
            conf_lvl = lv.value if hasattr(lv, "value") else str(lv)
        parts["score.summary"] = f"kind={kind} normalized={score!r} confidence_level={conf_lvl!r}"
        if sig_preview:
            parts["score.signal_codes"] = sig_preview
        return parts

    if pl.get("scoring.kind") == "deep" or "scoring.deep.normalized_score" in pl:
        score = pl.get("scoring.deep.normalized_score")
        kind = pl.get("scoring.kind", "deep")
        conf_lvl = None
        if out.confidence is not None and out.confidence.level is not None:
            lv = out.confidence.level
            conf_lvl = lv.value if hasattr(lv, "value") else str(lv)
        parts["score.summary"] = f"kind={kind} normalized={score!r} confidence_level={conf_lvl!r}"
        priors = pl.get("scoring.deep.used_questionnaire_stage_prior")
        if priors is not None:
            parts["score.priors"] = bool(priors)
        return parts

    if pl.get("stub"):
        parts["decision.summary"] = f"stub planner_path={pl.get('planner_path')!r}"
    return parts


def skill_decision_timeline_lines(
    sr: SkillExecutionResult,
    *,
    state_snapshot: Optional[OrchestrationState] = None,
) -> List[str]:
    """Human-readable indented lines (deterministic order) for embedding in timelines."""
    parts = skill_decision_summary_parts(sr, state_snapshot=state_snapshot)
    lines: List[str] = []
    if "decision.summary" in parts:
        lines.append(f"           decision.summary={parts['decision.summary']}")
    if "filter.reason_codes" in parts:
        lines.append(f"           filter.reason_codes={parts['filter.reason_codes']}")
    if "score.summary" in parts:
        lines.append(f"           score.summary={parts['score.summary']}")
    if "score.signal_codes" in parts:
        lines.append(f"           score.signal_codes={parts['score.signal_codes']}")
    if "score.priors" in parts:
        lines.append(f"           score.priors.used_questionnaire_stage_prior={parts['score.priors']}")
    if "evidence.refs" in parts:
        joined = ",".join(parts["evidence.refs"])
        lines.append(f"           evidence.refs=[{joined}]")
    return lines


def governance_envelope_summary_lines(envelope: Optional[EventEnvelope]) -> List[str]:
    """Lines derived from immutable governance ingress payload (recruiter_* only)."""
    if envelope is None:
        return []
    et = envelope.event_type
    if not str(et).startswith("recruiter_"):
        return []
    pl = dict(envelope.payload or {})
    lines: List[str] = []
    reason = pl.get("reason")
    if reason is not None:
        lines.append(f"    governance.reason={truncate_for_inspection(str(reason))!r}")
    refs = pl.get("evidence_refs")
    if isinstance(refs, (list, tuple)) and refs:
        rstr = ",".join(str(x) for x in list(refs)[:_MAX_EVIDENCE_REFS])
        lines.append(f"    governance.evidence.refs=[{rstr}]")
    ora = pl.get("override_rationale")
    if ora:
        lines.append(f"    governance.override_rationale={truncate_for_inspection(str(ora))!r}")
    return lines


def governance_transition_detail_lines(tr: StateTransitionRecord) -> List[str]:
    """Extra lines from ``StateTransitionRecord.extensions`` governance keys (post-commit facts)."""
    ex = tr.extensions or {}
    if not ex.get("governance.decision_code"):
        return []
    lines: List[str] = []
    code = ex.get("governance.decision_code")
    lines.append(f"    governance.decision_code={code!r}")
    gr = ex.get("governance.reason")
    if gr:
        lines.append(f"    governance.transition_reason={truncate_for_inspection(str(gr))!r}")
    grefs = ex.get("governance.evidence_refs")
    if isinstance(grefs, list) and grefs:
        rstr = ",".join(str(x) for x in grefs[:_MAX_EVIDENCE_REFS])
        lines.append(f"    governance.recorded_evidence.refs=[{rstr}]")
    gor = ex.get("governance.override_rationale")
    if gor:
        lines.append(f"    governance.recorded_override_rationale={truncate_for_inspection(str(gor))!r}")
    return lines


def transition_trail_rows(state: OrchestrationState) -> List[Dict[str, Any]]:
    """
    Ordered transition facts for navigation (one row per committed transition on state).

    Deterministic: same state snapshot → same rows.
    """
    rows: List[Dict[str, Any]] = []
    for tr in state.transitions:
        ex = tr.extensions or {}
        row: Dict[str, Any] = {
            "from_state": tr.from_state,
            "to_state": tr.to_state,
            "trigger": tr.trigger,
            "domain": tr.state_domain.value,
            "matched_rule_id": ex.get("matched_rule_id"),
            "event_id": str(tr.event_id) if tr.event_id else None,
            "actor_type": tr.actor.actor_type.value if tr.actor else None,
            "actor_id": tr.actor.actor_id if tr.actor else None,
        }
        if ex.get("governance.decision_code"):
            row["governance.decision_code"] = ex.get("governance.decision_code")
            row["governance.reason"] = ex.get("governance.reason")
            refs = ex.get("governance.evidence_refs")
            if isinstance(refs, list):
                row["governance.evidence_refs"] = list(refs)[:_MAX_EVIDENCE_REFS]
        rows.append(row)
    return rows


def governance_ingress_index(
    *,
    run_history: Sequence[OrchestrationExecutionResult],
    envelope_by_id: Mapping[str, EventEnvelope],
) -> List[Dict[str, Any]]:
    """
    One entry per orchestration run whose ingested envelope is a recruiter_* governance event.
    """
    out: List[Dict[str, Any]] = []
    for idx, run in enumerate(run_history, start=1):
        eid = str(run.trace.ingested_event_id)
        env = envelope_by_id.get(eid)
        if env is None or not str(env.event_type).startswith("recruiter_"):
            continue
        pl = dict(env.payload or {})
        entry: Dict[str, Any] = {
            "run_index": idx,
            "ingest_event_id": eid,
            "event_type": env.event_type,
            "ok": run.ok,
            "actor_id": pl.get("actor_id"),
            "reason_preview": truncate_for_inspection(pl.get("reason")),
        }
        refs = pl.get("evidence_refs")
        if isinstance(refs, (list, tuple)):
            entry["evidence_refs"] = [str(x) for x in refs[:_MAX_EVIDENCE_REFS]]
        out.append(entry)
    return out


def skills_contributing_by_run(
    run: OrchestrationExecutionResult,
    *,
    persisted_snapshot: Optional[OrchestrationState] = None,
) -> List[Dict[str, Any]]:
    return [
        skill_decision_summary_parts(sr, state_snapshot=persisted_snapshot)
        for sr in run.skill_results
    ]


def build_vertical_slice_operator_navigation(
    *,
    final_state: OrchestrationState,
    run_history: Sequence[OrchestrationExecutionResult],
    envelope_catalog: Sequence[EventEnvelope],
) -> Dict[str, Any]:
    """
    Structured navigation blob for tooling/tests (no side effects).

    Not persisted; safe to serialize for inspection UIs later.
    """
    by_id = {str(e.event_id): e for e in envelope_catalog}
    return {
        "final.pipeline.phase": final_state.pipeline.phase.value,
        "transition_trail": transition_trail_rows(final_state),
        "governance_ingress_index": governance_ingress_index(run_history=run_history, envelope_by_id=by_id),
        "runs_skill_summaries": [
            skills_contributing_by_run(r, persisted_snapshot=final_state) for r in run_history
        ],
    }


def render_operator_navigation_text(
    *,
    final_state: OrchestrationState,
    run_history: Sequence[OrchestrationExecutionResult],
    envelope_catalog: Sequence[EventEnvelope],
) -> str:
    """Short deterministic preamble suitable for pasting above/below a timeline."""
    nav = build_vertical_slice_operator_navigation(
        final_state=final_state,
        run_history=run_history,
        envelope_catalog=envelope_catalog,
    )
    lines: List[str] = []
    lines.append("=== operator navigation (inspection; deterministic) ===")
    lines.append(f"final.pipeline.phase={nav['final.pipeline.phase']}")
    lines.append(f"transitions.count={len(nav['transition_trail'])}")
    for i, row in enumerate(nav["transition_trail"], start=1):
        gov = ""
        if row.get("governance.decision_code"):
            gov = f" governance.decision_code={row['governance.decision_code']!r}"
        lines.append(
            f"  [{i}] {row['from_state']!r} -> {row['to_state']!r} trigger={row['trigger']!r}"
            f" rule={row.get('matched_rule_id')!r}{gov}"
        )
    gi = nav["governance_ingress_index"]
    if gi:
        lines.append(f"governance_ingress.count={len(gi)}")
        for g in gi:
            lines.append(
                f"  governance | run={g['run_index']} type={g['event_type']!r} ok={g['ok']}"
                f" actor={g.get('actor_id')!r} reason_preview={g.get('reason_preview')!r}"
            )
    lines.append("=== end operator navigation ===")
    return "\n".join(lines)
