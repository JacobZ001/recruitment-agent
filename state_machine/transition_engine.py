"""
Deterministic workflow transition validation engine.

Purpose
-------
Validate that proposed state transitions are allowed under explicit rules, with
optional guards, terminal-state protection, and replay-aware invariants. This
module is **control-plane validation only**: it does not mutate state, emit
events, call LLMs, or implement orchestration loops.

Boundaries
----------
- **In scope**: rule registry lookup, trigger matching, guard evaluation hooks,
  structured accept/reject results with explainable reasons.
- **Out of scope**: orchestration, event bus, persistence, retries, async
  execution, workflow execution.

Invariants
----------
- All decisions are deterministic given the same registry, context, and guard
  outcomes.
- Rejections are always explainable via structured codes and human-readable
  messages (audit/replay friendly).
- Human governance: transitions that would be blocked by terminal rules may be
  permitted when ``TransitionContext.human_override`` is true (operator-driven).

Evolution
---------
Rules are data (``TransitionRule``) registered in ``TransitionRegistry``. Add
edges and guards without changing engine logic. Prefer versioned rule sets for
replay consistency (see ``TransitionContext.rule_set_id``).

Trigger naming (lightweight governance)
-----------------------------------------
``TransitionContext.trigger`` and each entry in ``TransitionRule.allowed_triggers``
must use stable string identifiers (no enums required). Allowed prefixes:

- ``event:<name>`` — correlate with ingestion / domain events (e.g. ``event:cv_parsed``).
- ``manual_<name>`` — human-operator or explicit manual actions (e.g. ``manual_override``).
- ``system_<name>`` — deterministic system-initiated triggers (e.g. ``system_reconcile``).

``<name>`` is ``snake_case`` or ``dot.namespace.style`` (lowercase segments). Triggers
must not be empty or contain whitespace. This keeps replay and audit logs consistent
without centralizing every trigger into a single enum.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Protocol, Tuple
from uuid import UUID

from pydantic import BaseModel, Field

try:  # Pydantic v2
    from pydantic import ConfigDict, field_validator, model_validator

    _PYDANTIC_V2 = True
except Exception:  # Pydantic v1 fallback
    from pydantic import root_validator, validator as field_validator  # type: ignore

    _PYDANTIC_V2 = False

from schemas.state_schema import StateActor, StateDomain

# Stable name tail: snake_case or dot.namespace (lowercase).
_TRIGGER_NAME = r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*"
_TRIGGER_PATTERN = re.compile(
    rf"^(?:event:{_TRIGGER_NAME}|manual_{_TRIGGER_NAME}|system_{_TRIGGER_NAME})$"
)


def validate_trigger_naming(value: str) -> str:
    """
    Validate trigger strings for deterministic, replay-safe naming.

    Does not enumerate all triggers; only enforces format conventions.
    """
    if not value or not value.strip():
        raise ValueError("trigger must be a non-empty string")
    if value != value.strip():
        raise ValueError("trigger must not have leading or trailing whitespace")
    if any(ch.isspace() for ch in value):
        raise ValueError("trigger must not contain whitespace")
    if not _TRIGGER_PATTERN.match(value):
        raise ValueError(
            "trigger must match event:<name>, manual_<name>, or system_<name>, "
            "where <name> is snake_case or dot.namespace.style (lowercase)"
        )
    return value


class _EngineBase(BaseModel):
    if _PYDANTIC_V2:
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
            populate_by_name=True,
        )
    else:

        class Config:  # pragma: no cover
            extra = "forbid"
            validate_assignment = True
            allow_population_by_field_name = True


class TransitionFailureCode(str, Enum):
    """Taxonomy for validation failures (deterministic, stable strings)."""

    UNKNOWN_DOMAIN = "unknown_domain"
    ILLEGAL_TRANSITION = "illegal_transition"
    NO_MATCHING_RULE = "no_matching_rule"
    TRIGGER_NOT_ALLOWED = "trigger_not_allowed"
    INVALID_TRIGGER = "invalid_trigger"
    TERMINAL_STATE_BLOCKED = "terminal_state_blocked"
    GUARD_REJECTED = "guard_rejected"
    REPLAY_INVARIANT_VIOLATION = "replay_invariant_violation"


class ReplayValidationMode(str, Enum):
    """How strictly to apply guards during replay (orchestrator-neutral hint)."""

    STRICT = "strict"
    """Evaluate guards the same as live validation."""

    SKIP_GUARDS = "skip_guards"
    """Skip optional guard evaluation; still enforce graph/terminal/trigger rules."""


class TransitionReplayContext(_EngineBase):
    """
    Replay-aware validation signals.

    Orchestrators may set ``replay_mode`` when re-applying historical transitions;
    guards can be skipped for pure structural replay while keeping edge legality.
    """

    replay_mode: bool = Field(default=False)
    replay_run_id: Optional[UUID] = Field(default=None)
    validation_mode: ReplayValidationMode = Field(default=ReplayValidationMode.STRICT)

    extensions: Dict[str, Any] = Field(default_factory=dict)

    if _PYDANTIC_V2:

        @model_validator(mode="after")
        def _replay_invariants(self):  # type: ignore[override]
            if self.replay_mode and self.replay_run_id is None:
                raise ValueError("replay_run_id is required when replay_mode is true")
            return self

    else:

        @root_validator
        def _replay_invariants(cls, values):  # type: ignore[override]
            if values.get("replay_mode") and values.get("replay_run_id") is None:
                raise ValueError("replay_run_id is required when replay_mode is true")
            return values


class TransitionContext(_EngineBase):
    """
    Everything needed to validate one proposed transition deterministically.

    ``trigger`` must follow the project trigger naming convention (see module docstring):
    ``event:...``, ``manual_...``, or ``system_...`` with a stable ``<name>`` tail.
    """

    state_domain: StateDomain
    from_state: str = Field(..., min_length=1)
    to_state: str = Field(..., min_length=1)
    trigger: str = Field(
        ...,
        min_length=1,
        description=(
            "Stable trigger id: event:<name>, manual_<name>, or system_<name> "
            "(<name> snake_case or dot.namespace; no whitespace)."
        ),
    )

    actor: StateActor
    event_id: Optional[UUID] = Field(default=None)

    human_override: bool = Field(
        default=False,
        description="True when a human operator intentionally overrides normal policy.",
    )

    rule_set_id: Optional[str] = Field(
        default=None,
        description="Optional identifier of the rule set used (replay/audit alignment).",
    )

    replay: TransitionReplayContext = Field(default_factory=TransitionReplayContext)

    extensions: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("trigger")
    @classmethod
    def _trigger_naming(cls, v: str) -> str:  # type: ignore[override]
        return validate_trigger_naming(v)


class GuardEvaluation(_EngineBase):
    """Result of one deterministic guard check."""

    ok: bool
    code: Optional[str] = Field(default=None, description="Stable machine-readable code.")
    message: Optional[str] = Field(default=None, description="Human-readable explanation.")
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="Optional refs to artifacts supporting the decision.",
    )


class TransitionGuard(Protocol):
    """Optional guard: pure deterministic predicate over context."""

    def evaluate(self, ctx: TransitionContext) -> GuardEvaluation: ...


class TransitionRule(_EngineBase):
    """
    One allowed edge in the transition graph.

    - If ``allowed_triggers`` is empty, any **validly named** trigger on the context
      matches (see ``validate_trigger_naming``).
    - If non-empty, the context trigger must be in the set (each entry must obey the
      same naming convention).
    - ``guard_ids`` reference named guards registered on the engine.
    """

    rule_id: str = Field(..., min_length=1)
    state_domain: StateDomain
    from_state: str = Field(..., min_length=1)
    to_state: str = Field(..., min_length=1)

    allowed_triggers: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="If empty, any non-empty trigger matches; otherwise must be one of these.",
    )
    guard_ids: Tuple[str, ...] = Field(default_factory=tuple)

    description: Optional[str] = Field(
        default=None, description="Documentation only; not used in validation logic."
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)

    if _PYDANTIC_V2:

        @field_validator("allowed_triggers", mode="before")
        @classmethod
        def _normalize_triggers(cls, v):  # type: ignore[override]
            if v is None:
                return ()
            if isinstance(v, frozenset):
                return tuple(sorted(v))
            if isinstance(v, (list, tuple, set)):
                return tuple(sorted(frozenset(v)))
            return v

        @field_validator("allowed_triggers")
        @classmethod
        def _validate_allowed_trigger_names(cls, v: Tuple[str, ...]) -> Tuple[str, ...]:  # type: ignore[override]
            for t in v:
                validate_trigger_naming(t)
            return v

    else:

        @field_validator("allowed_triggers", pre=True)
        @classmethod
        def _normalize_triggers(cls, v):  # type: ignore[override]
            if v is None:
                return ()
            if isinstance(v, frozenset):
                return tuple(sorted(v))
            if isinstance(v, (list, tuple, set)):
                return tuple(sorted(frozenset(v)))
            return v

        @field_validator("allowed_triggers")
        @classmethod
        def _validate_allowed_trigger_names(cls, v):  # type: ignore[override]
            for t in v or ():
                validate_trigger_naming(t)
            return v


class TransitionRejection(_EngineBase):
    """Single structured rejection reason."""

    code: TransitionFailureCode
    rule_id: Optional[str] = Field(
        default=None, description="Rule involved, if any."
    )
    message: str = Field(..., min_length=1)
    details: Dict[str, Any] = Field(default_factory=dict)


class TransitionValidationResult(_EngineBase):
    """Outcome of validating a transition."""

    ok: bool
    matched_rule_id: Optional[str] = Field(default=None)
    rejections: List[TransitionRejection] = Field(default_factory=list)

    extensions: Dict[str, Any] = Field(default_factory=dict)

    if _PYDANTIC_V2:

        @model_validator(mode="after")
        def _result_invariants(self):  # type: ignore[override]
            if self.ok:
                if self.rejections:
                    raise ValueError("ok=true forbids rejections")
                if not self.matched_rule_id:
                    raise ValueError("ok=true requires matched_rule_id")
            else:
                if not self.rejections:
                    raise ValueError("ok=false requires at least one rejection")
                if self.matched_rule_id is not None:
                    raise ValueError("ok=false forbids matched_rule_id")
            return self

    else:

        @root_validator
        def _result_invariants(cls, values):  # type: ignore[override]
            ok = values.get("ok")
            rejections = values.get("rejections") or []
            mid = values.get("matched_rule_id")
            if ok:
                if rejections:
                    raise ValueError("ok=true forbids rejections")
                if not mid:
                    raise ValueError("ok=true requires matched_rule_id")
            else:
                if not rejections:
                    raise ValueError("ok=false requires at least one rejection")
                if mid is not None:
                    raise ValueError("ok=false forbids matched_rule_id")
            return values


@dataclass(frozen=True)
class TransitionRegistry:
    """
    Immutable, deterministic transition rule set.

    Rules are stored in stable sort order by ``rule_id`` for tie-breaking.
    """

    rules: Tuple[TransitionRule, ...] = ()
    terminal_states: Mapping[StateDomain, FrozenSet[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        sorted_rules = tuple(sorted(self.rules, key=lambda r: r.rule_id))
        object.__setattr__(self, "rules", sorted_rules)


def _wildcard_match(ctx_from: str, rule_from: str) -> bool:
    return rule_from == "*" or rule_from == ctx_from


def _rule_match_priority(rule: TransitionRule, ctx_from: str) -> Tuple[int, str]:
    """Prefer exact ``from_state`` matches over ``*``; then stable rule_id order."""
    prefer_exact = 0 if rule.from_state == ctx_from else 1
    return (prefer_exact, rule.rule_id)


class TransitionEngine:
    """
    Validates transitions against a registry and named guards.

    Thread-safe if guards are pure. No I/O.
    """

    def __init__(
        self,
        registry: TransitionRegistry,
        guards: Optional[Mapping[str, TransitionGuard]] = None,
    ) -> None:
        self._registry = registry
        self._guards: Dict[str, TransitionGuard] = dict(guards or {})

    def register_guard(self, guard_id: str, guard: TransitionGuard) -> None:
        if not guard_id or not guard_id.strip():
            raise ValueError("guard_id must be non-empty")
        self._guards[guard_id] = guard

    def validate(self, ctx: TransitionContext) -> TransitionValidationResult:
        # Replay: require run id when replay_mode (context validator also checks)
        if ctx.replay.replay_mode and ctx.replay.replay_run_id is None:
            return TransitionValidationResult(
                ok=False,
                rejections=[
                    TransitionRejection(
                        code=TransitionFailureCode.REPLAY_INVARIANT_VIOLATION,
                        message="replay_mode requires replay_run_id",
                    )
                ],
            )

        domain = ctx.state_domain
        if domain not in (
            StateDomain.PIPELINE,
            StateDomain.DECISION,
            StateDomain.COMMUNICATION,
        ):
            return TransitionValidationResult(
                ok=False,
                rejections=[
                    TransitionRejection(
                        code=TransitionFailureCode.UNKNOWN_DOMAIN,
                        message=f"Unsupported state domain: {domain!r}",
                        details={"state_domain": domain.value},
                    )
                ],
            )

        # Terminal: leaving a terminal state is blocked unless human override
        terminals = self._registry.terminal_states.get(domain, frozenset())
        if ctx.from_state in terminals and not ctx.human_override:
            return TransitionValidationResult(
                ok=False,
                rejections=[
                    TransitionRejection(
                        code=TransitionFailureCode.TERMINAL_STATE_BLOCKED,
                        message=(
                            f"Cannot transition from terminal state '{ctx.from_state}' "
                            f"without human_override"
                        ),
                        details={
                            "from_state": ctx.from_state,
                            "to_state": ctx.to_state,
                            "domain": domain.value,
                        },
                    )
                ],
            )

        candidates = [
            r
            for r in self._registry.rules
            if r.state_domain == domain
            and _wildcard_match(ctx.from_state, r.from_state)
            and r.to_state == ctx.to_state
        ]
        candidates = sorted(candidates, key=lambda r: _rule_match_priority(r, ctx.from_state))

        if not candidates:
            return TransitionValidationResult(
                ok=False,
                rejections=[
                    TransitionRejection(
                        code=TransitionFailureCode.ILLEGAL_TRANSITION,
                        message=(
                            f"No allowed transition {ctx.from_state!r} -> {ctx.to_state!r} "
                            f"in domain {domain.value}"
                        ),
                        details={
                            "from_state": ctx.from_state,
                            "to_state": ctx.to_state,
                            "trigger": ctx.trigger,
                        },
                    )
                ],
            )

        matched: Optional[TransitionRule] = None
        trigger_rejection: Optional[TransitionRejection] = None

        for rule in candidates:
            if rule.allowed_triggers and ctx.trigger not in rule.allowed_triggers:
                trigger_rejection = TransitionRejection(
                    code=TransitionFailureCode.TRIGGER_NOT_ALLOWED,
                    rule_id=rule.rule_id,
                    message=(
                        f"Trigger {ctx.trigger!r} not allowed for rule {rule.rule_id}; "
                        f"allowed: {list(rule.allowed_triggers)}"
                    ),
                    details={"trigger": ctx.trigger, "allowed": list(rule.allowed_triggers)},
                )
                continue
            matched = rule
            break

        if matched is None:
            if trigger_rejection is not None:
                return TransitionValidationResult(
                    ok=False,
                    rejections=[trigger_rejection],
                )
            return TransitionValidationResult(
                ok=False,
                rejections=[
                    TransitionRejection(
                        code=TransitionFailureCode.NO_MATCHING_RULE,
                        message="No rule matched trigger constraints",
                        details={"trigger": ctx.trigger},
                    )
                ],
            )

        skip_guards = (
            ctx.replay.replay_mode
            and ctx.replay.validation_mode == ReplayValidationMode.SKIP_GUARDS
        )

        if not skip_guards:
            for gid in matched.guard_ids:
                g = self._guards.get(gid)
                if g is None:
                    return TransitionValidationResult(
                        ok=False,
                        rejections=[
                            TransitionRejection(
                                code=TransitionFailureCode.GUARD_REJECTED,
                                rule_id=matched.rule_id,
                                message=f"Unknown guard_id: {gid!r}",
                                details={"guard_id": gid},
                            )
                        ],
                    )
                ev = g.evaluate(ctx)
                if not ev.ok:
                    return TransitionValidationResult(
                        ok=False,
                        rejections=[
                            TransitionRejection(
                                code=TransitionFailureCode.GUARD_REJECTED,
                                rule_id=matched.rule_id,
                                message=ev.message or f"Guard {gid!r} rejected",
                                details={
                                    "guard_id": gid,
                                    "guard_code": ev.code,
                                    "evidence_refs": ev.evidence_refs,
                                },
                            )
                        ],
                    )

        return TransitionValidationResult(
            ok=True,
            matched_rule_id=matched.rule_id,
            rejections=[],
        )


def default_pipeline_registry() -> TransitionRegistry:
    """
    Recruiter pipeline edges (deterministic; validated by :class:`TransitionEngine`).

    Automated ranking uses ``system_ranking_*`` triggers; human lifecycle uses
    ``manual_*`` and ``event:offer_*``; ``inactive`` is not terminal (``hired`` is).
    """
    from schemas.state_schema import PipelinePhase

    p = PipelinePhase

    # ``manual_recruiter_send_offer`` only after evaluation + shortlist/interview posture.
    send_from = (
        p.DEEP_SCORED,
        p.SHORTLISTED,
        p.INTERVIEW_PENDING,
        p.INTERVIEW_COMPLETED,
    )

    rules: List[TransitionRule] = [
        TransitionRule(
            rule_id="pipeline.new_to_cv_received",
            state_domain=StateDomain.PIPELINE,
            from_state=p.NEW.value,
            to_state=p.CV_RECEIVED.value,
            allowed_triggers=("event:cv_uploaded",),
        ),
        TransitionRule(
            rule_id="pipeline.cv_received_to_cv_parsed",
            state_domain=StateDomain.PIPELINE,
            from_state=p.CV_RECEIVED.value,
            to_state=p.CV_PARSED.value,
            allowed_triggers=("event:cv_parsed",),
        ),
        TransitionRule(
            rule_id="pipeline.new_to_cv_received_cv_submitted",
            state_domain=StateDomain.PIPELINE,
            from_state=p.NEW.value,
            to_state=p.CV_RECEIVED.value,
            allowed_triggers=("event:cv_submitted",),
        ),
        TransitionRule(
            rule_id="pipeline.cv_parsed_to_light_scored",
            state_domain=StateDomain.PIPELINE,
            from_state=p.CV_PARSED.value,
            to_state=p.LIGHT_SCORED.value,
            allowed_triggers=("event:light_scoring_completed",),
        ),
        TransitionRule(
            rule_id="pipeline.cv_parsed_to_hard_filter_passed",
            state_domain=StateDomain.PIPELINE,
            from_state=p.CV_PARSED.value,
            to_state=p.HARD_FILTER_PASSED.value,
            allowed_triggers=("event:hard_filter_passed",),
        ),
        TransitionRule(
            rule_id="pipeline.cv_parsed_to_inactive_filter_failed",
            state_domain=StateDomain.PIPELINE,
            from_state=p.CV_PARSED.value,
            to_state=p.INACTIVE.value,
            allowed_triggers=("event:hard_filter_failed", "manual_inactive"),
        ),
        TransitionRule(
            rule_id="pipeline.hard_filter_passed_to_light_scored",
            state_domain=StateDomain.PIPELINE,
            from_state=p.HARD_FILTER_PASSED.value,
            to_state=p.LIGHT_SCORED.value,
            allowed_triggers=("event:light_scoring_completed",),
        ),
        TransitionRule(
            rule_id="pipeline.light_scored_to_shortlisted_rank_top_k",
            state_domain=StateDomain.PIPELINE,
            from_state=p.LIGHT_SCORED.value,
            to_state=p.SHORTLISTED.value,
            allowed_triggers=("system_ranking_top_k",),
        ),
        TransitionRule(
            rule_id="pipeline.light_scored_to_questionnaire_pending_legacy",
            state_domain=StateDomain.PIPELINE,
            from_state=p.LIGHT_SCORED.value,
            to_state=p.QUESTIONNAIRE_PENDING.value,
            allowed_triggers=("event:questionnaire_requested",),
        ),
        TransitionRule(
            rule_id="pipeline.light_scored_to_questionnaire_pending_rank_mid_m",
            state_domain=StateDomain.PIPELINE,
            from_state=p.LIGHT_SCORED.value,
            to_state=p.QUESTIONNAIRE_PENDING.value,
            allowed_triggers=("system_ranking_mid_m",),
        ),
        TransitionRule(
            rule_id="pipeline.light_scored_to_inactive_rank_reject",
            state_domain=StateDomain.PIPELINE,
            from_state=p.LIGHT_SCORED.value,
            to_state=p.INACTIVE.value,
            allowed_triggers=("system_ranking_reject",),
        ),
        TransitionRule(
            rule_id="pipeline.questionnaire_pending_to_sent",
            state_domain=StateDomain.PIPELINE,
            from_state=p.QUESTIONNAIRE_PENDING.value,
            to_state=p.QUESTIONNAIRE_SENT.value,
            allowed_triggers=("event:questionnaire_sent",),
        ),
        TransitionRule(
            rule_id="pipeline.questionnaire_sent_to_completed",
            state_domain=StateDomain.PIPELINE,
            from_state=p.QUESTIONNAIRE_SENT.value,
            to_state=p.QUESTIONNAIRE_COMPLETED.value,
            allowed_triggers=("event:questionnaire_completed",),
        ),
        TransitionRule(
            rule_id="pipeline.questionnaire_completed_to_deep_scored",
            state_domain=StateDomain.PIPELINE,
            from_state=p.QUESTIONNAIRE_COMPLETED.value,
            to_state=p.DEEP_SCORED.value,
            allowed_triggers=("event:deep_scoring_completed",),
        ),
        TransitionRule(
            rule_id="pipeline.deep_scored_to_inactive_rank_reject",
            state_domain=StateDomain.PIPELINE,
            from_state=p.DEEP_SCORED.value,
            to_state=p.INACTIVE.value,
            allowed_triggers=("system_ranking_reject",),
        ),
        TransitionRule(
            rule_id="pipeline.deep_scored_to_shortlisted_rank_top_k",
            state_domain=StateDomain.PIPELINE,
            from_state=p.DEEP_SCORED.value,
            to_state=p.SHORTLISTED.value,
            allowed_triggers=("system_ranking_top_k",),
        ),
        TransitionRule(
            rule_id="pipeline.deep_scored_to_shortlisted_manual",
            state_domain=StateDomain.PIPELINE,
            from_state=p.DEEP_SCORED.value,
            to_state=p.SHORTLISTED.value,
            allowed_triggers=(
                "manual_recruiter_shortlist_candidate",
                "manual_recruiter_approve",
            ),
        ),
        TransitionRule(
            rule_id="pipeline.inactive_to_shortlisted_reconsider",
            state_domain=StateDomain.PIPELINE,
            from_state=p.INACTIVE.value,
            to_state=p.SHORTLISTED.value,
            allowed_triggers=("manual_recruiter_reconsider",),
        ),
        TransitionRule(
            rule_id="pipeline.interview_completed_to_interview_pending_next_round",
            state_domain=StateDomain.PIPELINE,
            from_state=p.INTERVIEW_COMPLETED.value,
            to_state=p.INTERVIEW_PENDING.value,
            allowed_triggers=("manual_recruiter_schedule_interview",),
        ),
        TransitionRule(
            rule_id="pipeline.shortlisted_to_interview_pending",
            state_domain=StateDomain.PIPELINE,
            from_state=p.SHORTLISTED.value,
            to_state=p.INTERVIEW_PENDING.value,
            allowed_triggers=("manual_recruiter_schedule_interview",),
        ),
        TransitionRule(
            rule_id="pipeline.interview_pending_to_completed",
            state_domain=StateDomain.PIPELINE,
            from_state=p.INTERVIEW_PENDING.value,
            to_state=p.INTERVIEW_COMPLETED.value,
            allowed_triggers=("manual_recruiter_complete_interview",),
        ),
        TransitionRule(
            rule_id="pipeline.offer_sent_to_hired",
            state_domain=StateDomain.PIPELINE,
            from_state=p.OFFER_SENT.value,
            to_state=p.HIRED.value,
            allowed_triggers=("event:offer_accepted", "manual_recruiter_mark_hired"),
        ),
        TransitionRule(
            rule_id="pipeline.offer_sent_to_inactive_offer_declined",
            state_domain=StateDomain.PIPELINE,
            from_state=p.OFFER_SENT.value,
            to_state=p.INACTIVE.value,
            allowed_triggers=("event:offer_declined",),
        ),
        TransitionRule(
            rule_id="pipeline.any_to_inactive_reject",
            state_domain=StateDomain.PIPELINE,
            from_state="*",
            to_state=p.INACTIVE.value,
            allowed_triggers=("event:candidate_rejected", "manual_recruiter_reject"),
        ),
    ]

    for sf in send_from:
        rules.append(
            TransitionRule(
                rule_id=f"pipeline.{sf.value}_to_offer_sent_send_offer",
                state_domain=StateDomain.PIPELINE,
                from_state=sf.value,
                to_state=p.OFFER_SENT.value,
                allowed_triggers=("manual_recruiter_send_offer",),
            )
        )

    terminals: Dict[StateDomain, FrozenSet[str]] = {
        StateDomain.PIPELINE: frozenset({p.HIRED.value}),
    }
    return TransitionRegistry(rules=tuple(rules), terminal_states=terminals)
