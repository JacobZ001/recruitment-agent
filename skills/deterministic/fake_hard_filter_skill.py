"""
Fake deterministic hard-filter execution for vertical-slice orchestration validation.

Deterministic hard-filter philosophy
-------------------------------------
A **hard filter** is eligibility gating: binary pass/fail with **auditable reasons**, not
ranking or semantic hiring judgment. This module simulates that gate using only
**declared, structured signals** in the skill payload (keywords, years, mandatory field
names, work authorization strings)—no CV parsing, no LLM, no external APIs. Rules are
pure functions of those inputs so the same envelope + payload yields the same outcome
for replay and harness tests (see ``docs/architecture/ADR.md`` ADR-001).

Explainable rejection semantics
--------------------------------
Rejections emit **stable machine-oriented reason codes** (e.g. missing mandatory field,
insufficient declared experience) rather than opaque scores. Free-text rationale belongs
in stored artifacts referenced elsewhere; here we keep outputs bounded and suitable for
deterministic orchestration records and transition audit trails.

Relationship to orchestrator / runtime
----------------------------------------
:class:`~orchestrator.vertical_slice_planner.VerticalSlicePlanner` invokes
``recruitment.vertical_slice.hard_filter`` on ``hard_filter_passed`` and
``hard_filter_failed`` ingress with ``outcome`` and ``vertical_slice.planner_path`` set.
The orchestrator already owns **which** transition fires; this skill records **bounded
deterministic evaluation** for explainability and runtime integration tests. It does
**not** mutate state, publish events, or override planner routing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Final, List, Mapping, Optional, Sequence, Tuple
from uuid import UUID, uuid5

from interfaces.skill_interface import (
    DeterminismClass,
    DeterministicBoundary,
    EvidenceKind,
    EvidenceRef,
    ExecutionAudit,
    ExecutionContext,
    ExecutionStatus,
    ExecutionTiming,
    FailureCategory,
    SkillExecutionResult,
    SkillFailure,
    SkillInputEnvelope,
    SkillKind,
    SkillMetadata,
    SkillOutputEnvelope,
    SkillInterfaceVersion,
)

# Stable registry key — must match ``SKILL_HARD_FILTER`` in
# ``orchestrator.vertical_slice_planner``.
SKILL_NAME: Final[str] = "recruitment.vertical_slice.hard_filter"
SKILL_VERSION: Final[str] = "1.0.0"

_REFERENCE_TIME: Final[datetime] = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

_MAX_REASON_CODES: Final[int] = 32
_MAX_KEYWORD_LEN: Final[int] = 64
_MAX_KEYWORDS: Final[int] = 24
_MAX_MANDATORY_FIELDS: Final[int] = 32
_MAX_METRIC_KEYS: Final[int] = 48

_EXECUTION_ID_NAMESPACE: Final[UUID] = UUID("018f3e2a-7c9b-7a3d-9f0e-recruitment01")

_ALLOWED_WORK_AUTH: Final[Tuple[str, ...]] = (
    "yes",
    "authorized",
    "citizen",
    "permanent_resident",
    "visa_sponsored_ok",
)


def _execution_id(context: ExecutionContext) -> UUID:
    raw = (context.extensions or {}).get("orchestrator_skill_execution_id")
    if raw:
        return UUID(str(raw))
    basis = "|".join(
        (
            str(context.event_id or ""),
            str(context.subject_id or ""),
            str(context.correlation_id or ""),
            SKILL_NAME,
        )
    )
    return uuid5(_EXECUTION_ID_NAMESPACE, basis)


def _require_non_empty_str(payload: Mapping[str, Any], key: str) -> str:
    raw = payload.get(key)
    if raw is None:
        raise ValueError(f"missing required payload key: {key!r}")
    s = str(raw).strip()
    if not s:
        raise ValueError(f"payload key {key!r} must be non-empty")
    return s


def _optional_int(payload: Mapping[str, Any], key: str) -> Optional[int]:
    raw = payload.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"payload key {key!r} must be an integral number if present")
    return int(raw)


def _optional_str(payload: Mapping[str, Any], key: str) -> Optional[str]:
    raw = payload.get(key)
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s else None


def _normalized_keyword_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.replace(",", " ").split() if p.strip()]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        parts = [str(x).strip().lower() for x in raw if str(x).strip()]
    else:
        raise ValueError("declared.skill_keywords must be a string or a list of strings")
    out: List[str] = []
    for p in parts[:_MAX_KEYWORDS]:
        if len(p) > _MAX_KEYWORD_LEN:
            raise ValueError("declared.skill_keywords entry exceeds max length")
        out.append(p)
    return out


def _mandatory_fields_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("filter.mandatory_fields must be a list of field names")
    out: List[str] = []
    for x in raw[:_MAX_MANDATORY_FIELDS]:
        s = str(x).strip()
        if not s:
            continue
        if len(s) > _MAX_KEYWORD_LEN:
            raise ValueError("filter.mandatory_fields entry exceeds max length")
        out.append(s)
    return out


def _required_keywords_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.replace(",", " ").split() if p.strip()]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        parts = [str(x).strip().lower() for x in raw if str(x).strip()]
    else:
        raise ValueError("filter.required_keywords must be a string or a list of strings")
    out: List[str] = []
    for p in parts[:_MAX_KEYWORDS]:
        if len(p) > _MAX_KEYWORD_LEN:
            raise ValueError("filter.required_keywords entry exceeds max length")
        out.append(p)
    return out


def _present_fields_set(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("declared.present_fields must be a list of field names")
    return {str(x).strip() for x in raw if str(x).strip()}


def _evaluate_gates(payload: Mapping[str, Any]) -> Tuple[bool, List[str], Dict[str, float]]:
    """
    Pure deterministic gate evaluation. Returns (passed, reason_codes, metrics).

    No wall-clock; bounded reason list.
    """
    reasons: List[str] = []
    metrics: Dict[str, float] = {"gates.checked": 0.0}

    min_years = _optional_int(payload, "filter.min_years_experience")
    if min_years is not None and (min_years < 0 or min_years > 60):
        raise ValueError("filter.min_years_experience must be in 0..60 if present")

    declared_years = _optional_int(payload, "declared.years_experience")
    work_auth = _optional_str(payload, "declared.work_authorization")
    skill_kw = _normalized_keyword_list(payload.get("declared.skill_keywords"))
    present = _present_fields_set(payload.get("declared.present_fields"))
    mandatory = _mandatory_fields_list(payload.get("filter.mandatory_fields"))
    required_kw = _required_keywords_list(payload.get("filter.required_keywords"))

    passed = True

    if work_auth is not None:
        metrics["gates.checked"] += 1.0
        normalized = work_auth.lower().replace(" ", "_").replace("-", "_")
        if normalized not in _ALLOWED_WORK_AUTH:
            passed = False
            reasons.append("WORK_AUTHORIZATION_NOT_ALLOWED")

    if min_years is not None:
        metrics["gates.checked"] += 1.0
        if declared_years is None:
            passed = False
            reasons.append("DECLARED_YEARS_EXPERIENCE_MISSING")
        elif declared_years < min_years:
            passed = False
            reasons.append("DECLARED_YEARS_BELOW_MINIMUM")

    if required_kw:
        metrics["gates.checked"] += 1.0
        haystack = " ".join(skill_kw)
        for req in required_kw:
            if req not in haystack:
                passed = False
                reasons.append(f"REQUIRED_KEYWORD_MISSING:{req}")

    if mandatory:
        metrics["gates.checked"] += 1.0
        for field in mandatory:
            if field not in present:
                passed = False
                reasons.append(f"MANDATORY_FIELD_MISSING:{field}")

    metrics["filter.reason_count"] = float(min(len(reasons), _MAX_REASON_CODES))
    metrics["filter.passed"] = 1.0 if passed else 0.0

    return passed, reasons[:_MAX_REASON_CODES], metrics


class FakeHardFilterSkill:
    """
    Deterministic stand-in for recruiter hard-filter gating on the vertical slice.

    Implements synchronous :class:`SkillInputEnvelope` execution without LLM, network,
    ranking, or orchestration mutation.
    """

    metadata: SkillMetadata

    def __init__(self) -> None:
        self.metadata = SkillMetadata(
            skill_name=SKILL_NAME,
            skill_version=SKILL_VERSION,
            kind=SkillKind.DETERMINISTIC,
            boundary=DeterministicBoundary(
                determinism_class=DeterminismClass.PURE_DETERMINISTIC,
                kind=SkillKind.DETERMINISTIC,
                requires_input_snapshot=False,
                requires_output_snapshot=False,
                requires_model_capture=False,
            ),
            description=(
                "Fake hard filter: deterministic eligibility simulation with explainable "
                "reason codes (vertical slice only)."
            ),
            input_contract_version="1.0",
            output_contract_version="1.0",
            supports_dry_run=True,
            supports_replay=True,
            supports_idempotency=True,
            tags=["vertical_slice", "fake", "recruitment", "hard_filter"],
        )

    def execute(
        self, skill_input: SkillInputEnvelope, context: ExecutionContext
    ) -> SkillExecutionResult:
        payload = skill_input.payload or {}
        timing = ExecutionTiming(
            started_at=_REFERENCE_TIME,
            ended_at=_REFERENCE_TIME,
            duration_ms=0,
        )
        audit = ExecutionAudit(
            execution_id=_execution_id(context),
            recorded_at=_REFERENCE_TIME,
            runtime="skills.deterministic.fake_hard_filter",
            model_info={},
            extensions={"fake_skill": True, "skill_version": SKILL_VERSION},
        )

        sim = payload.get("simulation")
        if isinstance(sim, Mapping):
            if sim.get("outcome") == "failed":
                return SkillExecutionResult(
                    metadata=self.metadata,
                    status=ExecutionStatus.FAILED,
                    failure=SkillFailure(
                        category=FailureCategory.PERMANENT,
                        message="Deterministic simulation requested execution failure (harness hook).",
                        code="fake_hard_filter.simulation.failed",
                        is_retryable=False,
                    ),
                    timing=timing,
                    audit=audit,
                    extensions={"simulation": "forced_execution_failure"},
                )

        try:
            planner_path = _require_non_empty_str(payload, "vertical_slice.planner_path")
            if planner_path not in ("hard_filter_passed", "hard_filter_failed"):
                raise ValueError(
                    f"unexpected planner_path {planner_path!r} for {SKILL_NAME!r}"
                )
            ingested_event_id = _require_non_empty_str(payload, "ingested_event_id")
            ingested_event_type = _require_non_empty_str(payload, "ingested_event_type")

            expected_event = (
                "hard_filter_passed"
                if planner_path == "hard_filter_passed"
                else "hard_filter_failed"
            )
            if ingested_event_type != expected_event:
                raise ValueError(
                    f"ingested_event_type must be {expected_event!r}, got {ingested_event_type!r}"
                )

            outcome = _optional_str(payload, "outcome")
            if outcome is None:
                raise ValueError("missing required payload key: 'outcome'")
            if outcome not in ("passed", "failed"):
                raise ValueError("outcome must be 'passed' or 'failed'")
            if (planner_path == "hard_filter_passed" and outcome != "passed") or (
                planner_path == "hard_filter_failed" and outcome != "failed"
            ):
                raise ValueError(
                    f"outcome {outcome!r} inconsistent with planner_path {planner_path!r}"
                )

            computed_pass, reason_codes, gate_metrics = _evaluate_gates(payload)
            gates_checked = int(gate_metrics.get("gates.checked", 0.0))
            if gates_checked == 0:
                # Default slice payloads carry only planner correlation + outcome; with no
                # declared gate inputs, align the recorded decision to the ingress branch
                # so optional post-transition skills do not spuriously signal mismatch.
                computed_pass = outcome == "passed"
                reason_codes = (
                    []
                    if computed_pass
                    else ["NO_DECLARED_GATES.planner_inactive_branch_only"]
                )
        except ValueError as exc:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.FAILED,
                failure=SkillFailure(
                    category=FailureCategory.VALIDATION_ERROR,
                    message=str(exc),
                    code="fake_hard_filter.validation_error",
                    is_retryable=False,
                ),
                timing=timing,
                audit=audit,
            )

        force_decision: Optional[str] = None
        if isinstance(sim, Mapping):
            raw_force = sim.get("force_decision")
            if raw_force is not None:
                force_decision = str(raw_force).strip().lower()
                if force_decision not in ("pass", "fail"):
                    return SkillExecutionResult(
                        metadata=self.metadata,
                        status=ExecutionStatus.FAILED,
                        failure=SkillFailure(
                            category=FailureCategory.VALIDATION_ERROR,
                            message="simulation.force_decision must be 'pass' or 'fail'",
                            code="fake_hard_filter.simulation.invalid_force",
                            is_retryable=False,
                        ),
                        timing=timing,
                        audit=audit,
                    )

        if force_decision == "pass":
            computed_pass = True
            reason_codes = []
        elif force_decision == "fail":
            computed_pass = False
            reason_codes = ["HARNESS_FORCED_FAIL"]

        planner_announced_pass = outcome == "passed"
        mismatch = planner_announced_pass != computed_pass

        if context.dry_run:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.SUCCEEDED,
                output=SkillOutputEnvelope(
                    payload={
                        "dry_run": True,
                        "would_pass": computed_pass,
                        "ingested_event_id": ingested_event_id,
                        "filter.reason_codes_preview": reason_codes[:8],
                    },
                    extensions={"fake_skill": True},
                ),
                timing=timing,
                audit=audit,
                metrics={**gate_metrics, "simulated.dry_run": 1.0},
                extensions={"simulation": "dry_run"},
            )

        filter_decision = "passed" if computed_pass else "failed"
        base_out: Dict[str, Any] = {
            "filter.simulation": True,
            "filter.decision": filter_decision,
            "filter.computed_pass": computed_pass,
            "filter.planner_announced_outcome": outcome,
            "filter.planner_path": planner_path,
            "filter.rejection.reason_codes": reason_codes,
            "filter.gates.evaluated_count": int(gate_metrics.get("gates.checked", 0.0)),
            "provenance.ingested_event_id": ingested_event_id,
            "provenance.ingested_event_type": ingested_event_type,
        }
        if context.event_id:
            base_out["provenance.context_event_id"] = str(context.event_id)
        if context.subject_id:
            base_out["provenance.subject_id"] = str(context.subject_id)

        evidence = EvidenceRef(
            kind=EvidenceKind.STRUCTURED_RECORD,
            ref=f"structured://hard_filter/{ingested_event_id}",
            sha256=None,
            created_at=_REFERENCE_TIME,
            extensions={"role": "simulated_hard_filter_record"},
        )

        out_env = SkillOutputEnvelope(
            payload=base_out,
            evidence_refs=[evidence],
            extensions={
                "fake_skill": True,
                "interface_version": SkillInterfaceVersion.V1.value,
            },
        )

        if mismatch:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.PARTIAL_SUCCESS,
                output=out_env,
                failure=SkillFailure(
                    category=FailureCategory.VALIDATION_ERROR,
                    message=(
                        "Planner branch outcome disagrees with deterministic gate evaluation "
                        "on declared payload signals (audit signal only)."
                    ),
                    code="fake_hard_filter.planner_signal_mismatch",
                    is_retryable=False,
                    extensions={"computed_pass": computed_pass, "planner_outcome": outcome},
                ),
                timing=timing,
                audit=audit,
                metrics=_bounded_metrics(gate_metrics),
                extensions={
                    "execution.semantics": "deterministic_fake_hard_filter",
                    "filter.planner_signal_mismatch": True,
                    "replay.note": (
                        "Timing uses module reference clock; order timelines by event ids."
                    ),
                },
            )

        return SkillExecutionResult(
            metadata=self.metadata,
            status=ExecutionStatus.SUCCEEDED,
            output=out_env,
            timing=timing,
            audit=audit,
            metrics=_bounded_metrics(gate_metrics),
            extensions={
                "execution.semantics": "deterministic_fake_hard_filter",
                "replay.note": (
                    "Timing uses module reference clock; order timelines by event ids."
                ),
            },
        )


def _bounded_metrics(metrics: Dict[str, float]) -> Dict[str, float]:
    """Drop excess keys to keep execution records bounded."""
    if len(metrics) <= _MAX_METRIC_KEYS:
        return metrics
    keys = sorted(metrics.keys())[:_MAX_METRIC_KEYS]
    return {k: metrics[k] for k in keys}
