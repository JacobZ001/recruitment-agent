"""
Fake deterministic deep scoring for vertical-slice orchestration validation.

Multi-stage scoring philosophy
-------------------------------
**Deep scoring** sits after structured intake and (in the slice) questionnaire completion:
it simulates a **later, evidence-rich** evaluation stage using **more factor dimensions**
than light scoring, still as a **pure deterministic function** of declared payloads—no
LLM, no embeddings, no autonomous hiring. The orchestrator owns progression; this skill
only emits **bounded signals** (normalized score, factor decomposition, recommendation
hints) for audit and downstream deterministic policy (``docs/architecture/ADR.md`` ADR-001).

Bounded confidence evolution
------------------------------
Confidence still measures **declared evidence coverage**, not model self-assurance, but
the deep stage applies a small **deterministic stage prior** when questionnaire fields
are omitted (pipeline context already implies questionnaire completion). Additional
explicit dimensions (evidence counts, communication/project signals) **boost**
confidence via a capped bonus—keeping semantics explainable and replay-stable without
wall-clock coupling.

Deterministic deep evaluation semantics
-----------------------------------------
Factors include the light-stage family (experience, keywords, profile completeness,
questionnaire readiness) plus **evidence density**, **declared communication quality**,
and **declared project depth**—each clamped and weighted. Weights merge with defaults
then renormalize so all dimensions exist for stable analytics keys.

Relationship to future cognition layers
-----------------------------------------
Hybrid or LLM skills can later supply richer **structured signals** into the same
envelope keys; the control plane should keep treating scores as **non-authoritative
signals** unless promoted by deterministic governance. This fake module defines the
**integration seam**: ``SkillOutputEnvelope`` with ``ConfidenceReport``, factor maps,
evaluation dimensions, evidence refs, and provenance ids.
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

SKILL_NAME: Final[str] = "recruitment.vertical_slice.deep_scoring"
SKILL_VERSION: Final[str] = "1.0.0"

_REFERENCE_TIME: Final[datetime] = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

_MAX_METRIC_KEYS: Final[int] = 64
_MAX_KEYWORDS: Final[int] = 24
_MAX_KEYWORD_LEN: Final[int] = 64
_MAX_PROFILE_FIELDS: Final[int] = 64
_MAX_DEFAULT_PROFILE_SLOTS: Final[int] = 32
_MAX_DIMENSION_ROWS: Final[int] = 16
_MAX_REC_HINTS: Final[int] = 8
_MAX_EVIDENCE_ITEMS: Final[int] = 10_000

# Valid RFC-4122 UUID namespace for uuid5 execution-id derivation (distinct from other slice fakes).
_EXECUTION_ID_NAMESPACE: Final[UUID] = UUID("018f3e2a-7c9b-4a3d-8f0e-000000000003")

_WEIGHT_KEYS: Final[Tuple[str, ...]] = (
    "years",
    "keywords",
    "completeness",
    "questionnaire",
    "evidence_density",
    "communication",
    "project_depth",
)

_DEFAULT_WEIGHTS: Final[Dict[str, float]] = {
    "years": 0.12,
    "keywords": 0.12,
    "completeness": 0.12,
    "questionnaire": 0.22,
    "evidence_density": 0.18,
    "communication": 0.12,
    "project_depth": 0.12,
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
    base: Dict[str, float] = {k: float(_DEFAULT_WEIGHTS[k]) for k in _WEIGHT_KEYS}
    if raw is None:
        return base
    if not isinstance(raw, Mapping):
        raise ValueError("scoring.recruiter_weights must be an object mapping factor names to weights")
    for k in _WEIGHT_KEYS:
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
    return {k: base[k] / s for k in _WEIGHT_KEYS}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _confidence_level(score: float) -> ConfidenceLevel:
    if score >= 0.78:
        return ConfidenceLevel.HIGH
    if score >= 0.52:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _recommendation_hints(score: float) -> Dict[str, Any]:
    """Deterministic recruiter-facing hints (signals only; orchestrator owns decisions)."""
    if score >= 0.72:
        tier = "favor_proceed"
        code = "deep.reco.proceed_review"
        hints = [
            "normalized_score_at_or_above_proceed_band",
            "confirm_human_review_before_shortlist",
        ]
    elif score >= 0.48:
        tier = "neutral_review"
        code = "deep.reco.mixed_signals"
        hints = [
            "normalized_score_in_mid_band",
            "request_additional_structured_evidence_if_policy_requires",
        ]
    else:
        tier = "caution"
        code = "deep.reco.hold_or_reject_signal"
        hints = [
            "normalized_score_below_mid_band",
            "deterministic_fake_skill_not_a_rejection_decision",
        ]
    return {
        "recruiter.recommendation.tier": tier,
        "recruiter.recommendation.code": code,
        "recruiter.recommendation.hints": hints[:_MAX_REC_HINTS],
    }


def _compute_deep_score(
    payload: Mapping[str, Any],
) -> Tuple[float, Dict[str, Any], Dict[str, float], ConfidenceReport, List[str], List[Dict[str, Any]]]:
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
    q_complete = _optional_bool(payload, "declared.questionnaire_completed")
    questionnaire_declared = (
        q_avail is not None or q_ready is not None or q_complete is not None
    )
    used_questionnaire_prior = False
    if q_ready is not None:
        questionnaire_component = _clamp01(q_ready)
    elif q_complete is not None:
        questionnaire_component = 1.0 if q_complete else 0.0
    elif q_avail is not None:
        questionnaire_component = 1.0 if q_avail else 0.0
    else:
        questionnaire_component = 0.78
        used_questionnaire_prior = True

    ev_n = _optional_int(payload, "declared.evidence_item_count")
    ev_slots = _optional_int(payload, "declared.evidence_max_slots")
    evidence_slots = int(ev_slots) if ev_slots is not None else 12
    evidence_slots = max(1, min(128, evidence_slots))
    evidence_declared = ev_n is not None
    if ev_n is None:
        evidence_component = 0.55
    else:
        ev_c = max(0, min(_MAX_EVIDENCE_ITEMS, int(ev_n)))
        evidence_component = _clamp01(ev_c / float(evidence_slots))

    comm = _optional_float(payload, "declared.communication_quality")
    communication_declared = comm is not None
    communication_component = _clamp01(comm) if comm is not None else 0.56

    proj = _optional_float(payload, "declared.project_depth_score")
    project_declared = proj is not None
    project_depth_component = _clamp01(proj) if proj is not None else 0.56

    score = sum(
        weights[k] * comp
        for k, comp in (
            ("years", experience_component),
            ("keywords", keyword_component),
            ("completeness", completeness_component),
            ("questionnaire", questionnaire_component),
            ("evidence_density", evidence_component),
            ("communication", communication_component),
            ("project_depth", project_depth_component),
        )
    )
    score = _clamp01(score)

    signal_count = sum(
        1
        for b in (
            years_declared,
            keywords_declared,
            completeness_declared,
            questionnaire_declared,
            evidence_declared,
            communication_declared,
            project_declared,
        )
        if b
    )

    deep_bonus_dims = sum(
        1 for b in (evidence_declared, communication_declared, project_declared) if b
    )
    deep_bonus = 0.06 * float(min(3, deep_bonus_dims))
    stage_bonus = 0.10 if used_questionnaire_prior else 0.0
    explicit_ratio = signal_count / 7.0
    confidence_raw = _clamp01(explicit_ratio + deep_bonus + stage_bonus)
    if confidence_raw < 0.20:
        confidence_raw = 0.20

    confidence = ConfidenceReport(
        score=_clamp01(confidence_raw),
        level=_confidence_level(confidence_raw),
        rationale_ref=(
            f"rationale://fake_deep_scoring/signals_explicit_{signal_count}_of_7"
            f"/deep_bonus_{deep_bonus_dims}"
        ),
        extensions={
            "signal_dimensions_observed": signal_count,
            "deep_bonus_dimensions": deep_bonus_dims,
            "used_questionnaire_stage_prior": used_questionnaire_prior,
        },
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
        "factors.questionnaire.completed": q_complete,
        "factors.questionnaire.component": round(questionnaire_component, 6),
        "factors.questionnaire.used_stage_prior": used_questionnaire_prior,
        "factors.evidence.item_count": ev_n,
        "factors.evidence.max_slots": evidence_slots,
        "factors.evidence.component": round(evidence_component, 6),
        "factors.communication.quality_input": comm,
        "factors.communication.component": round(communication_component, 6),
        "factors.project_depth.score_input": proj,
        "factors.project_depth.component": round(project_depth_component, 6),
        "factors.weights.effective": {k: round(weights[k], 6) for k in _WEIGHT_KEYS},
    }

    metrics: Dict[str, float] = {
        "scoring.deep.normalized_score": round(score, 6),
        "scoring.deep.signal_dimensions": float(signal_count),
        "scoring.deep.confidence_score": round(float(confidence.score or 0.0), 6),
        "factors.experience": round(experience_component, 6),
        "factors.keywords": round(keyword_component, 6),
        "factors.completeness": round(completeness_component, 6),
        "factors.questionnaire": round(questionnaire_component, 6),
        "factors.evidence_density": round(evidence_component, 6),
        "factors.communication": round(communication_component, 6),
        "factors.project_depth": round(project_depth_component, 6),
    }

    codes: List[str] = []
    if years_declared:
        codes.append("signal.years")
    if keywords_declared:
        codes.append("signal.keywords")
    if completeness_declared:
        codes.append("signal.completeness")
    if questionnaire_declared:
        codes.append("signal.questionnaire")
    if evidence_declared:
        codes.append("signal.evidence_density")
    if communication_declared:
        codes.append("signal.communication")
    if project_declared:
        codes.append("signal.project_depth")
    if used_questionnaire_prior:
        codes.append("signal.stage.questionnaire_prior")

    dimensions: List[Dict[str, Any]] = []
    for dim_id, comp, wkey in (
        ("experience", experience_component, "years"),
        ("keywords", keyword_component, "keywords"),
        ("profile_completeness", completeness_component, "completeness"),
        ("questionnaire", questionnaire_component, "questionnaire"),
        ("evidence_density", evidence_component, "evidence_density"),
        ("communication_quality", communication_component, "communication"),
        ("project_depth", project_depth_component, "project_depth"),
    ):
        dimensions.append(
            {
                "dimension.id": dim_id,
                "dimension.component": round(comp, 6),
                "dimension.weight": round(weights[wkey], 6),
                "dimension.weighted_contribution": round(weights[wkey] * comp, 6),
            }
        )

    return score, factors, metrics, confidence, codes, dimensions[:_MAX_DIMENSION_ROWS]


class FakeDeepScoringSkill:
    """
    Deterministic stand-in for recruiter deep scoring after questionnaire completion.

    Synchronous :class:`SkillInputEnvelope` execution without LLM, network, hidden
    ranking policy, or orchestration state mutation.
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
                "Fake deep scoring: multi-factor deterministic evaluation with bounded "
                "confidence and recruiter recommendation hints (vertical slice only)."
            ),
            input_contract_version="1.0",
            output_contract_version="1.0",
            supports_dry_run=True,
            supports_replay=True,
            supports_idempotency=True,
            tags=["vertical_slice", "fake", "recruitment", "deep_scoring"],
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
            runtime="skills.deterministic.fake_deep_scoring",
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
                        code="fake_deep_scoring.simulation.failed",
                        is_retryable=False,
                    ),
                    timing=timing,
                    audit=audit,
                    extensions={"simulation": "forced_execution_failure"},
                )

        try:
            planner_path = _require_non_empty_str(payload, "vertical_slice.planner_path")
            allowed_paths = (
                "deep_scoring_completed",
                "scoring_completed(disambiguated_deep)",
            )
            if planner_path not in allowed_paths:
                raise ValueError(
                    f"unexpected planner_path {planner_path!r} for {SKILL_NAME!r}"
                )
            ingested_event_id = _require_non_empty_str(payload, "ingested_event_id")
            ingested_event_type = _require_non_empty_str(payload, "ingested_event_type")

            expected_type = (
                "deep_scoring_completed"
                if planner_path == "deep_scoring_completed"
                else "scoring_completed"
            )
            if ingested_event_type != expected_type:
                raise ValueError(
                    f"ingested_event_type must be {expected_type!r}, got {ingested_event_type!r}"
                )

            score, factors, metrics, confidence, signal_codes, dimensions = _compute_deep_score(
                payload
            )
        except ValueError as exc:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.FAILED,
                failure=SkillFailure(
                    category=FailureCategory.VALIDATION_ERROR,
                    message=str(exc),
                    code="fake_deep_scoring.validation_error",
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
                            code="fake_deep_scoring.simulation.invalid_force_score",
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
                            code="fake_deep_scoring.simulation.invalid_force_confidence",
                            is_retryable=False,
                        ),
                        timing=timing,
                        audit=audit,
                    )

        if force_score is not None:
            score = _clamp01(force_score)
            metrics = {**metrics, "scoring.deep.normalized_score": round(score, 6)}
        if force_confidence is not None:
            fc_v = _clamp01(force_confidence)
            confidence = ConfidenceReport(
                score=fc_v,
                level=_confidence_level(fc_v),
                rationale_ref="rationale://fake_deep_scoring/harness_forced_confidence",
                extensions={"forced": True},
            )
            metrics = {**metrics, "scoring.deep.confidence_score": round(fc_v, 6)}

        reco = _recommendation_hints(score)

        if context.dry_run:
            return SkillExecutionResult(
                metadata=self.metadata,
                status=ExecutionStatus.SUCCEEDED,
                output=SkillOutputEnvelope(
                    payload={
                        "dry_run": True,
                        "scoring.deep.normalized_score_preview": round(score, 6),
                        "ingested_event_id": ingested_event_id,
                        "scoring.deep.signals_observed": signal_codes[:16],
                        "evaluation.dimensions_preview_count": len(dimensions),
                        "recruiter.recommendation.tier_preview": reco.get("recruiter.recommendation.tier"),
                    },
                    confidence=confidence,
                    extensions={"fake_skill": True},
                ),
                timing=timing,
                audit=audit,
                metrics={**_bounded_metrics(metrics), "simulated.dry_run": 1.0},
                extensions={"simulation": "dry_run"},
            )

        evidence_metric = EvidenceRef(
            kind=EvidenceKind.METRIC,
            ref=f"metric://deep_scoring/{ingested_event_id}",
            sha256=None,
            created_at=_REFERENCE_TIME,
            extensions={"role": "simulated_deep_scoring_metrics"},
        )
        evidence_struct = EvidenceRef(
            kind=EvidenceKind.STRUCTURED_RECORD,
            ref=f"structured://deep_scoring/{ingested_event_id}",
            sha256=None,
            created_at=_REFERENCE_TIME,
            extensions={"role": "simulated_deep_scoring_evaluation"},
        )

        out_payload: Dict[str, Any] = {
            "scoring.simulation": True,
            "scoring.kind": "deep",
            "scoring.deep.normalized_score": round(score, 6),
            "scoring.deep.signal_codes": signal_codes[:40],
            "scoring.deep.explainability": (
                "Deep normalized score is a seven-factor weighted blend of declared "
                "structured signals; not LLM, embedding, or autonomous hiring output."
            ),
            "evaluation.dimensions": dimensions,
            "evaluation.stage": "post_questionnaire_deep_slice",
            **factors,
            **reco,
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
                evidence_refs=[evidence_metric, evidence_struct],
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
                "execution.semantics": "deterministic_fake_deep_scoring",
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
