"""
Fake deterministic light scoring for vertical-slice orchestration validation.

Deterministic scoring philosophy
---------------------------------
**Light scoring** here means a **bounded numeric blend** of explicitly declared signals
(years, keyword coverage, profile completeness, questionnaire readiness)—not semantic
matching, embeddings, or production ranking. The function is fixed and pure so the same
payload + context identifiers yield the same normalized score for replay and harness
tests. **Programs** still own transitions and gating; this skill only emits **signals**
(``SkillOutputEnvelope``) for audit and downstream policy (see ``docs/architecture/ADR.md``
ADR-001).

Bounded confidence semantics
-----------------------------
**Confidence** reflects how much **declared evidence** was available to score—not model
self-assurance. Fewer populated dimensions lowers the confidence score and maps to
:class:`ConfidenceLevel` (low / medium / high) deterministically. This keeps semantics
honest for governance and avoids pretending certainty when inputs are sparse. Future
LLM/hybrid skills can reuse the same ``ConfidenceReport`` envelope while swapping the
derivation behind the interface boundary.

Relationship to future cognition layers
-----------------------------------------
Real cognition may replace or augment factor extraction with LLM-derived **signals**
still shaped as typed payloads. This fake skill establishes **integration seams**:
normalized score in ``[0, 1]``, factor breakdown dict, ``ConfidenceReport``, and
evidence refs—without entangling routing, retries, or state mutation in the skill.

Replay-safe scoring design
---------------------------
Timing and evidence stamps use the module **reference clock** (not wall-clock), and
``ExecutionAudit.execution_id`` aligns with orchestrator-injected ids when present, same
as other vertical-slice fakes. Provenance keys tie results to ``ingested_event_id`` for
timeline correlation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Final, List, Mapping, Optional, Sequence, Tuple
from uuid import UUID, uuid5

from interfaces.skill_interface import (
    ConfidenceLevel,
    ConfidenceReport,
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

SKILL_NAME: Final[str] = "recruitment.vertical_slice.light_scoring"
SKILL_VERSION: Final[str] = "1.0.0"

_REFERENCE_TIME: Final[datetime] = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

_MAX_METRIC_KEYS: Final[int] = 48
_MAX_KEYWORDS: Final[int] = 24
_MAX_KEYWORD_LEN: Final[int] = 64
_MAX_PROFILE_FIELDS: Final[int] = 64
_MAX_DEFAULT_PROFILE_SLOTS: Final[int] = 32

_EXECUTION_ID_NAMESPACE: Final[UUID] = UUID("018f3e2a-7c9b-7a3d-9f0e-recruitment02")

_DEFAULT_WEIGHTS: Final[Dict[str, float]] = {
    "years": 0.35,
    "keywords": 0.35,
    "completeness": 0.20,
    "questionnaire": 0.10,
}


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


def _optional_float(payload: Mapping[str, Any], key: str) -> Optional[float]:
    raw = payload.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"payload key {key!r} must be a number if present")
    return float(raw)


def _optional_bool(payload: Mapping[str, Any], key: str) -> Optional[bool]:
    raw = payload.get(key)
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)) and raw in (0, 1):
        return bool(int(raw))
    s = str(raw).strip().lower()
    if s in ("true", "yes", "1"):
        return True
    if s in ("false", "no", "0"):
        return False
    raise ValueError(f"payload key {key!r} must be a boolean if present")


def _normalized_keyword_haystack(raw: Any) -> str:
    if raw is None:
        return ""
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
    return " ".join(out)


def _required_keywords_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.replace(",", " ").split() if p.strip()]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        parts = [str(x).strip().lower() for x in raw if str(x).strip()]
    else:
        raise ValueError("scoring.required_keywords must be a string or a list of strings")
    out: List[str] = []
    for p in parts[:_MAX_KEYWORDS]:
        if len(p) > _MAX_KEYWORD_LEN:
            raise ValueError("scoring.required_keywords entry exceeds max length")
        out.append(p)
    return out


def _present_fields_count(raw: Any) -> int:
    if raw is None:
        return 0
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("declared.present_fields must be a list of field names")
    n = 0
    for x in raw[:_MAX_PROFILE_FIELDS]:
        if str(x).strip():
            n += 1
    return n


def _normalize_recruiter_weights(raw: Any) -> Dict[str, float]:
    keys = ("years", "keywords", "completeness", "questionnaire")
    base: Dict[str, float] = {k: float(_DEFAULT_WEIGHTS[k]) for k in keys}
    if raw is None:
        return base
    if not isinstance(raw, Mapping):
        raise ValueError("scoring.recruiter_weights must be an object mapping factor names to weights")
    for k in keys:
        v = raw.get(k)
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"scoring.recruiter_weights[{k!r}] must be a non-negative number")
        fv = float(v)
        if fv < 0.0:
            raise ValueError(f"scoring.recruiter_weights[{k!r}] must be non-negative")
        base[k] = fv
    s = sum(base.values())
    if s <= 0.0:
        raise ValueError("scoring.recruiter_weights must sum to a positive value after merge with defaults")
    return {k: base[k] / s for k in keys}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _confidence_level(score: float) -> ConfidenceLevel:
    if score >= 0.75:
        return ConfidenceLevel.HIGH
    if score >= 0.45:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _compute_light_score(
    payload: Mapping[str, Any],
) -> Tuple[float, Dict[str, Any], Dict[str, float], ConfidenceReport, List[str]]:
    """
    Returns (normalized_score, factors_payload, metrics, confidence_report, signals_present_flags as codes).
    """
    weights = _normalize_recruiter_weights(payload.get("scoring.recruiter_weights"))

    years = _optional_int(payload, "declared.years_experience")
    years_declared = years is not None
    y = float(years) if years is not None else 0.0
    y = max(0.0, min(60.0, y))
    experience_component = _clamp01(y / 20.0)

    req_kw = _required_keywords_list(payload.get("scoring.required_keywords"))
    hay = _normalized_keyword_haystack(payload.get("declared.skill_keywords"))
    keywords_declared = bool(hay) or bool(req_kw)
    if not req_kw:
        keyword_component = 1.0
        kw_matched = 0
        kw_total = 0
    else:
        kw_total = len(req_kw)
        kw_matched = sum(1 for r in req_kw if r in hay)
        keyword_component = _clamp01(kw_matched / max(1, kw_total))

    ratio = _optional_float(payload, "declared.profile_completeness_ratio")
    present_n = _present_fields_count(payload.get("declared.present_fields"))
    slots = _optional_int(payload, "declared.profile_field_slots")
    slot_n = int(slots) if slots is not None else 8
    slot_n = max(1, min(_MAX_DEFAULT_PROFILE_SLOTS, slot_n))

    completeness_declared = ratio is not None or present_n > 0
    if ratio is not None:
        completeness_component = _clamp01(ratio)
    else:
        completeness_component = _clamp01(present_n / float(slot_n))

    q_avail = _optional_bool(payload, "declared.questionnaire_available")
    q_ready = _optional_float(payload, "declared.questionnaire_readiness")
    questionnaire_declared = q_avail is not None or q_ready is not None
    if q_ready is not None:
        questionnaire_component = _clamp01(q_ready)
    elif q_avail is not None:
        questionnaire_component = 1.0 if q_avail else 0.0
    else:
        questionnaire_component = 0.5

    score = (
        weights["years"] * experience_component
        + weights["keywords"] * keyword_component
        + weights["completeness"] * completeness_component
        + weights["questionnaire"] * questionnaire_component
    )
    score = _clamp01(score)

    signal_count = sum(
        1 for b in (years_declared, keywords_declared, completeness_declared, questionnaire_declared) if b
    )
    confidence_raw = _clamp01(signal_count / 4.0)
    if confidence_raw < 0.15:
        confidence_raw = 0.15
    confidence = ConfidenceReport(
        score=_clamp01(confidence_raw),
        level=_confidence_level(confidence_raw),
        rationale_ref=f"rationale://fake_light_scoring/signal_coverage/{signal_count}_of_4",
        extensions={"signal_dimensions_observed": signal_count},
    )

    factors: Dict[str, Any] = {
        "factors.experience.years_input": years if years_declared else None,
        "factors.experience.component": round(experience_component, 6),
        "factors.keywords.required_count": kw_total,
        "factors.keywords.matched_count": kw_matched,
        "factors.keywords.component": round(keyword_component, 6),
        "factors.completeness.ratio_input": ratio,
        "factors.completeness.present_fields_count": present_n,
        "factors.completeness.profile_field_slots": slot_n,
        "factors.completeness.component": round(completeness_component, 6),
        "factors.questionnaire.available": q_avail,
        "factors.questionnaire.readiness_input": q_ready,
        "factors.questionnaire.component": round(questionnaire_component, 6),
        "factors.weights.effective": {k: round(weights[k], 6) for k in sorted(weights.keys())},
    }

    metrics: Dict[str, float] = {
        "scoring.normalized_score": round(score, 6),
        "scoring.signal_dimensions": float(signal_count),
        "scoring.confidence_score": round(float(confidence.score or 0.0), 6),
        "factors.experience": round(experience_component, 6),
        "factors.keywords": round(keyword_component, 6),
        "factors.completeness": round(completeness_component, 6),
        "factors.questionnaire": round(questionnaire_component, 6),
    }

    codes = []
    if years_declared:
        codes.append("signal.years")
    if keywords_declared:
        codes.append("signal.keywords")
    if completeness_declared:
        codes.append("signal.completeness")
    if questionnaire_declared:
        codes.append("signal.questionnaire")

    return score, factors, metrics, confidence, codes


class FakeLightScoringSkill:
    """
    Deterministic stand-in for recruiter light scoring on the vertical slice.

    Synchronous :class:`SkillInputEnvelope` execution without LLM, network, ranking policy
    in the control plane, or orchestration state mutation.
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
                "Fake light scoring: bounded deterministic score + confidence from declared "
                "signals (vertical slice only)."
            ),
            input_contract_version="1.0",
            output_contract_version="1.0",
            supports_dry_run=True,
            supports_replay=True,
            supports_idempotency=True,
            tags=["vertical_slice", "fake", "recruitment", "light_scoring"],
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
            runtime="skills.deterministic.fake_light_scoring",
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
                        code="fake_light_scoring.simulation.failed",
                        is_retryable=False,
                    ),
                    timing=timing,
                    audit=audit,
                    extensions={"simulation": "forced_execution_failure"},
                )

        try:
            planner_path = _require_non_empty_str(payload, "vertical_slice.planner_path")
            allowed_paths = (
                "light_scoring_completed",
                "scoring_completed(disambiguated_light)",
            )
            if planner_path not in allowed_paths:
                raise ValueError(
                    f"unexpected planner_path {planner_path!r} for {SKILL_NAME!r}"
                )
            ingested_event_id = _require_non_empty_str(payload, "ingested_event_id")
            ingested_event_type = _require_non_empty_str(payload, "ingested_event_type")

            expected_type = (
                "light_scoring_completed"
                if planner_path == "light_scoring_completed"
                else "scoring_completed"
            )
            if ingested_event_type != expected_type:
                raise ValueError(
                    f"ingested_event_type must be {expected_type!r}, got {ingested_event_type!r}"
                )

            score, factors, metrics, confidence, signal_codes = _compute_light_score(payload)
        except ValueError as exc:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.FAILED,
                failure=SkillFailure(
                    category=FailureCategory.VALIDATION_ERROR,
                    message=str(exc),
                    code="fake_light_scoring.validation_error",
                    is_retryable=False,
                ),
                timing=timing,
                audit=audit,
            )

        force_score: Optional[float] = None
        force_confidence: Optional[float] = None
        if isinstance(sim, Mapping):
            fs = sim.get("force_score")
            if fs is not None:
                force_score = float(fs)
                if force_score < 0.0 or force_score > 1.0:
                    return SkillExecutionResult(
                        metadata=self.metadata,
                        status=ExecutionStatus.FAILED,
                        failure=SkillFailure(
                            category=FailureCategory.VALIDATION_ERROR,
                            message="simulation.force_score must be in [0, 1]",
                            code="fake_light_scoring.simulation.invalid_force_score",
                            is_retryable=False,
                        ),
                        timing=timing,
                        audit=audit,
                    )
            fc = sim.get("force_confidence")
            if fc is not None:
                force_confidence = float(fc)
                if force_confidence < 0.0 or force_confidence > 1.0:
                    return SkillExecutionResult(
                        metadata=self.metadata,
                        status=ExecutionStatus.FAILED,
                        failure=SkillFailure(
                            category=FailureCategory.VALIDATION_ERROR,
                            message="simulation.force_confidence must be in [0, 1]",
                            code="fake_light_scoring.simulation.invalid_force_confidence",
                            is_retryable=False,
                        ),
                        timing=timing,
                        audit=audit,
                    )

        if force_score is not None:
            score = _clamp01(force_score)
            metrics = {**metrics, "scoring.normalized_score": round(score, 6)}
        if force_confidence is not None:
            fc_v = _clamp01(force_confidence)
            confidence = ConfidenceReport(
                score=fc_v,
                level=_confidence_level(fc_v),
                rationale_ref="rationale://fake_light_scoring/harness_forced_confidence",
                extensions={"forced": True},
            )
            metrics = {**metrics, "scoring.confidence_score": round(fc_v, 6)}

        if context.dry_run:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.SUCCEEDED,
                output=SkillOutputEnvelope(
                    payload={
                        "dry_run": True,
                        "scoring.normalized_score_preview": round(score, 6),
                        "ingested_event_id": ingested_event_id,
                        "scoring.signals_observed": signal_codes[:16],
                    },
                    confidence=confidence,
                    extensions={"fake_skill": True},
                ),
                timing=timing,
                audit=audit,
                metrics={**_bounded_metrics(metrics), "simulated.dry_run": 1.0},
                extensions={"simulation": "dry_run"},
            )

        evidence = EvidenceRef(
            kind=EvidenceKind.METRIC,
            ref=f"metric://light_scoring/{ingested_event_id}",
            sha256=None,
            created_at=_REFERENCE_TIME,
            extensions={"role": "simulated_light_scoring_snapshot"},
        )

        out_payload: Dict[str, Any] = {
            "scoring.simulation": True,
            "scoring.kind": "light",
            "scoring.normalized_score": round(score, 6),
            "scoring.signal_codes": signal_codes[:32],
            "scoring.explainability": (
                "Normalized score is a weighted linear blend of bounded factor components; "
                "not LLM or embedding output."
            ),
            **factors,
            "provenance.ingested_event_id": ingested_event_id,
            "provenance.ingested_event_type": ingested_event_type,
            "provenance.planner_path": planner_path,
        }
        if context.event_id:
            out_payload["provenance.context_event_id"] = str(context.event_id)
        if context.subject_id:
            out_payload["provenance.subject_id"] = str(context.subject_id)

        return SkillExecutionResult(
            metadata=self.metadata,
            status=ExecutionStatus.SUCCEEDED,
            output=SkillOutputEnvelope(
                payload=out_payload,
                evidence_refs=[evidence],
                confidence=confidence,
                extensions={
                    "fake_skill": True,
                    "interface_version": SkillInterfaceVersion.V1.value,
                },
            ),
            timing=timing,
            audit=audit,
            metrics=_bounded_metrics(metrics),
            extensions={
                "execution.semantics": "deterministic_fake_light_scoring",
                "replay.note": (
                    "Timing uses module reference clock; correlate timelines via provenance.*"
                ),
            },
        )


def _bounded_metrics(metrics: Dict[str, float]) -> Dict[str, float]:
    if len(metrics) <= _MAX_METRIC_KEYS:
        return metrics
    keys = sorted(metrics.keys())[:_MAX_METRIC_KEYS]
    return {k: metrics[k] for k in keys}
