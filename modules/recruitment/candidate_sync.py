"""
Candidate ↔ orchestration snapshot consistency (R-009.1).

Deterministic reconciliation when dual-write partially fails; read-time convergence
when snapshot evaluation_status_ref lags canonical Candidate.evaluation_revision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol, Tuple
from uuid import UUID

from modules.recruitment.candidate_writes import finalize_orchestration_snapshot
from runtime.persistence.sqlite_candidate_store import CandidateStoreFailureCode
from schemas.candidate_schema import Candidate
from schemas.state_schema import OrchestrationState

from .exceptions import CandidateCanonicalMissingError, CandidateStoreUnavailableError

logger = logging.getLogger(__name__)

SNAPSHOT_RECONCILE_MAX_ATTEMPTS = 3
READ_CANDIDATE_STORE_MAX_ATTEMPTS = 3

SYNC_PENDING_SNAPSHOT_RECONCILE = "sync.pending_snapshot_reconcile"
SYNC_LAST_OUTCOME = "sync.last_dual_write_outcome"


class DualWriteErrorCode(str, Enum):
    CANDIDATE_REPLACE_FAILED = "candidate_replace_failed"
    SNAPSHOT_REPLACE_FAILED_AFTER_CANDIDATE = "snapshot_replace_failed_after_candidate_success"
    RECONCILIATION_SUCCEEDED = "reconciliation_succeeded"
    RECONCILIATION_FAILED = "reconciliation_failed"


@dataclass(frozen=True)
class PersistDualWriteOutcome:
    ok: bool
    error_code: Optional[str] = None
    message: str = ""
    reconciliation_attempted: bool = False
    reconciliation_succeeded: bool = False
    candidate_revision: Optional[int] = None


class _OrchestrationStore(Protocol):
    def get(self, state_id: UUID) -> Any: ...
    def get_for_candidate(self, candidate_id: UUID) -> Any: ...
    def replace(
        self,
        state_id: UUID,
        snapshot: OrchestrationState,
        *,
        expected_store_revision: int,
    ) -> Any: ...


class _CandidateStore(Protocol):
    def get(self, candidate_id: UUID) -> Any: ...
    def replace(self, candidate: Candidate, *, expected_store_revision: int) -> Any: ...


def evaluation_ref_lags_candidate(
    snapshot: OrchestrationState,
    candidate: Candidate,
) -> bool:
    ref = snapshot.evaluation_status_ref
    ref_rev = int(ref.revision) if ref is not None else -1
    return int(candidate.evaluation_revision) > ref_rev


def _mark_candidate_pending_reconcile(
    candidate: Candidate,
    *,
    state_id: UUID,
    outcome_code: str,
) -> Candidate:
    sync = dict(candidate.extensions.get("sync") or {})
    sync[SYNC_PENDING_SNAPSHOT_RECONCILE] = True
    sync["state_id"] = str(state_id)
    sync[SYNC_LAST_OUTCOME] = outcome_code
    return candidate.model_copy(update={"extensions": {**candidate.extensions, "sync": sync}})


def _clear_candidate_pending_reconcile(candidate: Candidate) -> Candidate:
    sync = dict(candidate.extensions.get("sync") or {})
    sync.pop(SYNC_PENDING_SNAPSHOT_RECONCILE, None)
    sync[SYNC_LAST_OUTCOME] = DualWriteErrorCode.RECONCILIATION_SUCCEEDED.value
    return candidate.model_copy(update={"extensions": {**candidate.extensions, "sync": sync}})


def persist_candidate_and_snapshot_with_reconcile(
    *,
    candidate_store: _CandidateStore,
    orchestration_store: _OrchestrationStore,
    state_id: UUID,
    candidate_id: UUID,
    workflow_snapshot: OrchestrationState,
    candidate: Candidate,
    expected_snapshot_revision: int,
) -> PersistDualWriteOutcome:
    """
    Replace canonical Candidate then orchestration snapshot; reconcile on snapshot failure.
    """
    got_c = candidate_store.get(candidate_id)
    if not got_c.ok or got_c.meta is None:
        return PersistDualWriteOutcome(
            ok=False,
            error_code=DualWriteErrorCode.CANDIDATE_REPLACE_FAILED.value,
            message=f"candidate store get failed before replace: {got_c.failure}",
        )
    rep_c = candidate_store.replace(candidate, expected_store_revision=got_c.meta.store_revision)
    if not rep_c.ok or rep_c.candidate is None:
        logger.warning(
            "dual_write candidate_replace_failed candidate_id=%s failure=%s",
            candidate_id,
            rep_c.failure,
        )
        return PersistDualWriteOutcome(
            ok=False,
            error_code=DualWriteErrorCode.CANDIDATE_REPLACE_FAILED.value,
            message=f"candidate store replace failed: {rep_c.failure}",
        )
    cand = rep_c.candidate
    snap = finalize_orchestration_snapshot(workflow_snapshot, cand)

    for attempt in range(1, SNAPSHOT_RECONCILE_MAX_ATTEMPTS + 1):
        rep_s = orchestration_store.replace(
            state_id,
            snap,
            expected_store_revision=expected_snapshot_revision,
        )
        if rep_s.ok:
            logger.info(
                "dual_write snapshot_replace_ok candidate_id=%s state_id=%s attempt=%s",
                candidate_id,
                state_id,
                attempt,
            )
            return PersistDualWriteOutcome(
                ok=True,
                candidate_revision=cand.evaluation_revision,
            )
        logger.warning(
            "dual_write snapshot_replace_failed candidate_id=%s state_id=%s attempt=%s failure=%s",
            candidate_id,
            state_id,
            attempt,
            rep_s.failure,
        )
        got_s = orchestration_store.get(state_id)
        if got_s.ok and got_s.meta is not None:
            expected_snapshot_revision = got_s.meta.store_revision
        snap = finalize_orchestration_snapshot(workflow_snapshot, cand)

    logger.warning(
        "dual_write reconciliation_failed candidate_id=%s state_id=%s after candidate success",
        candidate_id,
        state_id,
    )
    cand = _mark_candidate_pending_reconcile(
        cand,
        state_id=state_id,
        outcome_code=DualWriteErrorCode.RECONCILIATION_FAILED.value,
    )
    got_c2 = candidate_store.get(candidate_id)
    if got_c2.ok and got_c2.meta is not None:
        candidate_store.replace(cand, expected_store_revision=got_c2.meta.store_revision)

    return PersistDualWriteOutcome(
        ok=False,
        error_code=DualWriteErrorCode.SNAPSHOT_REPLACE_FAILED_AFTER_CANDIDATE.value,
        message="state store replace failed after candidate success; reconciliation exhausted",
        reconciliation_attempted=True,
        reconciliation_succeeded=False,
        candidate_revision=cand.evaluation_revision,
    )


def load_candidate_for_read(
    candidate_store: _CandidateStore,
    candidate_id: UUID,
    *,
    orchestration_exists: bool,
) -> Candidate:
    """
    Load canonical Candidate for recruiter read surfaces (fail-fast, bounded retries).

    Does not fall back to legacy snapshot profile/evaluation when the store is unavailable.
    """
    last_failure: Any = None
    for attempt in range(1, READ_CANDIDATE_STORE_MAX_ATTEMPTS + 1):
        got = candidate_store.get(candidate_id)
        if got.ok and got.candidate is not None:
            return got.candidate
        last_failure = got.failure
        if got.failure is not None and got.failure.code == CandidateStoreFailureCode.NOT_FOUND:
            if orchestration_exists:
                raise CandidateCanonicalMissingError(
                    f"canonical candidate row missing while orchestration state exists: {candidate_id!s}"
                )
            raise CandidateCanonicalMissingError(
                f"candidate not found in canonical store: {candidate_id!s}"
            )
        logger.warning(
            "candidate_store_read_failed candidate_id=%s attempt=%s failure=%s",
            candidate_id,
            attempt,
            got.failure,
        )
    raise CandidateStoreUnavailableError(
        f"candidate store unavailable after {READ_CANDIDATE_STORE_MAX_ATTEMPTS} attempts: {last_failure}"
    )


def converge_snapshot_for_read(
    runtime: Any,
    candidate_id: UUID,
    snapshot: OrchestrationState,
    candidate: Candidate,
) -> OrchestrationState:
    """
    Best-effort: refresh snapshot evaluation_status_ref when it lags Candidate revision.
    """
    pending = bool((candidate.extensions.get("sync") or {}).get(SYNC_PENDING_SNAPSHOT_RECONCILE))
    if not evaluation_ref_lags_candidate(snapshot, candidate) and not pending:
        return snapshot

    snap = finalize_orchestration_snapshot(snapshot, candidate)
    store = runtime.bundle.store
    for attempt in range(1, SNAPSHOT_RECONCILE_MAX_ATTEMPTS + 1):
        got = store.get_for_candidate(candidate_id)
        if not got.ok or got.snapshot is None or got.meta is None:
            break
        rep = store.replace(
            got.meta.state_id,
            snap,
            expected_store_revision=got.meta.store_revision,
        )
        if rep.ok and rep.snapshot is not None:
            logger.info(
                "reconciliation_read_time_ok candidate_id=%s attempt=%s",
                candidate_id,
                attempt,
            )
            return rep.snapshot
        logger.warning(
            "reconciliation_read_time_failed candidate_id=%s attempt=%s failure=%s",
            candidate_id,
            attempt,
            rep.failure,
        )
        got = store.get_for_candidate(candidate_id)
        if got.ok and got.snapshot is not None:
            snap = finalize_orchestration_snapshot(got.snapshot, candidate)

    raise CandidateStoreUnavailableError(
        "snapshot read-time convergence failed; candidate and orchestration stores diverged"
    )


def load_candidate_and_snapshot_for_read(
    runtime: Any,
    candidate_id: UUID,
) -> Tuple[Candidate, OrchestrationState]:
    got = runtime.bundle.store.get_for_candidate(candidate_id)
    if not got.ok or got.snapshot is None:
        from .exceptions import CandidateNotFoundError

        raise CandidateNotFoundError(f"no orchestration state for candidate: {candidate_id!s}")
    snapshot = got.snapshot
    candidate = load_candidate_for_read(
        runtime.candidate_store,
        candidate_id,
        orchestration_exists=True,
    )
    snapshot = converge_snapshot_for_read(runtime, candidate_id, snapshot, candidate)
    return candidate, snapshot
